"""Outgoing webhooks: URL safety (SSRF), signing and delivery.

Signature header (verify on the receiving side, e.g. in an n8n Code node)::

    X-PropTech-Event: lead.created
    X-PropTech-Delivery: <delivery id>
    X-PropTech-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256(secret, f"{t}.{raw body}")>

Receivers should reject signatures older than 5 minutes.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import socket
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.core.config import get_settings

# Event names a webhook may subscribe to ("*" = all).
WEBHOOK_EVENTS = [
    "listing.created",
    "listing.updated",
    "listing.published",
    "listing.rejected",
    "listing.suspended",
    "listing.expired",
    "listing.reported",
    "lead.created",
    "lead.assigned",
    "lead.status_changed",
    "inquiry.created",
    "message.created",
    "appointment.scheduled",
    "report.created",
    "report.resolved",
    "user.registered",
]

# Internal domain events → public webhook event names.
EVENT_ALIASES = {
    "property.approved": "listing.published",
    "property.rejected": "listing.rejected",
    "property.suspended": "listing.suspended",
    "property.expired": "listing.expired",
}


class UnsafeURLError(ValueError):
    pass


def check_url(url: str, *, resolve: bool = True) -> None:
    """Reject URLs that could reach internal services (SSRF) unless explicitly allowed."""
    settings = get_settings()
    parts = urlsplit(url)
    if parts.scheme not in ("https", "http") or not parts.hostname:
        raise UnsafeURLError("URL must be http(s) with a host")
    if parts.username or parts.password:
        raise UnsafeURLError("credentials in URLs are not allowed")
    if parts.scheme == "http" and not settings.webhook_allow_http:
        raise UnsafeURLError("https is required")
    if settings.webhook_allow_private_hosts or not resolve:
        return
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError("host does not resolve") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            raise UnsafeURLError("host resolves to a private or reserved address")


def sign(secret: str, body: bytes, timestamp: int | None = None) -> str:
    ts = int(time.time()) if timestamp is None else timestamp
    digest = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def verify(secret: str, body: bytes, header: str, tolerance: int = 300) -> bool:
    try:
        fields = dict(part.split("=", 1) for part in header.split(","))
        ts = int(fields["t"])
    except (KeyError, ValueError):
        return False
    if abs(time.time() - ts) > tolerance:
        return False
    expected = sign(secret, body, ts)
    return hmac.compare_digest(expected, header)


def post(
    url: str,
    secret: str,
    event: str,
    delivery_id: str,
    payload: dict[str, Any],
    client: httpx.Client | None = None,
) -> int:
    """Send one webhook; returns the HTTP status. Raises on network errors / unsafe URLs."""
    check_url(url)
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode()
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "IraqPropTech-Webhooks/1",
        "X-PropTech-Event": event,
        "X-PropTech-Delivery": delivery_id,
        "X-PropTech-Signature": sign(secret, body),
    }
    owned = client is None
    http = client or httpx.Client(timeout=10, follow_redirects=False)
    try:
        return http.post(url, content=body, headers=headers).status_code
    finally:
        if owned:
            http.close()
