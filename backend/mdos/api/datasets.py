"""Datasets: upload, versions, preview, quality diagnostics, cleaning plans and lineage."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import audit, storage
from ..analytics import cleaning
from ..db import get_db
from ..deps import ProjectAccess, project_access
from ..errors import Conflict, NotFound, ValidationFailed
from ..models import Dataset, DatasetVersion
from ..ratelimit import limit_uploads
from ..services import approvals
from ..services import datasets as svc
from .common import get_owned, to_dict

router = APIRouter(prefix="/projects/{project_id}/datasets", tags=["datasets"])


class OperationsIn(BaseModel):
    parent_version_id: str
    operations: list[dict] = Field(min_length=1, max_length=50)


def _dataset_out(db: Session, dataset: Dataset) -> dict:
    data = to_dict(dataset)
    data["versions"] = [to_dict(v, exclude={"storage_key"}) for v in dataset.versions]
    return data


@router.get("")
def list_datasets(access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Dataset).where(Dataset.project_id == access.project.id).order_by(Dataset.created_at)).all()
    out = []
    for d in rows:
        current = db.get(DatasetVersion, d.current_version_id) if d.current_version_id else None
        item = to_dict(d)
        item["current_version"] = to_dict(current, exclude={"storage_key", "columns", "quality"}) if current else None
        item["version_count"] = len(d.versions)
        out.append(item)
    return out


@router.post("", status_code=201, dependencies=[Depends(limit_uploads)])
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(default=""),
    kind: Literal["survey", "reviews", "sales", "web_analytics", "experiment", "other"] = Form(default="survey"),
    origin: Literal["user_data", "external"] = Form(default="user_data"),
    description: str = Form(default=""),
    access: ProjectAccess = Depends(project_access),
    db: Session = Depends(get_db),
) -> dict:
    access.require("editor")
    raw = await file.read()
    filename = file.filename or "upload.csv"
    df, fmt = svc.parse_upload(filename, raw)
    dataset = svc.create_dataset(db, access.project, name=name or filename, kind=kind, origin=origin, filename=filename,
                                 df=df, fmt=fmt, user_id=access.actor, description=description)
    db.commit()
    return _dataset_out(db, dataset)


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    return _dataset_out(db, get_owned(db, Dataset, dataset_id, access.project.id))


@router.delete("/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> None:
    access.require("editor")
    dataset = get_owned(db, Dataset, dataset_id, access.project.id)
    keys = [v.storage_key for v in dataset.versions]
    db.delete(dataset)
    audit.record(db, org_id=access.user.org_id, project_id=access.project.id, actor_type="user", actor_id=access.actor,
                 action="dataset.delete", entity_type="dataset", entity_id=dataset_id)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("Evidence records depend on analyses of this dataset. Delete that evidence first.") from exc
    for key in keys:
        storage.delete_key(key)


@router.get("/{dataset_id}/versions/{version_id}")
def get_version(dataset_id: str, version_id: str, access: ProjectAccess = Depends(project_access),
                db: Session = Depends(get_db)) -> dict:
    version = svc.get_version(db, access.project.id, version_id)
    if version.dataset_id != dataset_id:
        raise NotFound("Dataset version not found.")
    return to_dict(version, exclude={"storage_key"})


@router.get("/{dataset_id}/versions/{version_id}/preview")
def preview(dataset_id: str, version_id: str, limit: int = 50, access: ProjectAccess = Depends(project_access),
            db: Session = Depends(get_db)) -> dict:
    version = svc.get_version(db, access.project.id, version_id)
    if version.dataset_id != dataset_id:
        raise NotFound("Dataset version not found.")
    return svc.preview(version, limit)


@router.post("/{dataset_id}/cleaning-plan")
def propose_cleaning_plan(dataset_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    """Deterministic plan from the current version's diagnostics. Applying it requires approval."""
    access.require("editor")
    dataset = get_owned(db, Dataset, dataset_id, access.project.id)
    version = svc.current_version(db, dataset)
    plan = cleaning.propose_plan(version.quality or {})
    approval = None
    if plan:
        approval = approvals.request(db, access.project, action="apply_cleaning", entity_type="dataset_version",
                                     entity_id=version.id, summary=f"Apply {len(plan)} cleaning operation(s) to {dataset.name} v{version.version}",
                                     payload={"operations": plan}, requested_by=access.actor)
    db.commit()
    return {"parent_version_id": version.id, "operations": plan, "approval_id": approval.id if approval else None}


@router.post("/{dataset_id}/versions", status_code=201)
def apply_operations(dataset_id: str, body: OperationsIn, access: ProjectAccess = Depends(project_access),
                     db: Session = Depends(get_db)) -> dict:
    """A person applying operations directly is the approval (recorded as approved_by)."""
    access.require("editor")
    dataset = get_owned(db, Dataset, dataset_id, access.project.id)
    parent = svc.get_version(db, access.project.id, body.parent_version_id)
    if parent.dataset_id != dataset.id:
        raise ValidationFailed("Parent version belongs to another dataset.")
    version = svc.derive_version(db, access.project, parent, body.operations, user_id=access.actor, approved_by=access.actor)
    approvals.resolve_pending(db, access.project, "apply_cleaning", parent.id, "approved", access.actor, "Applied directly")
    db.commit()
    return to_dict(version, exclude={"storage_key"})


@router.post("/{dataset_id}/compute-scales", status_code=201)
def compute_scales(dataset_id: str, access: ProjectAccess = Depends(project_access), db: Session = Depends(get_db)) -> dict:
    """Add construct mean scores (non-destructive derived columns) as a new version."""
    access.require("editor")
    dataset = get_owned(db, Dataset, dataset_id, access.project.id)
    version = svc.current_version(db, dataset)
    ops = svc.construct_scale_operations(db, access.project.id, [c["name"] for c in version.columns])
    if not ops:
        raise ValidationFailed("No construct scores to compute (items missing or scores already present).")
    new_version = svc.derive_version(db, access.project, version, ops, user_id=access.actor, approved_by=access.actor)
    db.commit()
    return to_dict(new_version, exclude={"storage_key"})


@router.post("/{dataset_id}/versions/{version_id}/restore")
def restore_version(dataset_id: str, version_id: str, access: ProjectAccess = Depends(project_access),
                    db: Session = Depends(get_db)) -> dict:
    """Rollback: make an earlier version current again; later versions are marked superseded."""
    access.require("editor")
    dataset = get_owned(db, Dataset, dataset_id, access.project.id)
    target = svc.get_version(db, access.project.id, version_id)
    if target.dataset_id != dataset.id:
        raise NotFound("Dataset version not found.")
    for v in dataset.versions:
        v.status = "superseded" if v.version > target.version else "active"
    dataset.current_version_id = target.id
    audit.record(db, org_id=access.user.org_id, project_id=access.project.id, actor_type="user", actor_id=access.actor,
                 action="dataset.version.restore", entity_type="dataset_version", entity_id=target.id)
    db.commit()
    return _dataset_out(db, dataset)
