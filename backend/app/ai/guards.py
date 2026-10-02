"""Fact guards for generated text.

Generated text may only restate facts it was given. These checks run on every
generative output (mock or real provider) before it is returned:

* every number in the output must appear in the facts;
* sensitive claims (ownership/legal status, guaranteed returns, "verified")
  are allowed only when the corresponding fact supports them.

A failing output is rejected and replaced by the deterministic template.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.ai.nlsearch import normalize

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")

# claim → fact key that must be truthy for the claim to be allowed
SENSITIVE_CLAIMS: dict[str, tuple[str, ...]] = {
    "ownership": ("طابو", "سند ملكيه", "tapu", "title deed", "freehold"),
    "verified": ("موثق", "verified"),
    "guarantee": ("مضمون", "ارباح مضمونه", "guaranteed", "guarantee"),
}
CLAIM_FACT = {"ownership": "ownership_declared", "verified": "verified", "guarantee": "__never__"}


def _numbers(text: str) -> set[str]:
    out = set()
    for raw in _NUMBER.findall(normalize(text)):
        cleaned = raw.replace(",", "")
        if "." in cleaned:
            cleaned = cleaned.rstrip("0").rstrip(".")
        out.add(cleaned)
    return out


def fact_numbers(facts: dict[str, Any]) -> set[str]:
    text = json.dumps(facts, ensure_ascii=False, default=str)
    numbers = _numbers(text)
    # also accept grouped forms of the same amounts, e.g. "200,000,000"
    return numbers | {n.replace(",", "") for n in numbers}


def check_text(text: str, facts: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    allowed = fact_numbers(facts)
    for number in sorted(_numbers(text)):
        if number not in allowed:
            problems.append(f"number_not_in_facts:{number}")
    normalized = normalize(text)
    for claim, phrases in SENSITIVE_CLAIMS.items():
        if any(normalize(p) in normalized for p in phrases) and not facts.get(CLAIM_FACT[claim]):
            problems.append(f"unsupported_claim:{claim}")
    return problems


def collect_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(collect_text(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(collect_text(v) for v in value)
    return ""
