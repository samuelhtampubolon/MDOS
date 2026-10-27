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

from mdos import __version__ as VERSION  # noqa: E402 - importable once backend is on sys.path

COPYRIGHT = "Copyright \u00a9 2026 Samuel Hasudungan Tampubolon. Released under the MIT License."


def windows_version_file() -> str:
    """Write the Windows file properties (Properties, Details): product, version and copyright."""
    numbers = tuple(int(n) for n in VERSION.split(".")[:3]) + (0,)
    strings = {
        "CompanyName": "Samuel Hasudungan Tampubolon",
        "FileDescription": "MDOS, Marketing Decision OS",
        "FileVersion": VERSION,
        "InternalName": "MDOS",
        "LegalCopyright": COPYRIGHT,
        "OriginalFilename": "MDOS.exe",
        "ProductName": "MDOS, Marketing Decision OS",
        "ProductVersion": VERSION,
    }
    table = ", ".join(f"StringStruct({ascii(k)}, {ascii(v)})" for k, v in strings.items())
    text = (
        f"VSVersionInfo(ffi=FixedFileInfo(filevers={numbers}, prodvers={numbers}, mask=0x3f, flags=0x0, "
        f"OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)), kids=["
        f"StringFileInfo([StringTable('040904B0', [{table}])]), "
        f"VarFileInfo([VarStruct('Translation', [1033, 1200])])])\n"
    )
    path = Path(workpath) / "version_info.txt"  # noqa: F821 - workpath is provided by PyInstaller
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")
    return str(path)


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
    version=windows_version_file(),  # used on Windows only
)
coll = COLLECT(exe, a.binaries, a.datas, name="MDOS")
