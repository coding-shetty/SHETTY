"""Small same-origin/session boundary, not network-user authentication."""
from __future__ import annotations

import asyncio
import hmac
from urllib.parse import urlsplit

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse

MAX_BODY_BYTES = 128 * 1024


class LocalSecurityMiddleware:
    def __init__(self, app, *, token: str, preview: bool):
        self.app = app
        self.token = token.encode("utf-8")
        self.preview = preview

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        api = scope["path"].startswith("/api/")

        async def secured_send(message):
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Content-Type-Options"] = "nosniff"
                response_headers["Referrer-Policy"] = "no-referrer"
                response_headers["Cache-Control"] = "no-store" if api else "no-cache"
                csp = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'"
                if not self.preview:
                    csp += "; frame-ancestors 'none'"
                response_headers["Content-Security-Policy"] = csp
                response_headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            await send(message)

        async def fail(detail, status=403):
            await JSONResponse({"detail": detail}, status_code=status)(scope, receive, secured_send)

        host = headers.get("host", "")
        try:
            parts = urlsplit("//" + host)
            hostname = parts.hostname
            valid_host = not parts.username and not parts.password and parts.path in {"", "/"}
        except ValueError:
            hostname, valid_host = None, False
        allowed = hostname in {"localhost", "127.0.0.1", "::1"}
        if self.preview and hostname and hostname.endswith(".e2b.app"):
            allowed = True
        if not valid_host or not allowed:
            await fail("Host not allowed. Use the local address shown by SHETTY.")
            return
        if api:
            if headers.get("sec-fetch-site") == "cross-site":
                await fail("Cross-site API requests are blocked.")
                return
            origin = headers.get("origin")
            if origin:
                try:
                    origin_parts = urlsplit(origin)
                    same_origin = origin_parts.scheme in {"http", "https"} and origin_parts.netloc.lower() == host.lower()
                except ValueError:
                    same_origin = False
                if not same_origin:
                    await fail("Cross-origin API requests are blocked.")
                    return
            if scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
                supplied = headers.get("x-shetty-token", "").encode("utf-8")
                if not hmac.compare_digest(supplied, self.token):
                    await fail("Session check failed. Refresh SHETTY and try again.")
                    return
                try:
                    length = int(headers.get("content-length", "0"))
                except ValueError:
                    await fail("Invalid request length.", 400)
                    return
                if length < 0 or length > MAX_BODY_BYTES:
                    await fail("Request is too large.", 413)
                    return
                # Count actual bytes as well as Content-Length, including chunked
                # bodies. Buffer only this bounded JSON input, before the parser.
                body = bytearray()
                while True:
                    try:
                        message = await asyncio.wait_for(receive(), timeout=10)
                    except asyncio.TimeoutError:
                        await fail("Request body timed out.", 408)
                        return
                    if message["type"] == "http.disconnect":
                        return
                    body.extend(message.get("body", b""))
                    if len(body) > MAX_BODY_BYTES:
                        await fail("Request is too large.", 413)
                        return
                    if not message.get("more_body", False):
                        break
                supplied_body = False

                async def replay_body():
                    nonlocal supplied_body
                    if not supplied_body:
                        supplied_body = True
                        return {"type": "http.request", "body": bytes(body), "more_body": False}
                    return await receive()

                await self.app(scope, replay_body, secured_send)
                return
        await self.app(scope, receive, secured_send)
