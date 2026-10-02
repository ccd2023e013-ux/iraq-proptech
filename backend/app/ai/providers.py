"""AI provider abstraction.

Every generative feature calls ``AIProvider.generate`` with a task name, a
system instruction, the *facts* it may use, and the JSON shape it must
return. Providers return parsed JSON plus usage metadata; the caller
validates the result against a schema and against the facts (see
``app/ai/guards.py``) before anything reaches a user.

``MockAIProvider`` (default) is deterministic and offline: it fills Arabic /
English templates strictly from the supplied facts, so the whole product works
— and is testable — without any API key or cost. Real adapters (Anthropic
Claude, OpenAI, Google Gemini) use plain HTTPS via ``httpx``; no vendor SDK is
required and switching provider is configuration only.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.core.config import Settings, get_settings


class AIProviderError(Exception):
    """The provider failed or returned something unusable."""


@dataclass
class AIRequest:
    task: str
    system: str
    facts: dict[str, Any]
    output_schema: dict[str, Any]
    instructions: str = ""
    language: str = "ar"
    max_tokens: int = 1200


@dataclass
class AIResponse:
    data: dict[str, Any]
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int = 0
    raw_text: str = field(default="", repr=False)


class AIProvider(Protocol):
    name: str
    model: str

    def generate(self, request: AIRequest) -> AIResponse: ...


def _user_prompt(request: AIRequest) -> str:
    return (
        f"{request.instructions}\n\n"
        "FACTS (the only information you may use; never add or infer other facts):\n"
        f"{json.dumps(request.facts, ensure_ascii=False, default=str)}\n\n"
        f"Answer in language: {request.language}.\n"
        "Return ONLY a JSON object matching this JSON Schema, with no prose around it:\n"
        f"{json.dumps(request.output_schema, ensure_ascii=False)}"
    )


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise AIProviderError("Provider did not return a JSON object")
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AIProviderError("Provider returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise AIProviderError("Provider returned a non-object JSON value")
    return value


class _HttpProvider:
    name = "http"
    default_model = ""

    def __init__(
        self, api_key: str, model: str | None, settings: Settings, client: httpx.Client | None
    ) -> None:
        self.api_key = api_key
        self.model = model or self.default_model
        self.settings = settings
        self.client = client or httpx.Client(timeout=settings.ai_timeout_seconds)

    def _post(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.client.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise AIProviderError(f"{self.name} request failed: {type(exc).__name__}") from exc
        if response.status_code >= 400:
            # Never echo the response body: it may contain prompt data.
            raise AIProviderError(f"{self.name} returned HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise AIProviderError(f"{self.name} returned a non-JSON response") from exc


class ClaudeProvider(_HttpProvider):
    """Anthropic Messages API."""

    name = "claude"
    default_model = "claude-sonnet-5-5"
    url = "https://api.anthropic.com/v1/messages"

    def generate(self, request: AIRequest) -> AIResponse:
        started = time.monotonic()
        payload = self._post(
            self.url,
            {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            {
                "model": self.model,
                "max_tokens": request.max_tokens,
                "system": request.system,
                "messages": [{"role": "user", "content": _user_prompt(request)}],
            },
        )
        text = "".join(
            block.get("text", "")
            for block in payload.get("content", [])
            if block.get("type") == "text"
        )
        usage = payload.get("usage", {})
        return AIResponse(
            data=_parse_json(text),
            provider=self.name,
            model=str(payload.get("model", self.model)),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            latency_ms=int((time.monotonic() - started) * 1000),
            raw_text=text,
        )


class OpenAIProvider(_HttpProvider):
    """OpenAI Chat Completions API (JSON mode)."""

    name = "openai"
    default_model = "gpt-4o-mini"
    url = "https://api.openai.com/v1/chat/completions"

    def generate(self, request: AIRequest) -> AIResponse:
        started = time.monotonic()
        payload = self._post(
            self.url,
            {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            {
                "model": self.model,
                "max_tokens": request.max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": request.system},
                    {"role": "user", "content": _user_prompt(request)},
                ],
            },
        )
        choices = payload.get("choices") or [{}]
        text = (choices[0].get("message") or {}).get("content") or ""
        usage = payload.get("usage", {})
        return AIResponse(
            data=_parse_json(text),
            provider=self.name,
            model=str(payload.get("model", self.model)),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            latency_ms=int((time.monotonic() - started) * 1000),
            raw_text=text,
        )


class GeminiProvider(_HttpProvider):
    """Google Gemini generateContent API (JSON response MIME type)."""

    name = "gemini"
    default_model = "gemini-1.5-flash"

    def generate(self, request: AIRequest) -> AIResponse:
        started = time.monotonic()
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )
        payload = self._post(
            url,
            {"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            {
                "systemInstruction": {"parts": [{"text": request.system}]},
                "contents": [{"role": "user", "parts": [{"text": _user_prompt(request)}]}],
                "generationConfig": {
                    "maxOutputTokens": request.max_tokens,
                    "responseMimeType": "application/json",
                },
            },
        )
        candidates = payload.get("candidates") or [{}]
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)
        usage = payload.get("usageMetadata", {})
        return AIResponse(
            data=_parse_json(text),
            provider=self.name,
            model=self.model,
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
            latency_ms=int((time.monotonic() - started) * 1000),
            raw_text=text,
        )


class MockAIProvider:
    """Deterministic, offline provider. Uses templates filled only from facts."""

    name = "mock"
    model = "mock-templates-v1"

    def generate(self, request: AIRequest) -> AIResponse:
        from app.ai import templates  # local import: templates depend on domain enums

        started = time.monotonic()
        builder = templates.BUILDERS.get(request.task)
        if builder is None:
            raise AIProviderError(f"Mock provider has no template for task {request.task!r}")
        data = builder(request.facts, request.language)
        return AIResponse(
            data=data,
            provider=self.name,
            model=self.model,
            input_tokens=0,
            output_tokens=0,
            latency_ms=int((time.monotonic() - started) * 1000),
        )


_override: AIProvider | None = None


def set_provider_override(provider: AIProvider | None) -> None:
    """Tests/ops: force a provider instance (None restores configuration)."""
    global _override
    _override = provider


def get_provider(settings: Settings | None = None) -> AIProvider:
    if _override is not None:
        return _override
    settings = settings or get_settings()
    # A provider without its key falls back to mock: misconfiguration must not take
    # the product down.
    if settings.ai_provider == "claude" and settings.anthropic_api_key:
        return ClaudeProvider(settings.anthropic_api_key, settings.ai_model, settings, None)
    if settings.ai_provider == "openai" and settings.openai_api_key:
        return OpenAIProvider(settings.openai_api_key, settings.ai_model, settings, None)
    if settings.ai_provider == "gemini" and settings.gemini_api_key:
        return GeminiProvider(settings.gemini_api_key, settings.ai_model, settings, None)
    return MockAIProvider()
