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
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True, shell=sys.platform == "win32")  # noqa: S603


def main() -> None:
    frontend = ROOT / "frontend"
    if "--skip-frontend" not in sys.argv:
        run(["npm", "ci"], frontend)
        run(["npm", "run", "build"], frontend)
    run([sys.executable, "-m", "PyInstaller", str(ROOT / "packaging" / "mdos.spec"), "--noconfirm", "--clean",
         "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build" / "pyinstaller")], ROOT)
    system = {"Darwin": "macos", "Windows": "windows"}.get(platform.system(), "linux")
    archive = shutil.make_archive(str(ROOT / "dist" / f"MDOS-{system}-{platform.machine().lower()}"), "zip",
                                  ROOT / "dist", "MDOS")
    print(f"Built {archive}")


if __name__ == "__main__":
    main()
