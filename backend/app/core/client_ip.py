"""Client IP resolution behind a known number of reverse proxies.

Rate limits, analytics de-duplication and the audit log key on the client
address. In Docker the API's socket peer is the frontend proxy (or an edge
proxy), so every user would share one address. ``TRUSTED_PROXY_HOPS`` says
how many proxies *in front of the frontend* append to ``X-Forwarded-For``
(Caddy/nginx/Cloudflare Tunnel/Render's edge: 1). The client address is the
entry those proxies appended; anything to its left is client-controlled and
ignored. The default ``0`` never trusts the header.
"""

from __future__ import annotations

import ipaddress

from starlette.requests import Request

from app.core.config import get_settings


def _valid(value: str) -> str | None:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def resolve_client_ip(peer: str | None, forwarded_for: str | None, hops: int) -> str | None:
    if hops > 0 and forwarded_for:
        chain = [part for part in forwarded_for.split(",") if part.strip()]
        if len(chain) >= hops:
            candidate = _valid(chain[-hops])
            if candidate is not None:
                return candidate
    return peer


def client_ip(request: Request) -> str:
    cached = getattr(request.state, "client_ip", None)
    if isinstance(cached, str):
        return cached
    peer = request.client.host if request.client else None
    ip = resolve_client_ip(
        peer, request.headers.get("x-forwarded-for"), get_settings().trusted_proxy_hops
    )
    request.state.client_ip = ip or "unknown"
    return request.state.client_ip
