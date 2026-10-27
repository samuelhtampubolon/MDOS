"""Build the desktop executable for the current operating system.

Usage (from the repository root, with the backend virtual environment active):
    pip install -e "backend[desktop]"
    python scripts/build_desktop.py

Steps: build the React frontend into backend/mdos/static, then run PyInstaller with packaging/mdos.spec.
The result is dist/MDOS/ (run MDOS or MDOS.exe inside it) plus a zip archive for distribution.
"""

from __future__ import annotations

import platform
import shutil
import subprocess  # noqa: S404 - build script runs trusted local tools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path) -> None:
    """Run a fixed command without a shell. npm is npm.cmd on Windows, so resolve the program's full path first."""
    program = shutil.which(cmd[0])
    if program is None:
        raise SystemExit(f"{cmd[0]} was not found. Install it and try again.")
    print("+", " ".join(cmd))
    subprocess.run([program, *cmd[1:]], cwd=cwd, check=True)  # noqa: S603


def main() -> None:
    frontend = ROOT / "frontend"
    if "--skip-frontend" not in sys.argv:
        run(["npm", "ci", "--ignore-scripts"], frontend)  # exact lockfile versions; package scripts never run
        run(["npm", "run", "build"], frontend)
    run([sys.executable, "-m", "PyInstaller", str(ROOT / "packaging" / "mdos.spec"), "--noconfirm", "--clean",
         "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build" / "pyinstaller")], ROOT)
    system = {"Darwin": "macos", "Windows": "windows"}.get(platform.system(), "linux")
    archive = shutil.make_archive(str(ROOT / "dist" / f"MDOS-{system}-{platform.machine().lower()}"), "zip",
                                  ROOT / "dist", "MDOS")
    print(f"Built {archive}")


if __name__ == "__main__":
    main()
