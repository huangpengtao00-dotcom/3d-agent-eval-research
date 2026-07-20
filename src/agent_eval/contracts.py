from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SafeIdentifier = Annotated[
    str,
    Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"),
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DataQualityStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    EXCLUDED = "excluded"


class DisclosureClass(StrEnum):
    PUBLIC = "public"
    DERIVED_PUBLIC = "derived_public"
    PRIVATE_REPRODUCIBLE = "private_reproducible"
    RESTRICTED = "restricted"


class AuditIssueCode(StrEnum):
    AUDIT_NOT_RUN = "audit_not_run"
    MISSING_EXPLICIT_AGENT_VERSION = "missing_explicit_agent_version"
    MISSING_AGENT_CONFIG_DIGEST = "missing_agent_config_digest"
    MISSING_EXPERIMENT_SNAPSHOT = "missing_experiment_snapshot"
    AMBIGUOUS_ROUND_TURN_MAPPING = "ambiguous_round_turn_mapping"
    MISSING_REQUIRED_ARTIFACT = "missing_required_artifact"
    ARTIFACT_HASH_MISMATCH = "artifact_hash_mismatch"
    BROKEN_ARTIFACT_LINEAGE = "broken_artifact_lineage"
    STANDARD_VIEW_GENERATION_FAILED = "standard_view_generation_failed"
    LABEL_LEAKAGE_IN_JUDGE_INPUT = "label_leakage_in_judge_input"
    UNAPPROVED_USER_DATA = "unapproved_user_data"
    BUNDLE_CHECKSUM_INCOMPLETE = "bundle_checksum_incomplete"
    UNSUPPORTED_SOURCE_SCHEMA = "unsupported_source_schema"
    MISSING_ROUND_SIMULATOR_CALL_RECORD = "missing_round_simulator_call_record"
    INVALID_EVIDENCE_REFERENCE = "invalid_evidence_reference"
    UNSUPPORTED_ARTIFACT_FORMAT = "unsupported_artifact_format"


class ExperimentSnapshot(StrictModel):
    snapshot_hash: Sha256 | None = None
    dataset_content_hash: Sha256 | None = None
    snapshot_at: datetime
    case_spec: dict[str, Any]


class RunSnapshot(StrictModel):
    agent_version: str | None = Field(default=None, min_length=1)
    agent_config_digest: Sha256 | None = None
    toolset_digest: Sha256 | None = None
    skill_digests: dict[str, Sha256]
    simulator: dict[str, Any]
    random_seed: int | None = None


class AttemptSnapshot(StrictModel):
    attempt_id: str = Field(min_length=1)
    attempt_no: int = Field(ge=1)
    thread_id: str = Field(min_length=1)
    state: str = Field(min_length=1)
    termination_reason: str = Field(min_length=1)
    source_quality_issues: list[AuditIssueCode] = Field(default_factory=list)


class RoundSnapshot(StrictModel):
    round_no: int = Field(ge=1)
    submitted_blocks: list[dict[str, Any]]
    turn_ids: list[str] = Field(default_factory=list)
    observations: list[dict[str, Any]]
    simulator_calls: list[dict[str, Any]]


class TurnSnapshot(StrictModel):
    turn_id: str = Field(min_length=1)
    idempotency_key: str | None = None
    state: str = Field(min_length=1)


class StepSnapshot(StrictModel):
    step_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    payload: dict[str, Any]


class EventSnapshot(StrictModel):
    event_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    order_key: int = Field(ge=0)
    payload: dict[str, Any]


class LineageEdge(StrictModel):
    parent_id: str = Field(min_length=1)
    child_id: str = Field(min_length=1)
    relation: str = Field(min_length=1)


class ArtifactSource(StrictModel):
    artifact_id: SafeIdentifier
    kind: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    sha256: Sha256
    byte_length: int = Field(ge=0)
    producing_turn_id: str = Field(min_length=1)
    producing_step_id: str = Field(min_length=1)
    required: bool = True


class StandardViewSource(StrictModel):
    artifact_id: SafeIdentifier
    view_name: SafeIdentifier
    relative_path: str = Field(min_length=1)
    source_artifact_sha256: Sha256
    sha256: Sha256
    byte_length: int = Field(ge=0)
    renderer: str = Field(min_length=1)
    renderer_version: str = Field(min_length=1)
    parameters: dict[str, Any]


class SourceSnapshot(StrictModel):
    schema_version: int = Field(ge=1)
    trajectory_id: SafeIdentifier
    case_family_key: str = Field(min_length=1)
    split_group_key: str = Field(min_length=1)
    experiment: ExperimentSnapshot
    run: RunSnapshot
    attempt: AttemptSnapshot
    rounds: list[RoundSnapshot]
    turns: list[TurnSnapshot]
    steps: list[StepSnapshot]
    events: list[EventSnapshot]
    lineage: list[LineageEdge]
    artifacts: list[ArtifactSource]
    standard_views: list[StandardViewSource]

    @model_validator(mode="after")
    def evidence_destinations_are_unique(self) -> Self:
        artifact_ids = [artifact.artifact_id for artifact in self.artifacts]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("duplicate artifact_id")
        folded_artifact_ids = [artifact_id.casefold() for artifact_id in artifact_ids]
        if len(folded_artifact_ids) != len(set(folded_artifact_ids)):
            raise ValueError("case-insensitive artifact_id collision")
        view_keys = [(view.artifact_id, view.view_name) for view in self.standard_views]
        if len(view_keys) != len(set(view_keys)):
            raise ValueError("duplicate standard view")
        folded_view_keys = [
            (artifact_id.casefold(), view_name.casefold()) for artifact_id, view_name in view_keys
        ]
        if len(folded_view_keys) != len(set(folded_view_keys)):
            raise ValueError("case-insensitive standard view collision")
        return self


class FileRecord(StrictModel):
    relative_path: str
    sha256: Sha256
    byte_length: int = Field(ge=0)
    media_type: str


class AuditResult(StrictModel):
    status: DataQualityStatus
    issues: list[AuditIssueCode]
    eligible_analyses: list[str]


class BundleManifest(StrictModel):
    bundle_schema_version: int = 1
    trajectory_id: SafeIdentifier
    source_schema_version: int
    case_family_key: str
    split_group_key: str
    source_snapshot_at: datetime
    source_snapshot_sha256: Sha256
    content_inventory_sha256: Sha256
    agent_version: str | None
    agent_config_digest: Sha256 | None
    toolset_digest: Sha256 | None
    skill_digests: dict[str, Sha256]
    simulator_config_sha256: Sha256
    exporter_version: str
    exporter_parameters: dict[str, Any]
    disclosure_class: DisclosureClass
    files: list[FileRecord]
    data_quality: AuditResult


def load_source_snapshot(path: Path) -> SourceSnapshot:
    return SourceSnapshot.model_validate(json.loads(path.read_text(encoding="utf-8")))
