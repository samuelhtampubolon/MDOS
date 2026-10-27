"""Helpers shared by routers."""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypeVar

from sqlalchemy import func, select
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.orm import Session

from ..errors import NotFound

T = TypeVar("T")


def get_owned(db: Session, model: type[T], entity_id: str, project_id: str) -> T:
    """Load an entity and make sure it belongs to the project (tenant isolation)."""
    entity = db.get(model, entity_id)
    if entity is None or getattr(entity, "project_id", None) != project_id:
        raise NotFound(f"{model.__name__} not found.")
    return entity


def to_dict(obj: Any, exclude: set[str] | None = None) -> dict[str, Any]:
    """Serialize an ORM row using its mapped columns."""
    exclude = exclude or set()
    out: dict[str, Any] = {}
    for column in sa_inspect(obj).mapper.column_attrs:
        key = column.key
        if key in exclude:
            continue
        value = getattr(obj, key)
        if isinstance(value, datetime):
            value = value.isoformat()
        out[key] = value
    return out


def next_seq(db: Session, model: Any, project_id: str) -> int:
    current = db.scalar(select(func.max(model.seq)).where(model.project_id == project_id))
    return int(current or 0) + 1


def next_code(db: Session, model: Any, project_id: str, prefix: str) -> str:
    """Next human code such as H3 or RQ2, based on existing codes with the same prefix."""
    codes = db.scalars(select(model.code).where(model.project_id == project_id)).all()
    numbers = [int(c[len(prefix):]) for c in codes if c.startswith(prefix) and c[len(prefix):].isdigit()]
    return f"{prefix}{(max(numbers) if numbers else 0) + 1}"
