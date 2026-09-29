"""File storage for dataset versions.

Files are stored under generated keys (``<org>/<project>/<uuid>.csv``); user-supplied file names are
kept only as metadata and never used to build paths.
"""

from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path

import pandas as pd

from .config import get_settings
from .errors import NotFound


def _root() -> Path:
    root = get_settings().storage_dir
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_path(key: str) -> Path:
    root = _root().resolve()
    path = (root / key).resolve()
    if root not in path.parents:
        raise NotFound("File not found.")
    return path


def new_key(org_id: str, project_id: str, suffix: str = ".csv") -> str:
    return f"{org_id}/{project_id}/{uuid.uuid4().hex}{suffix}"


def save_frame(df: pd.DataFrame, org_id: str, project_id: str) -> tuple[str, str]:
    """Persist a normalized dataframe as UTF-8 CSV. Returns (storage_key, sha256)."""
    key = new_key(org_id, project_id)
    path = _safe_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    return key, sha256_file(path)


def load_frame(key: str) -> pd.DataFrame:
    path = _safe_path(key)
    if not path.exists():
        raise NotFound("Stored dataset file is missing.")
    return pd.read_csv(path, encoding="utf-8", low_memory=False)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def delete_key(key: str) -> None:
    try:
        path = _safe_path(key)
    except NotFound:
        return
    path.unlink(missing_ok=True)


def delete_project_files(org_id: str, project_id: str) -> None:
    folder = _safe_path(f"{org_id}/{project_id}")
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)
