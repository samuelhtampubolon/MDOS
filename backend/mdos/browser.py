"""In-browser engine for the live demo on GitHub Pages.

The demo runs this same FastAPI application inside the visitor's browser with Pyodide (Python compiled to
WebAssembly). The page hands every ``/api`` request to :func:`handle`, which calls the ASGI app directly: there is no
server, no network listener and nothing leaves the browser. Pyodide has no threads, so agents run in-line
(``EXECUTION_MODE=sync``) and the thread hand-off that FastAPI and Starlette use for plain functions runs in-line too.

The session cookie lives in :class:`CookieJar` because responses built by the page never reach the browser's own
cookie store. It holds only this engine's cookies and only for its lifetime.
"""

from __future__ import annotations

import os
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any

_engine: Engine | None = None


class CookieJar:
    """Name to value for cookies the app sets. Every cookie is sent back on every request (one site, path ``/``)."""

    def __init__(self) -> None:
        self.cookies: dict[str, str] = {}

    def header(self) -> str:
        return "; ".join(f"{name}={value}" for name, value in self.cookies.items())

    def update(self, set_cookie: str) -> None:
        parsed = SimpleCookie()
        parsed.load(set_cookie)
        for name, morsel in parsed.items():
            expired = morsel["max-age"] in ("0", "-1") or morsel.value in ("", '""')
            if expired:
                self.cookies.pop(name, None)
            else:
                self.cookies[name] = morsel.value


def _run_inline() -> None:
    """Make anyio's thread hand-off call the function directly; Pyodide cannot start threads."""
    import anyio.to_thread

    async def run_sync(func: Any, *args: Any, abandon_on_cancel: bool = False, cancellable: Any = None,
                       limiter: Any = None) -> Any:
        return func(*args)

    anyio.to_thread.run_sync = run_sync


class Engine:
    def __init__(self, data_dir: str) -> None:
        os.environ.update({
            "MDOS_MODE": "local",
            "MDOS_DATA_DIR": data_dir,
            "EXECUTION_MODE": "sync",
        })
        for name in ("ANTHROPIC_API_KEY", "DATABASE_URL", "MDOS_LOCAL_KEY"):
            os.environ.pop(name, None)  # offline drafting, the local SQLite file, no launch key
        _run_inline()
        from mdos.config import get_settings
        from mdos.main import create_app

        get_settings.cache_clear()
        self.app = create_app()
        self.jar = CookieJar()
        self._lifespan: Any = None

    async def start(self) -> None:
        self._lifespan = self.app.router.lifespan_context(self.app)
        await self._lifespan.__aenter__()

    async def stop(self) -> None:
        if self._lifespan is not None:
            await self._lifespan.__aexit__(None, None, None)
            self._lifespan = None

    async def handle(self, method: str, path: str, query: str, headers: list[list[str]], body: bytes) -> dict:
        if not path.startswith("/api/"):
            return {"status": 404, "headers": [["content-type", "application/json"]],
                    "body": b'{"error": {"code": "not_found", "message": "Not found."}}'}
        raw_headers = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers
                       if k.lower() not in ("host", "cookie", "content-length")]
        raw_headers += [(b"host", b"localhost"), (b"content-length", str(len(body)).encode())]
        if self.jar.cookies:
            raw_headers.append((b"cookie", self.jar.header().encode("latin-1")))
        scope = {
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"}, "http_version": "1.1",
            "method": method.upper(), "scheme": "http", "path": path, "raw_path": path.encode(), "root_path": "",
            "query_string": query.encode("latin-1"), "headers": raw_headers,
            "server": ("localhost", 80), "client": ("127.0.0.1", 0),
        }
        pending = [{"type": "http.request", "body": body, "more_body": False}]

        async def receive() -> dict:
            return pending.pop() if pending else {"type": "http.disconnect"}

        response: dict = {"status": 500, "headers": [], "body": bytearray()}

        async def send(message: dict) -> None:
            if message["type"] == "http.response.start":
                response["status"] = message["status"]
                for k, v in message.get("headers", []):
                    name, value = k.decode("latin-1"), v.decode("latin-1")
                    if name.lower() == "set-cookie":
                        self.jar.update(value)
                    else:
                        response["headers"].append([name, value])
            elif message["type"] == "http.response.body":
                response["body"] += message.get("body", b"")

        await self.app(scope, receive, send)
        response["body"] = bytes(response["body"])
        return response


async def boot(data_dir: str) -> None:
    """Create the engine once per page: migrations run on the SQLite file in ``data_dir``."""
    global _engine
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    if _engine is None:
        _engine = Engine(data_dir)
        await _engine.start()


async def handle(method: str, path: str, query: str, headers: list[list[str]], body: bytes) -> dict:
    if _engine is None:
        raise RuntimeError("Call boot() first.")
    return await _engine.handle(method, path, query, headers, body)
