"""Desktop launcher: runs Marketing Decision OS on this computer and opens it in the browser.

Used by the ``mdos`` console command and by the packaged desktop executable. The server always binds to
127.0.0.1 in local mode, so nothing is reachable from other machines.

Each launch creates a random key. The browser receives it once, in the address fragment (never sent over the
network), to open a session; other accounts and programs on this computer do not know it. The browser is opened
through a small redirect file readable only by you, so the key never appears in the process list.
"""

from __future__ import annotations

import argparse
import html
import multiprocessing
import os
import secrets
import signal
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path


def _free_port(preferred: int, strict: bool = False) -> int:
    """Use the preferred port when it is free, otherwise any free port (unless strict)."""
    for port in (preferred,) if strict else (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if os.name != "nt":  # a port left in TIME_WAIT by a previous run is still usable (uvicorn does the same)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return int(sock.getsockname()[1])
    raise RuntimeError(f"Port {preferred} is already in use." if strict else "No free local port is available.")


def _write_launcher(folder: Path, open_url: str) -> Path:
    """A private (0600) HTML file that redirects to ``open_url``, so the key is not passed on a command line."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "open-mdos.html"
    target = html.escape(open_url, quote=True)
    page = (f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={target}">'
            f'<title>Opening Marketing Decision OS</title><p><a href="{target}">Open Marketing Decision OS</a></p>')
    path.unlink(missing_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(page)
    return path


def _open_when_ready(url: str, launcher: Path, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}api/health", timeout=2) as res:  # noqa: S310 - fixed loopback URL
                if res.status == 200:
                    webbrowser.open(launcher.as_uri())
                    return
        except OSError:
            time.sleep(0.4)


def _exit_on_signal(*_args: object) -> None:
    raise SystemExit(0)  # lets the launcher's clean-up run when MDOS is stopped or its terminal is closed


def main(argv: list[str] | None = None) -> None:
    if getattr(sys, "frozen", False):
        multiprocessing.freeze_support()  # required for worker processes in the packaged build on Windows
    parser = argparse.ArgumentParser(prog="mdos", description="Marketing Decision OS on this computer.")
    parser.add_argument("--port", type=int, default=int(os.environ.get("MDOS_PORT", "8765")),
                        help="Preferred local port (default 8765; another free port is used if it is busy).")
    parser.add_argument("--data-dir", help="Folder for the database and uploaded files (default: your user data folder).")
    parser.add_argument("--strict-port", action="store_true", help="Fail instead of choosing another port when the port is busy.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically.")
    args = parser.parse_args(argv)

    os.environ["MDOS_MODE"] = "local"  # the desktop build is always single-user and loopback-only
    os.environ["MDOS_ENV_FILE"] = ""  # never read a .env file from the folder MDOS was started in
    if args.data_dir:
        os.environ["MDOS_DATA_DIR"] = args.data_dir
    key = os.environ.get("MDOS_LOCAL_KEY") or secrets.token_urlsafe(32)  # set by tests; otherwise new per launch
    os.environ["MDOS_LOCAL_KEY"] = key

    import uvicorn

    from .config import get_settings
    from .main import create_app

    get_settings.cache_clear()
    settings = get_settings()
    port = _free_port(args.port, strict=args.strict_port)
    url = f"http://127.0.0.1:{port}/"
    open_url = f"{url}#key={key}"
    app = create_app()
    launcher = _write_launcher(settings.ensure_data_dir(), open_url)
    if not args.no_browser:
        threading.Thread(target=_open_when_ready, args=(url, launcher), daemon=True).start()
    print("Marketing Decision OS is running.")
    print(f"  Open this private link (it works until MDOS is closed): {open_url}")
    print(f"  Data folder: {settings.mdos_data_dir}")
    print("  Press Ctrl+C to stop.")
    # uvicorn stops gracefully on these signals, then re-raises them to the handler set here.
    for name in ("SIGTERM", "SIGHUP", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), _exit_on_signal)
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning", server_header=False)
    finally:
        launcher.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
