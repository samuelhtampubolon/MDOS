"""SQLAlchemy models for every core entity in the specification's data architecture.

Conventions
-----------
* Primary keys are UUID strings.
* Every project-scoped table carries ``project_id`` with ``ON DELETE CASCADE`` so the data deletion
  workflow removes everything that belongs to a project.
* ``source_run_id`` marks rows created by applying an agent proposal. Rollback deletes rows that
  carry the run ID and have not been approved or edited since.
* Human-readable codes (``E1``, ``I1``, ``R1``, ``H1``, ``RQ1``) are unique within a project.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, IdMixin, TimestampMixin, utcnow

# --------------------------------------------------------------------------------------------
# Identity and tenancy
# --------------------------------------------------------------------------------------------


class Organization(IdMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200))


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="member")  # owner | admin | member
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Incremented by "sign out everywhere"; tokens carry the version they were issued with.
    session_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    organization: Mapped[Organization] = relationship()


class Project(IdMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    business_question: Mapped[str] = mapped_column(Text)
    decision_to_inform: Mapped[str] = mapped_column(Text, default="")
    context: Mapped[str] = mapped_column(Text, default="")
    industry: Mapped[str] = mapped_column(String(100), default="")
    geography: Mapped[str] = mapped_column(String(100), default="Indonesia")
    currency: Mapped[str] = mapped_column(String(3), default="IDR")
    status: Mapped[str] = mapped_column(String(20), default="active")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    brief: Mapped[dict] = mapped_column(default=dict)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ProjectMember(Base):
    __tablename__ = "project_members"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default="editor")  # owner | editor | viewer


# --------------------------------------------------------------------------------------------
# Research design
# --------------------------------------------------------------------------------------------


class ResearchQuestion(IdMixin, TimestampMixin, Base):
    __tablename__ = "research_questions"
    __table_args__ = (UniqueConstraint("project_id", "code"),)

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


class Hypothesis(IdMixin, TimestampMixin, Base):
    __tablename__ = "hypotheses"
    __table_args__ = (UniqueConstraint("project_id", "code"),)

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    statement: Mapped[str] = mapped_column(Text)
    iv: Mapped[str] = mapped_column(String(100), default="")
    dv: Mapped[str] = mapped_column(String(100), default="")
    mediator: Mapped[str] = mapped_column(String(100), default="")
    moderator: Mapped[str] = mapped_column(String(100), default="")
    expected_direction: Mapped[str] = mapped_column(String(20), default="positive")
    rationale: Mapped[str] = mapped_column(Text, default="")
    # untested | proposed_supported | proposed_not_supported | proposed_inconclusive
    # | supported | not_supported | inconclusive
    status: Mapped[str] = mapped_column(String(30), default="untested")
    verdict_rationale: Mapped[str] = mapped_column(Text, default="")
    verdict_evidence: Mapped[list] = mapped_column(default=list)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


class Construct(IdMixin, TimestampMixin, Base):
    __tablename__ = "constructs"
    __table_args__ = (UniqueConstraint("project_id", "code"),)

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    definition: Mapped[str] = mapped_column(Text, default="")
    library_key: Mapped[str] = mapped_column(String(100), default="")
    source_reference: Mapped[str] = mapped_column(Text, default="")
    measurement: Mapped[str] = mapped_column(String(20), default="reflective")
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


class Variable(IdMixin, TimestampMixin, Base):
    __tablename__ = "variables"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    construct_id: Mapped[str | None] = mapped_column(
        ForeignKey("constructs.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100))
    label: Mapped[str] = mapped_column(Text, default="")
    # likert | numeric | categorical | binary | text | price | id | datetime
    var_type: Mapped[str] = mapped_column(String(20), default="numeric")
    # iv | dv | mediator | moderator | control | descriptor | screening | text | price | other
    role: Mapped[str] = mapped_column(String(20), default="other")
    scale_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    scale_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_labels: Mapped[dict] = mapped_column(default=dict)
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


class Survey(IdMixin, TimestampMixin, Base):
    __tablename__ = "surveys"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    introduction: Mapped[str] = mapped_column(Text, default="")
    consent_text: Mapped[str] = mapped_column(Text, default="")
    languages: Mapped[list] = mapped_column(default=lambda: ["en", "id"])
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | approved | fielded | closed
    version: Mapped[int] = mapped_column(Integer, default=1)
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    questions: Mapped[list[Question]] = relationship(
        back_populates="survey", cascade="all, delete-orphan", order_by="Question.position"
    )


class Question(IdMixin, TimestampMixin, Base):
    __tablename__ = "questions"

    survey_id: Mapped[str] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(100))
    section: Mapped[str] = mapped_column(String(100), default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
    # single | multi | likert | numeric | text | price | info
    qtype: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    text_id: Mapped[str] = mapped_column(Text, default="")
    options: Mapped[list] = mapped_column(default=list)
    scale: Mapped[dict] = mapped_column(default=dict)
    logic: Mapped[dict] = mapped_column(default=dict)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    construct_code: Mapped[str] = mapped_column(String(20), default="")
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    survey: Mapped[Survey] = relationship(back_populates="questions")


class ResearchPlan(IdMixin, TimestampMixin, Base):
    """Free-form but schema-validated plan documents (framing, design notes, sampling, fieldwork...)."""

    __tablename__ = "research_plans"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    content: Mapped[dict] = mapped_column(default=dict)
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# --------------------------------------------------------------------------------------------
# Data, analysis, evidence
# --------------------------------------------------------------------------------------------


class Dataset(IdMixin, TimestampMixin, Base):
    __tablename__ = "datasets"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(300))
    # survey | reviews | sales | web_analytics | experiment | other
    kind: Mapped[str] = mapped_column(String(30), default="survey")
    # user_data | external | synthetic_demo
    origin: Mapped[str] = mapped_column(String(30), default="user_data")
    description: Mapped[str] = mapped_column(Text, default="")
    current_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    versions: Mapped[list[DatasetVersion]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", order_by="DatasetVersion.version"
    )


class DatasetVersion(IdMixin, TimestampMixin, Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version"),)

    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | superseded
    storage_key: Mapped[str] = mapped_column(String(500))
    original_filename: Mapped[str] = mapped_column(String(300), default="")
    file_format: Mapped[str] = mapped_column(String(10), default="csv")
    n_rows: Mapped[int] = mapped_column(Integer, default=0)
    n_cols: Mapped[int] = mapped_column(Integer, default=0)
    columns: Mapped[list] = mapped_column(default=list)
    operations: Mapped[list] = mapped_column(default=list)
    quality: Mapped[dict] = mapped_column(default=dict)
    checksum: Mapped[str] = mapped_column(String(64), default="")
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    dataset: Mapped[Dataset] = relationship(back_populates="versions")


class Analysis(IdMixin, TimestampMixin, Base):
    __tablename__ = "analyses"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    dataset_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    method: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(300), default="")
    params: Mapped[dict] = mapped_column(default=dict)
    status: Mapped[str] = mapped_column(String(20), default="succeeded")
    result: Mapped[dict] = mapped_column(default=dict)
    assumptions: Mapped[list] = mapped_column(default=list)
    warnings: Mapped[list] = mapped_column(default=list)
    limitations: Mapped[list] = mapped_column(default=list)
    n: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


insight_evidence = Table(
    "insight_evidence",
    Base.metadata,
    Column("insight_id", ForeignKey("insights.id", ondelete="CASCADE"), primary_key=True),
    Column("evidence_id", ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True),
)

recommendation_evidence = Table(
    "recommendation_evidence",
    Base.metadata,
    Column("recommendation_id", ForeignKey("recommendations.id", ondelete="CASCADE"), primary_key=True),
    Column("evidence_id", ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True),
)


class Evidence(IdMixin, TimestampMixin, Base):
    __tablename__ = "evidence"
    __table_args__ = (UniqueConstraint("project_id", "seq"),)

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    code: Mapped[str] = mapped_column(String(20))
    # statistical | quote | theme | external | user_assertion | model_interpretation | experiment
    kind: Mapped[str] = mapped_column(String(30), default="statistical")
    title: Mapped[str] = mapped_column(String(300))
    statement: Mapped[str] = mapped_column(Text)
    analysis_id: Mapped[str | None] = mapped_column(
        ForeignKey("analyses.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    dataset_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_ref: Mapped[dict] = mapped_column(default=dict)
    # user_data | external | model_generated | experiment | synthetic_demo
    origin: Mapped[str] = mapped_column(String(30), default="user_data")
    # cross_sectional_survey | experiment | observational | qualitative | external
    design: Mapped[str] = mapped_column(String(40), default="cross_sectional_survey")
    strength: Mapped[str] = mapped_column(String(20), default="moderate")
    n: Mapped[int | None] = mapped_column(Integer, nullable=True)
    effect_size: Mapped[float | None] = mapped_column(Float, nullable=True)
    effect_label: Mapped[str] = mapped_column(String(50), default="")
    p_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    ci_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ci_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    value: Mapped[dict] = mapped_column(default=dict)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


class Insight(IdMixin, TimestampMixin, Base):
    __tablename__ = "insights"
    __table_args__ = (UniqueConstraint("project_id", "seq"),)

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    code: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(300))
    statement: Mapped[str] = mapped_column(Text)
    implication: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[str] = mapped_column(String(10), default="medium")
    uncertainty: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | approved | rejected
    is_model_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    evidence: Mapped[list[Evidence]] = relationship(secondary=insight_evidence, order_by="Evidence.seq")


class Recommendation(IdMixin, TimestampMixin, Base):
    __tablename__ = "recommendations"
    __table_args__ = (UniqueConstraint("project_id", "seq"),)

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    code: Mapped[str] = mapped_column(String(20))
    statement: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text, default="")
    module: Mapped[str] = mapped_column(String(20), default="research")
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    is_model_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    evidence: Mapped[list[Evidence]] = relationship(secondary=recommendation_evidence, order_by="Evidence.seq")


class Segment(IdMixin, TimestampMixin, Base):
    __tablename__ = "segments"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    analysis_id: Mapped[str | None] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    size: Mapped[int] = mapped_column(Integer, default=0)
    share: Mapped[float] = mapped_column(Float, default=0.0)
    profile: Mapped[dict] = mapped_column(default=dict)
    persona: Mapped[dict] = mapped_column(default=dict)
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


# --------------------------------------------------------------------------------------------
# Strategy
# --------------------------------------------------------------------------------------------


class Scenario(IdMixin, TimestampMixin, Base):
    __tablename__ = "scenarios"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default="scenario")  # baseline | scenario
    baseline_id: Mapped[str | None] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=True, index=True
    )
    description: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[dict] = mapped_column(default=dict)
    levers: Mapped[list] = mapped_column(default=list)
    results: Mapped[dict] = mapped_column(default=dict)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | adopted
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Decision(IdMixin, TimestampMixin, Base):
    __tablename__ = "decisions"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    decision: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text, default="")
    scenario_id: Mapped[str | None] = mapped_column(
        ForeignKey("scenarios.id", ondelete="SET NULL"), nullable=True
    )
    evidence_ids: Mapped[list] = mapped_column(default=list)
    status: Mapped[str] = mapped_column(String(20), default="proposed")  # proposed | approved | rejected
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --------------------------------------------------------------------------------------------
# Journey and experiments
# --------------------------------------------------------------------------------------------


class Journey(IdMixin, TimestampMixin, Base):
    __tablename__ = "journeys"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    template: Mapped[str] = mapped_column(String(40), default="tourism")
    stages: Mapped[list] = mapped_column(default=list)
    settings: Mapped[dict] = mapped_column(default=dict)
    voc: Mapped[dict] = mapped_column(default=dict)
    voc_dataset_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | adopted
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    touchpoints: Mapped[list[Touchpoint]] = relationship(cascade="all, delete-orphan")
    pain_points: Mapped[list[PainPoint]] = relationship(cascade="all, delete-orphan")
    interventions: Mapped[list[Intervention]] = relationship(cascade="all, delete-orphan")


class Touchpoint(IdMixin, TimestampMixin, Base):
    __tablename__ = "touchpoints"

    journey_id: Mapped[str] = mapped_column(ForeignKey("journeys.id", ondelete="CASCADE"), index=True)
    stage_key: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    channel: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    owner: Mapped[str] = mapped_column(String(100), default="")
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


class PainPoint(IdMixin, TimestampMixin, Base):
    __tablename__ = "pain_points"

    journey_id: Mapped[str] = mapped_column(ForeignKey("journeys.id", ondelete="CASCADE"), index=True)
    stage_key: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    theme: Mapped[str] = mapped_column(String(100), default="")
    mentions: Mapped[int] = mapped_column(Integer, default=0)
    frequency: Mapped[float] = mapped_column(Float, default=0.0)  # share of all documents
    severity: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1
    reach: Mapped[float] = mapped_column(Float, default=1.0)  # share of customers passing the stage
    score: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_ids: Mapped[list] = mapped_column(default=list)
    quotes: Mapped[list] = mapped_column(default=list)
    status: Mapped[str] = mapped_column(String(20), default="open")
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


class Intervention(IdMixin, TimestampMixin, Base):
    __tablename__ = "interventions"

    journey_id: Mapped[str] = mapped_column(ForeignKey("journeys.id", ondelete="CASCADE"), index=True)
    pain_point_id: Mapped[str | None] = mapped_column(
        ForeignKey("pain_points.id", ondelete="SET NULL"), nullable=True
    )
    stage_key: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    # reduce_steps | conversion_uplift | satisfaction_uplift
    kind: Mapped[str] = mapped_column(String(30), default="conversion_uplift")
    params: Mapped[dict] = mapped_column(default=dict)
    uplift_low: Mapped[float] = mapped_column(Float, default=0.0)
    uplift_mid: Mapped[float] = mapped_column(Float, default=0.0)
    uplift_high: Mapped[float] = mapped_column(Float, default=0.0)
    effort: Mapped[str] = mapped_column(String(2), default="M")
    confidence: Mapped[str] = mapped_column(String(10), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="idea")
    simulation: Mapped[dict] = mapped_column(default=dict)
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


class Experiment(IdMixin, TimestampMixin, Base):
    __tablename__ = "experiments"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(300))
    source_type: Mapped[str] = mapped_column(String(30), default="manual")
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    hypothesis: Mapped[str] = mapped_column(Text)
    primary_metric: Mapped[str] = mapped_column(String(200))
    baseline_rate: Mapped[float] = mapped_column(Float)
    mde: Mapped[float] = mapped_column(Float)  # relative minimum detectable effect
    alpha: Mapped[float] = mapped_column(Float, default=0.05)
    power: Mapped[float] = mapped_column(Float, default=0.8)
    sample_size_per_arm: Mapped[int] = mapped_column(Integer, default=0)
    expected_daily_traffic: Mapped[int] = mapped_column(Integer, default=0)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    variants: Mapped[list] = mapped_column(default=list)
    # draft | approved | running | completed | cancelled
    status: Mapped[str] = mapped_column(String(20), default="draft")
    results: Mapped[dict] = mapped_column(default=dict)
    evidence_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


# --------------------------------------------------------------------------------------------
# Reports, agents, approvals, audit
# --------------------------------------------------------------------------------------------


class Report(IdMixin, TimestampMixin, Base):
    __tablename__ = "reports"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    # research_report | executive_summary | decision_memo | methods_appendix | experiment_brief
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(300))
    document: Mapped[dict] = mapped_column(default=dict)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | final
    version: Mapped[int] = mapped_column(Integer, default=1)
    evidence_ids: Mapped[list] = mapped_column(default=list)
    is_model_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    finalized_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


class WorkflowRun(IdMixin, TimestampMixin, Base):
    __tablename__ = "workflow_runs"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    workflow: Mapped[str] = mapped_column(String(50))
    # queued | running | awaiting_approval | succeeded | failed | cancelled
    status: Mapped[str] = mapped_column(String(30), default="queued")
    input: Mapped[dict] = mapped_column(default=dict)
    steps: Mapped[list] = mapped_column(default=list)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    context: Mapped[dict] = mapped_column(default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentRun(IdMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    workflow_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    agent: Mapped[str] = mapped_column(String(50))
    step_index: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    input: Mapped[dict] = mapped_column(default=dict)
    result: Mapped[dict] = mapped_column(default=dict)
    provider: Mapped[str] = mapped_column(String(30), default="offline")
    model: Mapped[str] = mapped_column(String(60), default="")
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    error: Mapped[str] = mapped_column(Text, default="")
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    applied_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rolled_back: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Approval(IdMixin, Base):
    __tablename__ = "approvals"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(50))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | approved | rejected
    summary: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(default=dict)
    requested_by: Mapped[str] = mapped_column(String(80))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rationale: Mapped[str] = mapped_column(Text, default="")


class AuditLog(IdMixin, TimestampMixin, Base):
    __tablename__ = "audit_log"

    org_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    actor_type: Mapped[str] = mapped_column(String(10))  # user | agent | system
    actor_id: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(50), default="")
    entity_id: Mapped[str] = mapped_column(String(36), default="")
    details: Mapped[dict] = mapped_column(default=dict)
