"""Request body size limits, enforced before and while the body streams in.

A declared ``Content-Length`` above the limit is refused at once. Bodies without one (chunked uploads) are
counted as they arrive, so an oversized request never fills memory or the temporary folder.
"""

from __future__ import annotations

import json

from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MB = 1024 * 1024


def _message(limit: int) -> str:
    return f"The request is larger than {max(1, limit // MB)} MB."


class BodyTooLarge(HTTPException):
    def __init__(self, limit: int) -> None:
        super().__init__(status_code=413, detail=_message(limit))


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, *, json_limit: int, upload_limit: int) -> None:
        self.app = app
        self.json_limit = json_limit
        self.upload_limit = upload_limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_type = headers.get(b"content-type", b"").decode("latin-1").lower()
        limit = self.upload_limit if content_type.startswith("multipart/form-data") else self.json_limit
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                too_large = int(declared) > limit
            except ValueError:
                too_large = True
            if too_large:
                await _reject(send, limit)
                return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise BodyTooLarge(limit)
            return message

        await self.app(scope, limited_receive, send)


async def _reject(send: Send, limit: int) -> None:
    body = json.dumps({"error": {"code": "too_large", "message": _message(limit), "details": {}}}).encode()
    await send({"type": "http.response.start", "status": 413,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})
