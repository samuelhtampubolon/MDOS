"""Human approval gates. Agents request approvals; people decide; decisions dispatch to handlers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import utcnow
from ..errors import Conflict, NotFound, ValidationFailed
from ..jsonutil import to_jsonable
from ..models import Approval, Project

Handler = Callable[[Session, Project, Approval, str], dict[str, Any]]
_HANDLERS: dict[str, Handler] = {}


def handler(action: str) -> Callable[[Handler], Handler]:
    def register(fn: Handler) -> Handler:
        _HANDLERS[action] = fn
        return fn

    return register


def request(db: Session, project: Project, *, action: str, entity_type: str, entity_id: str, summary: str,
            payload: dict[str, Any] | None = None, requested_by: str) -> Approval:
    pending = db.scalar(select(Approval).where(Approval.project_id == project.id, Approval.action == action,
                                               Approval.entity_id == entity_id, Approval.status == "pending"))
    if pending:
        pending.payload = to_jsonable(payload or pending.payload)
        pending.summary = summary
        return pending
    approval = Approval(project_id=project.id, action=action, entity_type=entity_type, entity_id=entity_id,
                        summary=summary, payload=to_jsonable(payload or {}), requested_by=requested_by)
    db.add(approval)
    db.flush()
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type="agent" if requested_by.startswith("agent:") else "user",
                 actor_id=requested_by, action="approval.request", entity_type=entity_type, entity_id=entity_id,
                 details={"action": action, "approval": approval.id})
    return approval


def resolve_pending(db: Session, project: Project, action: str, entity_id: str, status: str, user_id: str,
                    rationale: str = "") -> None:
    """Close pending approvals when a person decides directly on the entity page."""
    for approval in db.scalars(select(Approval).where(Approval.project_id == project.id, Approval.action == action,
                                                      Approval.entity_id == entity_id, Approval.status == "pending")).all():
        approval.status = status
        approval.decided_by = user_id
        approval.decided_at = utcnow()
        approval.rationale = rationale


def decide(db: Session, project: Project, approval: Approval, decision: str, user_id: str, rationale: str = "") -> dict[str, Any]:
    if approval.project_id != project.id:
        raise NotFound("Approval not found.")
    if approval.status != "pending":
        raise Conflict("This approval has already been decided.")
    if decision not in ("approved", "rejected"):
        raise ValidationFailed("Decision must be approved or rejected.")
    fn = _HANDLERS.get(approval.action)
    if fn is None:
        raise ValidationFailed(f"No handler for approval action '{approval.action}'.")
    approval.decided_by = user_id
    outcome: dict[str, Any] = fn(db, project, approval, decision) or {}
    approval.status = decision
    approval.decided_at = utcnow()
    approval.rationale = rationale
    audit.record(db, org_id=project.org_id, project_id=project.id, actor_type="user", actor_id=user_id,
                 action=f"approval.{decision}", entity_type=approval.entity_type, entity_id=approval.entity_id,
                 details={"action": approval.action, "approval": approval.id, "outcome": outcome})
    return outcome
