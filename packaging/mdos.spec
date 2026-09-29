# PyInstaller spec for the Marketing Decision OS desktop build.
# Build from the repository root after building the frontend:
#   pyinstaller packaging/mdos.spec --noconfirm --clean
# Output: dist/MDOS/ (a folder with the MDOS executable). Zip that folder to distribute it.

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821 - SPECPATH is provided by PyInstaller
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))  # make the mdos package importable for collect_submodules

if not (BACKEND / "mdos" / "static" / "index.html").exists():
    raise SystemExit("Build the frontend first: cd frontend && npm ci && npm run build")


def tree(sub: str) -> list[tuple[str, str]]:
    """Ship a folder of the mdos package as data (the built UI, migrations and demo data)."""
    base = BACKEND / "mdos" / sub
    return [(str(f), str(Path("mdos") / sub / f.relative_to(base).parent))
            for f in base.rglob("*") if f.is_file() and "__pycache__" not in f.parts]


datas = tree("static") + tree("migrations") + tree("demo_data")
hiddenimports = (
    collect_submodules("mdos")
    + collect_submodules("uvicorn")
    + ["sqlalchemy.dialects.sqlite", "email_validator", "multipart", "python_multipart", "argon2", "_cffi_backend"]
)

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(BACKEND)],
    datas=datas,
    hiddenimports=hiddenimports,
    # The desktop app uses SQLite: leave out the PostgreSQL driver and GUI or notebook toolkits.
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "notebook", "PyQt5", "PySide6", "psycopg", "psycopg_binary"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MDOS",
    console=True,  # the window shows the local address and closing it stops the app
    icon=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="MDOS")
