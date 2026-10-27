"""The agent output contract (specification) and the execution context with tool authorization."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..models import Project


class AgentResult(BaseModel):
    """Exactly the ten fields named in the specification's agent_output_contract."""

    task_id: str
    status: Literal["succeeded", "failed", "awaiting_approval", "skipped"]
    inputs_used: list[str] = Field(default_factory=list)
    actions_taken: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    outputs: dict[str, Any] = Field(default_factory=dict)
    recommended_next_step: str = ""


class ToolNotAuthorized(PermissionError):
    """Raised when an agent calls a tool outside its allowlist."""


class AgentBlocked(RuntimeError):
    """Raised when an agent cannot proceed because a precondition is missing (clear message for the user)."""


@dataclass
class AgentContext:
    db: Session
    project: Project
    user_id: str
    run_id: str
    workflow_run_id: str | None
    state: dict[str, Any]
    provider: Any
    allowed_tools: frozenset[str]
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    inputs_used: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    llm_calls: list[dict[str, Any]] = field(default_factory=list)

    @property
    def source_run_id(self) -> str:
        """Rows written by agents carry the workflow ID (or the single run ID) for rollback."""
        return self.workflow_run_id or self.run_id

    def tool(self, name: str):
        """Return an authorized tool. Every call is recorded in ``tools_used``."""
        from .tools import TOOLS

        if name not in self.allowed_tools:
            raise ToolNotAuthorized(f"Tool '{name}' is not on this agent's allowlist.")
        if name not in TOOLS:
            raise ToolNotAuthorized(f"Unknown tool '{name}'.")
        if name not in self.tools_used:
            self.tools_used.append(name)
        fn = TOOLS[name]
        return lambda *args, **kwargs: fn(self, *args, **kwargs)

    def used(self, *inputs: str) -> None:
        for i in inputs:
            if i not in self.inputs_used:
                self.inputs_used.append(i)

    def act(self, text: str) -> None:
        self.actions.append(text)

    def cite(self, *evidence_codes: str) -> None:
        for code in evidence_codes:
            if code and code not in self.evidence:
                self.evidence.append(code)

    def result(self, outputs: dict[str, Any], next_step: str, status: str = "succeeded") -> AgentResult:
        return AgentResult(task_id=self.task_id, status=status, inputs_used=self.inputs_used, actions_taken=self.actions,
                           tools_used=self.tools_used, evidence=self.evidence, assumptions=self.assumptions,
                           uncertainties=self.uncertainties, outputs=outputs, recommended_next_step=next_step)
