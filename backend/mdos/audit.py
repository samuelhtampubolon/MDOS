"""Audit log helper. Every mutation, approval and agent action is written here."""

from __future__ import annotations

from sqlalchemy.orm import Session

from .jsonutil import to_jsonable
from .models import AuditLog


def record(
    db: Session,
    *,
    org_id: str,
    actor_type: str,
    actor_id: str,
    action: str,
    entity_type: str = "",
    entity_id: str = "",
    project_id: str | None = None,
    details: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        org_id=org_id,
        project_id=project_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id or "",
        details=to_jsonable(details or {}),
    )
    db.add(entry)
    return entry
