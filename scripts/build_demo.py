"""Assemble the live demo for GitHub Pages: the full MDOS app running in the browser with Pyodide.

Usage (from the repository root, after `npm run build:demo` in frontend/):
    python scripts/build_demo.py [--pyodide-archive PATH] [--out frontend/dist-demo]

Adds to the demo build:
  pyodide/            Pyodide's runtime and only the compiled packages MDOS needs (numpy, pandas, SciPy, statsmodels,
                      scikit-learn, SQLAlchemy, FastAPI, ...), taken from the official release archive. The archive
                      is checked against PYODIDE_SHA256 before anything is extracted.
  wheels/             The pure-Python packages Pyodide does not ship, downloaded from PyPI with pip in hash-checking
                      mode, using the hashes pinned in backend/requirements.txt.
  mdos.zip            The MDOS server package (backend/mdos) without the desktop launcher or the built frontend.
  demo-manifest.json  What the browser loads (read by frontend/src/demo/engine.worker.ts).

Nothing is fetched at run time from anywhere but the site itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess  # noqa: S404 - runs pip with fixed arguments
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYODIDE_VERSION = "314.0.7"
PYODIDE_URL = f"https://github.com/pyodide/pyodide/releases/download/{PYODIDE_VERSION}/pyodide-{PYODIDE_VERSION}.tar.bz2"
PYODIDE_SHA256 = "192b5864e6e6d30ab074861af800cb8b4acb0998ef0f9342c3367448aeb86645"
PYODIDE_RUNTIME = ["pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"]
# Compiled or Pyodide-provided packages MDOS imports; their dependencies are added from pyodide-lock.json.
PYODIDE_PACKAGES = ["fastapi", "pydantic", "sqlalchemy", "numpy", "pandas", "scipy", "statsmodels", "scikit-learn",
                    "argon2-cffi", "dnspython", "idna", "markupsafe"]
# Pure-Python packages from backend/requirements.txt that Pyodide does not ship.
EXTRA_WHEELS = ["alembic", "mako", "pydantic-settings", "python-dotenv", "python-multipart", "openpyxl", "et-xmlfile",
                "pyjwt", "email-validator", "defusedxml"]
APP_EXCLUDE = ("static/", "desktop.py")
ZIP_TIME = (2026, 1, 1, 0, 0, 0)  # fixed, so the same code gives the same mdos.zip


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_pyodide(cache: Path) -> Path:
    archive = cache / f"pyodide-{PYODIDE_VERSION}.tar.bz2"
    if not archive.exists() or sha256(archive) != PYODIDE_SHA256:
        print(f"Downloading {PYODIDE_URL}")
        with urllib.request.urlopen(PYODIDE_URL, timeout=600) as res, archive.open("wb") as out:  # noqa: S310 - fixed https URL
            shutil.copyfileobj(res, out)
    return archive


def package_closure(lock: dict, roots: list[str]) -> list[str]:
    packages = lock["packages"]
    seen: list[str] = []
    todo = list(roots)
    while todo:
        name = re.sub(r"[-_.]+", "-", todo.pop()).lower()  # lock names are normalized; depends lists may not be
        if name in seen:
            continue
        if name not in packages:
            raise SystemExit(f"Pyodide {PYODIDE_VERSION} has no package named {name}.")
        seen.append(name)
        todo.extend(packages[name].get("depends", []))
    return sorted(seen)


def add_pyodide(archive: Path, out: Path) -> list[str]:
    if sha256(archive) != PYODIDE_SHA256:
        raise SystemExit(f"{archive} does not match the pinned SHA-256 for Pyodide {PYODIDE_VERSION}.")
    target = out / "pyodide"
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:bz2") as tar:
        members = {m.name: m for m in tar.getmembers() if m.isfile()}

        def extract(name: str) -> Path:
            member = members.get(f"pyodide/{name}")
            if member is None or "/" in name or name.startswith("."):
                raise SystemExit(f"The Pyodide archive has no file named {name}.")
            dest = target / name
            with tar.extractfile(member) as src, dest.open("wb") as dst:  # type: ignore[union-attr]
                shutil.copyfileobj(src, dst)
            return dest

        for name in PYODIDE_RUNTIME:
            extract(name)
        lock = json.loads((target / "pyodide-lock.json").read_text())
        packages = package_closure(lock, PYODIDE_PACKAGES)
        for name in packages:
            entry = lock["packages"][name]
            dest = extract(entry["file_name"])
            if sha256(dest) != entry["sha256"]:
                raise SystemExit(f"{entry['file_name']} does not match its hash in pyodide-lock.json.")
    return packages


def pinned_requirements(names: list[str]) -> str:
    """The blocks of backend/requirements.txt (version and hashes) for the given packages."""
    text = (ROOT / "backend" / "requirements.txt").read_text()
    blocks = {}
    for block in re.split(r"\n(?=[a-z0-9])", text):
        name = block.split("==", 1)[0].strip().lower()
        if name in names:
            blocks[name] = "\n".join(line for line in block.splitlines() if not line.strip().startswith("#"))
    missing = sorted(set(names) - set(blocks))
    if missing:
        raise SystemExit(f"backend/requirements.txt does not pin {', '.join(missing)}.")
    return "\n".join(blocks[n] for n in names) + "\n"


def add_wheels(out: Path) -> list[str]:
    target = out / "wheels"
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        req = Path(tmp) / "requirements.txt"
        req.write_text(pinned_requirements(EXTRA_WHEELS))
        subprocess.run([sys.executable, "-m", "pip", "download", "--quiet", "--no-deps", "--require-hashes",  # noqa: S603
                        "--only-binary=:all:", "--platform", "any", "--implementation", "py",
                        "--python-version", "3.14", "--dest", str(target), "-r", str(req)], check=True)
    wheels = sorted(p.name for p in target.glob("*.whl"))
    if len(wheels) != len(EXTRA_WHEELS):
        raise SystemExit(f"Expected {len(EXTRA_WHEELS)} wheels, found {len(wheels)}: {wheels}")
    return wheels


def add_app(out: Path) -> str:
    source = ROOT / "backend" / "mdos"
    dest = out / "mdos.zip"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source.rglob("*")):
            rel = path.relative_to(source).as_posix()
            if not path.is_file() or "__pycache__" in rel or rel.endswith(".pyc") or rel.startswith(APP_EXCLUDE):
                continue
            info = zipfile.ZipInfo(f"mdos/{rel}", ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes())
    return dest.name


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pyodide-archive", type=Path, help="a local copy of the Pyodide release archive")
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache", help="where to keep the downloaded archive")
    parser.add_argument("--out", type=Path, default=ROOT / "frontend" / "dist-demo")
    args = parser.parse_args()
    if not (args.out / "index.html").exists():
        raise SystemExit(f"{args.out} has no index.html. Run `npm run build:demo` in frontend/ first.")
    for name in ("pyodide", "wheels"):
        shutil.rmtree(args.out / name, ignore_errors=True)
    args.cache.mkdir(parents=True, exist_ok=True)
    archive = args.pyodide_archive or fetch_pyodide(args.cache)
    manifest = {
        "pyodide": "pyodide/",
        "packages": add_pyodide(archive, args.out),
        "wheels": add_wheels(args.out),
        "app": add_app(args.out),
    }
    (args.out / "demo-manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    size = sum(p.stat().st_size for p in args.out.rglob("*") if p.is_file())
    print(f"Demo ready in {args.out}: {len(manifest['packages'])} Pyodide packages, "
          f"{len(manifest['wheels'])} extra wheels, {size / 1e6:.0f} MB in total.")


if __name__ == "__main__":
    main()
