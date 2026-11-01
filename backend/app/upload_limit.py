"""Bound multipart bodies before Starlette can spool unbounded chunked uploads."""

import re

from starlette.responses import JSONResponse


class ImportBodyLimit:
    def __init__(self, app, max_bytes=11 * 1024 * 1024):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        avatar = scope["type"] == "http" and re.fullmatch(
            r"/api/users/[^/]+/avatar/?", scope["path"]
        )
        if scope["type"] != "http" or scope.get("method", "POST") not in (
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        ):
            return await self.app(scope, receive, send)
        path = scope["path"].rstrip("/")
        limit = (
            (2 * 1024 * 1024 + 128 * 1024)
            if avatar
            else (
                1152 * 1024
                if path == "/api/icons"
                else self.max_bytes
                if path == "/api/imports/splitwise/analyze"
                else 1024 * 1024
            )
        )
        headers = dict(scope.get("headers", []))
        try:
            oversized = int(headers.get(b"content-length", b"0")) > limit
        except ValueError:
            oversized = True
        if oversized:
            return await self.reject(scope, receive, send)
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > limit:
                return await self.reject(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)

    async def reject(self, scope, receive, send):
        response = JSONResponse({"detail": "Il file supera il limite consentito."}, status_code=413)
        await response(scope, receive, send)
