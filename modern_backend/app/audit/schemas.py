"""Pydantic models for audit events, checks, and package generation."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


AuditStatus = Literal["PASS", "WARN", "FAIL"]
PackageMode = Literal["standard", "print", "email"]


class AuditEventActor(BaseModel):
    actor_type: Literal["user", "service", "system"] = "user"
    user_id: str | None = None
    username: str | None = None
    role: str | None = None


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    module: str = Field(min_length=1, max_length=120)
    entity_type: str = Field(min_length=1, max_length=120)
    entity_id: str = Field(min_length=1, max_length=120)
    action: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=60)
    correlation_id: str | None = Field(default=None, max_length=128)
    actor: AuditEventActor
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    evidence_links: list[str] = Field(default_factory=list)
    retention_until: date
    note: str | None = Field(default=None, max_length=1000)
    prev_hash: str | None = Field(default=None, max_length=128)
    event_hash: str | None = Field(default=None, max_length=128)


class AuditCheckRequest(BaseModel):
    fiscal_year: int = Field(ge=2000, le=2100)
    date_from: date | None = None
    date_to: date | None = None
    include_sections: list[str] = Field(default_factory=list)
    generated_by: str = Field(default="system", max_length=120)
    generated_by_name: str | None = Field(default=None, max_length=120)
    correlation_id: str | None = Field(default=None, max_length=128)
    package_mode: PackageMode = "standard"
    package_name: str | None = Field(default=None, max_length=120)


class AuditCheckFinding(BaseModel):
    check_id: str
    status: AuditStatus
    severity: Literal["low", "medium", "high", "critical"]
    message: str
    affected_record_ids: list[str] = Field(default_factory=list)
    suggested_fix_steps: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False


class AuditCheckReport(BaseModel):
    fiscal_year: int
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    overall_status: AuditStatus
    findings: list[AuditCheckFinding] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
    correlation_id: str | None = None


class PackageArtifact(BaseModel):
    section: str
    file_name: str
    format: Literal["pdf", "csv", "xlsx", "json", "md", "txt"]
    sha256: str
    size_bytes: int
    source_tables: list[str] = Field(default_factory=list)


class PackageManifest(BaseModel):
    package_id: str
    package_name: str
    package_mode: PackageMode
    fiscal_year: int
    date_from: date | None = None
    date_to: date | None = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generated_by: str
    generated_by_name: str | None = None
    correlation_id: str | None = None
    retention_policy: str = "6+ years"
    overall_status: AuditStatus
    content_hash: str
    zip_path: str
    notes_path: str
    artifacts: list[PackageArtifact] = Field(default_factory=list)
    checks: list[AuditCheckFinding] = Field(default_factory=list)
