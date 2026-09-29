"""Apply an approved cleaning plan to a dataframe and record exactly what changed (lineage)."""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
import pandas as pd

from ..jsonutil import to_jsonable
from .common import AnalysisError

ALLOWED_OPS = {
    "drop_duplicates",
    "drop_rows",
    "drop_columns",
    "pseudonymize",
    "set_out_of_range_missing",
    "recode",
    "trim_text",
    "winsorize",
    "compute_scale",
    "reverse_code",
}


def validate_operations(operations: list[dict[str, Any]]) -> None:
    for i, op in enumerate(operations):
        name = op.get("op")
        if name not in ALLOWED_OPS:
            raise AnalysisError(f"Operation {i + 1}: unknown operation '{name}'.")


def apply_operations(df: pd.DataFrame, operations: list[dict[str, Any]]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Apply operations in order. Row references use positions in the *input* dataframe."""
    validate_operations(operations)
    out = df.copy()
    out["__row"] = np.arange(len(out))
    log: list[dict[str, Any]] = []
    for op in operations:
        rows_before, cols_before = len(out), out.shape[1] - 1
        name = op["op"]
        affected: Any = None
        if name == "drop_duplicates":
            subset = [c for c in out.columns if c != "__row"]
            mask = out.duplicated(subset=subset, keep="first")
            affected = int(mask.sum())
            out = out[~mask]
        elif name == "drop_rows":
            rows = {int(r) for r in op.get("rows", [])}
            mask = out["__row"].isin(rows)
            affected = int(mask.sum())
            out = out[~mask]
        elif name == "drop_columns":
            cols = [c for c in op.get("columns", []) if c in out.columns and c != "__row"]
            out = out.drop(columns=cols)
            affected = cols
        elif name == "pseudonymize":
            cols = [c for c in op.get("columns", []) if c in out.columns]
            salt = str(op.get("salt", "mdos"))
            for col in cols:
                out[col] = out[col].map(
                    lambda v, s=salt: None if pd.isna(v) else hashlib.sha256(f"{s}:{v}".encode()).hexdigest()[:12]
                )
            affected = cols
        elif name == "set_out_of_range_missing":
            col = _col(out, op)
            values = pd.to_numeric(out[col], errors="coerce")
            bad = (values < float(op["min"])) | (values > float(op["max"]))
            affected = int(bad.sum())
            out[col] = values.where(~bad)
        elif name == "recode":
            col = _col(out, op)
            mapping = {str(k): v for k, v in (op.get("mapping") or {}).items()}
            before = out[col].copy()
            out[col] = out[col].map(lambda v, m=mapping: m.get(str(v), v) if not pd.isna(v) else v)
            affected = int((before.astype(str) != out[col].astype(str)).sum())
        elif name == "trim_text":
            cols = [c for c in op.get("columns", []) if c in out.columns]
            for col in cols:
                out[col] = out[col].map(lambda v: v.strip() if isinstance(v, str) else v)
            affected = cols
        elif name == "winsorize":
            col = _col(out, op)
            values = pd.to_numeric(out[col], errors="coerce")
            lo, hi = values.quantile(float(op.get("lower", 0.01))), values.quantile(float(op.get("upper", 0.99)))
            clipped = values.clip(lo, hi)
            affected = int(((values != clipped) & values.notna()).sum())
            out[col] = clipped
        elif name == "reverse_code":
            col = _col(out, op)
            values = pd.to_numeric(out[col], errors="coerce")
            out[col] = float(op["min"]) + float(op["max"]) - values
            affected = int(values.notna().sum())
        elif name == "compute_scale":
            items = [c for c in op.get("items", []) if c in out.columns]
            if len(items) < 2:
                raise AnalysisError("compute_scale needs at least two existing item columns.")
            target = str(op.get("name") or "scale")
            block = out[items].apply(pd.to_numeric, errors="coerce")
            min_items = int(op.get("min_items", max(1, len(items) - 1)))
            score = block.mean(axis=1).where(block.notna().sum(axis=1) >= min_items)
            out[target] = score
            affected = {"name": target, "items": items, "min_items": min_items}
        log.append(
            to_jsonable(
                {
                    "op": name,
                    "params": {k: v for k, v in op.items() if k != "op" and k != "rows"},
                    "row_count": len(op.get("rows", [])) if "rows" in op else None,
                    "rows_before": rows_before,
                    "rows_after": len(out),
                    "cols_before": cols_before,
                    "cols_after": out.shape[1] - 1,
                    "affected": affected,
                    "reason": op.get("reason", ""),
                }
            )
        )
    return out.drop(columns=["__row"]).reset_index(drop=True), log


def _col(df: pd.DataFrame, op: dict[str, Any]) -> str:
    col = op.get("column")
    if col not in df.columns:
        raise AnalysisError(f"Column '{col}' not found for operation '{op['op']}'.")
    return col


def propose_plan(diagnostics: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn diagnostics into an ordered cleaning plan (the Data Cleaning agent's deterministic core).

    Rows flagged by several checks are dropped once. Outlier winsorizing is never proposed
    automatically, because extreme values can be valid; it stays a visible suggestion.
    """
    plan: list[dict[str, Any]] = []
    drop_rows: dict[int, list[str]] = {}
    for issue in diagnostics.get("issues", []):
        op = issue.get("operation")
        if not op:
            continue
        if op["op"] == "drop_rows":
            for r in op.get("rows", []):
                drop_rows.setdefault(int(r), []).append(op.get("reason", issue["check"]))
        elif op["op"] in ("drop_duplicates", "pseudonymize", "set_out_of_range_missing", "drop_columns"):
            plan.append(op)
    if drop_rows:
        reasons = sorted({reason for rs in drop_rows.values() for reason in rs})
        plan.append({"op": "drop_rows", "rows": sorted(drop_rows), "reason": "; ".join(reasons)})
    order = {"pseudonymize": 0, "drop_duplicates": 1, "set_out_of_range_missing": 2, "drop_rows": 3, "drop_columns": 4}
    plan.sort(key=lambda o: order.get(o["op"], 9))
    return plan
