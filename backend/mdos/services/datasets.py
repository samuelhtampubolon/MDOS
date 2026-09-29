"""Dataset ingestion, versioning and cleaning (the lineage chain's capture, normalize and transform steps)."""

from __future__ import annotations

import csv
import io
import re
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, storage
from ..analytics import cleaning, quality
from ..analytics.common import AnalysisError
from ..analytics.profiling import profile_column
from ..config import get_settings
from ..errors import NotFound, ValidationFailed
from ..jsonutil import to_jsonable
from ..models import Dataset, DatasetVersion, Project, Variable

ALLOWED_SUFFIXES = {".csv", ".tsv", ".txt", ".xlsx"}


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationFailed("Could not decode the file. Save it as UTF-8 CSV.")


def parse_upload(filename: str, raw: bytes) -> tuple[pd.DataFrame, str]:
    settings = get_settings()
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise ValidationFailed(f"File is larger than {settings.max_upload_mb} MB.")
    suffix = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if suffix not in ALLOWED_SUFFIXES:
        raise ValidationFailed("Upload a CSV, TSV or XLSX file.")
    try:
        if suffix == ".xlsx":
            # openpyxl uses defusedxml when installed, which protects against XML entity attacks.
            df = pd.read_excel(io.BytesIO(raw), engine="openpyxl", sheet_name=0, dtype=object)
            fmt = "xlsx"
        else:
            text = _decode(raw)
            sample = text[:65536]
            try:
                delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
            except csv.Error:
                delimiter = "\t" if suffix == ".tsv" else ","
            df = pd.read_csv(io.StringIO(text), sep=delimiter, dtype=str, keep_default_na=True, skipinitialspace=True)
            fmt = "csv"
    except ValidationFailed:
        raise
    except Exception as exc:  # noqa: BLE001 - surface a clean message for any parser failure
        raise ValidationFailed(f"Could not read the file: {exc}") from exc
    if df.empty:
        raise ValidationFailed("The file has no data rows.")
    if len(df) > settings.max_rows or df.shape[1] > settings.max_cols:
        raise ValidationFailed(f"The file exceeds {settings.max_rows} rows or {settings.max_cols} columns.")
    df = normalize_columns(df)
    df = coerce_types(df)
    return df, fmt


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    seen: dict[str, int] = {}
    names = []
    for i, col in enumerate(df.columns):
        name = re.sub(r"\s+", "_", str(col).strip())
        name = re.sub(r"[^\w\-.]", "", name, flags=re.UNICODE) or f"column_{i + 1}"
        if name.lower().startswith("unnamed"):
            name = f"column_{i + 1}"
        count = seen.get(name.lower(), 0)
        seen[name.lower()] = count + 1
        names.append(name if count == 0 else f"{name}_{count + 1}")
    out = df.copy()
    out.columns = names
    return out.dropna(how="all")


def coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Turn numeric-looking text columns into numbers; strip whitespace in text columns."""
    out = df.copy()
    for col in out.columns:
        series = out[col]
        if pd.api.types.is_numeric_dtype(series):
            continue
        stripped = series.map(lambda v: v.strip() if isinstance(v, str) else v)
        stripped = stripped.mask(stripped.astype(str).isin(["", "nan", "None"]) & stripped.notna() | stripped.isna())
        numeric = pd.to_numeric(stripped, errors="coerce")
        non_null = stripped.notna().sum()
        if non_null and numeric.notna().sum() / non_null >= 0.98:
            out[col] = numeric
        else:
            out[col] = stripped
    return out


def project_variable_meta(db: Session, project_id: str) -> dict[str, Variable]:
    return {v.name: v for v in db.scalars(select(Variable).where(Variable.project_id == project_id)).all()}


def column_types_for(version: DatasetVersion, variables: dict[str, Variable]) -> dict[str, str]:
    types = {c["name"]: c.get("type") or c.get("inferred_type") for c in version.columns}
    for name, var in variables.items():
        if name in types and var.var_type in ("likert", "numeric", "binary", "categorical", "text", "price", "id", "datetime"):
            types[name] = var.var_type
    return types


def labels_for(variables: dict[str, Variable]) -> dict[str, str]:
    out = {}
    for name, var in variables.items():
        if var.construct_id and name.isupper():
            out[name] = var.label.replace(" (mean score)", "") if var.label else name
        elif var.label and len(var.label) <= 60:
            out[name] = var.label
    return out


def _profile_and_check(df: pd.DataFrame, variables: dict[str, Variable]) -> tuple[list[dict], dict]:
    columns = []
    for col in df.columns:
        prof = profile_column(df[col], col)
        var = variables.get(col)
        if var is not None:
            prof["variable_id"] = var.id
            prof["type"] = var.var_type if var.var_type != "other" else prof["inferred_type"]
            prof["role"] = var.role
        columns.append(prof)
    types = {c["name"]: c.get("type") or c["inferred_type"] for c in columns}
    scales = {n: (v.scale_min, v.scale_max) for n, v in variables.items()
              if v.var_type == "likert" and v.scale_min is not None and v.scale_max is not None and n in df.columns}
    attention = {n: v.value_labels.get("expected") for n, v in variables.items()
                 if n in df.columns and isinstance(v.value_labels, dict) and v.value_labels.get("expected") is not None}
    report = quality.diagnose(df, types, scales, attention)
    return columns, report


def create_dataset(db: Session, project: Project, *, name: str, kind: str, origin: str, filename: str, df: pd.DataFrame,
                   fmt: str, user_id: str, description: str = "", source_run_id: str | None = None) -> Dataset:
    if kind not in ("survey", "reviews", "sales", "web_analytics", "experiment", "other"):
        raise ValidationFailed("Unknown dataset kind.")
    if origin not in ("user_data", "external", "synthetic_demo"):
        raise ValidationFailed("Unknown data origin.")
    variables = project_variable_meta(db, project.id)
    columns, report = _profile_and_check(df, variables)
    key, checksum = storage.save_frame(df, project.org_id, project.id)
    dataset = Dataset(project_id=project.id, name=name, kind=kind, origin=origin, description=description, created_by=user_id)
    db.add(dataset)
    db.flush()
    version = DatasetVersion(dataset_id=dataset.id, project_id=project.id, version=1, storage_key=key,
                             original_filename=filename[:300], file_format=fmt, n_rows=len(df), n_cols=df.shape[1],
                             columns=to_jsonable(columns), quality=report, checksum=checksum, created_by=user_id,
                             operations=[{"op": "import", "file": filename[:300], "format": fmt, "rows": len(df),
                                          "cols": int(df.shape[1])}], source_run_id=source_run_id)
    db.add(version)
    db.flush()
    dataset.current_version_id = version.id
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type="user", actor_id=user_id,
                 action="dataset.import", entity_type="dataset", entity_id=dataset.id,
                 details={"rows": len(df), "cols": int(df.shape[1]), "checksum": checksum, "origin": origin})
    return dataset


def get_version(db: Session, project_id: str, version_id: str) -> DatasetVersion:
    version = db.get(DatasetVersion, version_id)
    if not version or version.project_id != project_id:
        raise NotFound("Dataset version not found.")
    return version


def current_version(db: Session, dataset: Dataset) -> DatasetVersion:
    if not dataset.current_version_id:
        raise NotFound("Dataset has no version.")
    version = db.get(DatasetVersion, dataset.current_version_id)
    if not version:
        raise NotFound("Dataset has no version.")
    return version


def load_version(version: DatasetVersion) -> pd.DataFrame:
    df = storage.load_frame(version.storage_key)
    text_like = {c["name"] for c in version.columns
                 if (c.get("type") or c.get("inferred_type")) in ("categorical", "text", "id", "binary", "datetime")}
    for col in df.columns:
        if col in text_like and not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].astype("object").where(df[col].notna())
    return df


def preview(version: DatasetVersion, limit: int = 50) -> dict[str, Any]:
    df = load_version(version)
    return {"columns": list(df.columns), "rows": to_jsonable(df.head(max(1, min(limit, 500))).to_dict(orient="records")),
            "n_rows": len(df)}


def derive_version(db: Session, project: Project, parent: DatasetVersion, operations: list[dict[str, Any]], *,
                   user_id: str, approved_by: str | None, source_run_id: str | None = None) -> DatasetVersion:
    """Apply operations to ``parent`` and store the result as the next version (lineage preserved)."""
    df = load_version(parent)
    try:
        new_df, log = cleaning.apply_operations(df, operations)
    except AnalysisError as exc:
        raise ValidationFailed(str(exc)) from exc
    variables = project_variable_meta(db, project.id)
    columns, report = _profile_and_check(new_df, variables)
    key, checksum = storage.save_frame(new_df, project.org_id, project.id)
    dataset = db.get(Dataset, parent.dataset_id)
    latest = max(v.version for v in dataset.versions)
    version = DatasetVersion(dataset_id=dataset.id, project_id=project.id, version=latest + 1, parent_id=parent.id,
                             storage_key=key, original_filename=parent.original_filename, file_format="csv",
                             n_rows=len(new_df), n_cols=new_df.shape[1], columns=to_jsonable(columns), quality=report,
                             checksum=checksum, created_by=user_id, approved_by=approved_by, operations=log,
                             source_run_id=source_run_id)
    db.add(version)
    db.flush()
    dataset.current_version_id = version.id
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type="user", actor_id=user_id,
                 action="dataset.version.create", entity_type="dataset_version", entity_id=version.id,
                 details={"parent": parent.id, "operations": [o["op"] for o in operations], "rows": len(new_df),
                          "checksum": checksum})
    return version


def construct_scale_operations(db: Session, project_id: str, df_columns: list[str]) -> list[dict[str, Any]]:
    """compute_scale operations for every construct whose items are present and whose score is missing."""
    from ..models import Construct

    ops = []
    variables = project_variable_meta(db, project_id)
    for construct in db.scalars(select(Construct).where(Construct.project_id == project_id)).all():
        items = sorted(n for n, v in variables.items() if v.construct_id == construct.id and n != construct.code and n in df_columns)
        if len(items) >= 2 and construct.code not in df_columns:
            ops.append({"op": "compute_scale", "name": construct.code, "items": items, "min_items": max(1, len(items) - 1)})
    return ops
