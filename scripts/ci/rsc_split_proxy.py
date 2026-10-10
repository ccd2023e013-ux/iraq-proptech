"""Same-site HTTP proxy that streams chosen RSC responses in two timed parts.

Used by the draw-area browser checks (issue #4). The App Router's soft
navigation reads React Server Component (RSC) payloads as a stream; how the
bytes are split over time decides which router/React code path runs. Playwright
routing can only fulfil a response in one piece, so this proxy sits in front of
the frontend and, for requests matching ``match`` (default: polygon RSC
fetches), sends the first part of the upstream body, waits ``gap_ms``, then
sends the rest. Every other request is passed through unchanged (buffered).

    python scripts/ci/rsc_split_proxy.py --upstream http://localhost:3000 --port 3100

The split point and gap can be changed at runtime, without restarting, by
``GET /__split?at=<mode>&gap=<ms>`` where mode is ``root`` (right after the
root ``0:`` row), ``off`` (no split), or a fraction like ``0.5``.
"""

from __future__ import annotations

import argparse
import http.client
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "content-encoding",
    "server",
    "date",
}

STATE = {"at": "root", "gap": 200, "hits": 0}
LOCK = threading.Lock()


def split_index(body: bytes, mode: str) -> int | None:
    if mode == "off" or not body:
        return None
    if mode == "root":
        # End of the root row ("0:{...}\n"): the router can act on the response
        # while the rows it references are still on the way.
        start = body.find(b"\n0:")
        start = 0 if body.startswith(b"0:") else (start + 1 if start >= 0 else -1)
        if start < 0:
            return None
        end = body.find(b"\n", start)
        return None if end < 0 else end + 1
    try:
        frac = float(mode)
    except ValueError:
        return None
    i = int(len(body) * frac)
    return i if 0 < i < len(body) else None


def make_handler(upstream: str, match: str):
    up = urlsplit(upstream)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):  # quiet
            pass

        def _proxy(self) -> None:
            if self.path.startswith("/__split"):
                q = parse_qs(urlsplit(self.path).query)
                with LOCK:
                    if "at" in q:
                        STATE["at"] = q["at"][0]
                    if "gap" in q:
                        STATE["gap"] = int(q["gap"][0])
                    if q.get("reset"):
                        STATE["hits"] = 0
                    payload = repr(STATE).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            length = int(self.headers.get("Content-Length") or 0)
            data = self.rfile.read(length) if length else None
            headers = {
                k: v
                for k, v in self.headers.items()
                if k.lower() not in HOP and k.lower() not in ("host", "accept-encoding")
            }
            # Keep the browser's Host so the app's same-origin checks and any
            # absolute URLs it builds refer to the proxy's origin.
            headers["Host"] = self.headers.get("Host") or up.netloc
            conn = http.client.HTTPConnection(up.hostname, up.port or 80, timeout=120)
            try:
                conn.request(self.command, self.path, body=data, headers=headers)
                resp = conn.getresponse()
                body = resp.read()
            finally:
                conn.close()
            target = match in self.path and "_rsc=" in self.path
            with LOCK:
                at, gap = STATE["at"], STATE["gap"]
                if target:
                    STATE["hits"] += 1
            cut = split_index(body, at) if target else None
            self.send_response(resp.status, resp.reason)
            for k, v in resp.getheaders():
                if k.lower() not in HOP:
                    self.send_header(k, v)
            if cut is None:
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)
                return
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("X-Split", f"{at}@{cut}/{len(body)}+{gap}ms")
            self.end_headers()
            for part, pause in ((body[:cut], gap), (body[cut:], 0)):
                self.wfile.write(f"{len(part):x}\r\n".encode() + part + b"\r\n")
                self.wfile.flush()
                if pause:
                    time.sleep(pause / 1000)
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()

        do_GET = do_POST = do_HEAD = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = _proxy

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", default="http://localhost:3000")
    ap.add_argument("--port", type=int, default=3100)
    ap.add_argument("--match", default="polygon=")
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.upstream, args.match))
    server.daemon_threads = True
    server.serve_forever()


if __name__ == "__main__":
    main()
