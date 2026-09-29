"""Desktop launcher: runs Marketing Decision OS on this computer and opens it in the browser.

Used by the ``mdos`` console command and by the packaged desktop executable. The server always binds to
127.0.0.1 in local mode, so nothing is reachable from other machines.
"""

from __future__ import annotations

import argparse
import multiprocessing
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser


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


def _open_when_ready(url: str, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}api/health", timeout=2) as res:  # noqa: S310 - fixed loopback URL
                if res.status == 200:
                    webbrowser.open(url)
                    return
        except OSError:
            time.sleep(0.4)


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
    if args.data_dir:
        os.environ["MDOS_DATA_DIR"] = args.data_dir

    import uvicorn

    from .config import get_settings
    from .main import create_app

    get_settings.cache_clear()
    settings = get_settings()
    port = _free_port(args.port, strict=args.strict_port)
    url = f"http://127.0.0.1:{port}/"
    app = create_app()
    if not args.no_browser:
        threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()
    print("Marketing Decision OS is running.")
    print(f"  Open: {url}")
    print(f"  Data folder: {settings.mdos_data_dir}")
    print("  Press Ctrl+C to stop.")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
