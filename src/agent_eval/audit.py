from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_eval.artifacts import UnsafeSourcePath, resolve_source_path
from agent_eval.canonical import sha256_file
from agent_eval.contracts import AuditIssueCode, AuditResult, DataQualityStatus, SourceSnapshot
from agent_eval.mapping import AmbiguousRoundTurnMapping, resolve_round_turns

REQUIRED_VIEWS = {"front", "back", "left", "right", "top", "isometric"}
JUDGE_LABEL_KEYS = {
    "gold_label",
    "hidden_verdict",
    "judge_label",
    "simulator_termination_label",
    "termination_label",
}
SENSITIVE_USER_DATA_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "credential",
    "password",
    "secret",
}


def _contains_key(value: Any, forbidden_keys: set[str]) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).casefold() in forbidden_keys or _contains_key(item, forbidden_keys)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_key(item, forbidden_keys) for item in value)
    return False


def audit_snapshot(snapshot: SourceSnapshot, source_root: Path) -> AuditResult:
    fatal: list[AuditIssueCode] = []
    partial: list[AuditIssueCode] = []

    if snapshot.schema_version != 1:
        fatal.append(AuditIssueCode.UNSUPPORTED_SOURCE_SCHEMA)
    if not snapshot.run.agent_version:
        fatal.append(AuditIssueCode.MISSING_EXPLICIT_AGENT_VERSION)
    if (
        not snapshot.run.agent_config_digest
        or not snapshot.run.toolset_digest
        or not snapshot.run.skill_digests
    ):
        fatal.append(AuditIssueCode.MISSING_AGENT_CONFIG_DIGEST)
    if not snapshot.experiment.snapshot_hash or not snapshot.experiment.dataset_content_hash:
        fatal.append(AuditIssueCode.MISSING_EXPERIMENT_SNAPSHOT)
    if snapshot.research_data_approved is not True:
        fatal.append(AuditIssueCode.UNAPPROVED_USER_DATA)
    if not any(
        artifact.required and artifact.kind.casefold() == "model" for artifact in snapshot.artifacts
    ):
        fatal.append(AuditIssueCode.MISSING_REQUIRED_ARTIFACT)
    if any(
        _contains_key(round_record.submitted_blocks, JUDGE_LABEL_KEYS)
        for round_record in snapshot.rounds
    ):
        fatal.append(AuditIssueCode.LABEL_LEAKAGE_IN_JUDGE_INPUT)
    if any(
        _contains_key(round_record.submitted_blocks, SENSITIVE_USER_DATA_KEYS)
        for round_record in snapshot.rounds
    ):
        fatal.append(AuditIssueCode.UNAPPROVED_USER_DATA)
    try:
        resolve_round_turns(snapshot)
    except AmbiguousRoundTurnMapping:
        fatal.append(AuditIssueCode.AMBIGUOUS_ROUND_TURN_MAPPING)

    steps_by_id = {step.step_id: step for step in snapshot.steps}
    turn_ids = {turn.turn_id for turn in snapshot.turns}
    if any(step.turn_id not in turn_ids for step in snapshot.steps):
        fatal.append(AuditIssueCode.BROKEN_ARTIFACT_LINEAGE)
    if any(event.turn_id not in turn_ids for event in snapshot.events):
        fatal.append(AuditIssueCode.BROKEN_TRAJECTORY_REFERENCE)
    event_ids = [event.event_id for event in snapshot.events]
    event_order_keys = [event.order_key for event in snapshot.events]
    if (
        len(event_ids) != len(set(event_ids))
        or len(event_order_keys) != len(set(event_order_keys))
        or event_order_keys != sorted(event_order_keys)
    ):
        fatal.append(AuditIssueCode.INCONSISTENT_TRAJECTORY_ORDER)
    lineage_pairs = {(edge.parent_id, edge.child_id) for edge in snapshot.lineage}
    for artifact in snapshot.artifacts:
        try:
            artifact_path = resolve_source_path(source_root, artifact.relative_path)
        except UnsafeSourcePath:
            artifact_path = None
        if artifact.required and (artifact_path is None or not artifact_path.is_file()):
            fatal.append(AuditIssueCode.MISSING_REQUIRED_ARTIFACT)
        elif artifact_path is not None and (
            artifact_path.stat().st_size != artifact.byte_length
            or sha256_file(artifact_path) != artifact.sha256
        ):
            fatal.append(AuditIssueCode.ARTIFACT_HASH_MISMATCH)
        producing_step = steps_by_id.get(artifact.producing_step_id)
        if (
            producing_step is None
            or artifact.producing_turn_id not in turn_ids
            or producing_step.turn_id != artifact.producing_turn_id
        ):
            fatal.append(AuditIssueCode.BROKEN_ARTIFACT_LINEAGE)
        if (artifact.producing_step_id, artifact.artifact_id) not in lineage_pairs:
            fatal.append(AuditIssueCode.BROKEN_ARTIFACT_LINEAGE)

    artifact_hashes = {artifact.artifact_id: artifact.sha256 for artifact in snapshot.artifacts}
    views_by_artifact: dict[str, set[str]] = {}
    render_protocols_by_artifact: dict[str, set[str | None]] = {}
    for view in snapshot.standard_views:
        try:
            view_path = resolve_source_path(source_root, view.relative_path)
        except UnsafeSourcePath:
            view_path = None
        if (
            view_path is None
            or not view_path.is_file()
            or view_path.stat().st_size != view.byte_length
            or sha256_file(view_path) != view.sha256
        ):
            fatal.append(AuditIssueCode.STANDARD_VIEW_GENERATION_FAILED)
        if artifact_hashes.get(view.artifact_id) != view.source_artifact_sha256:
            fatal.append(AuditIssueCode.ARTIFACT_HASH_MISMATCH)
        views_by_artifact.setdefault(view.artifact_id, set()).add(view.view_name)
        render_protocols_by_artifact.setdefault(view.artifact_id, set()).add(
            view.render_protocol_digest
        )
    for artifact in snapshot.artifacts:
        is_model = artifact.kind.casefold() == "model"
        if is_model and not REQUIRED_VIEWS.issubset(
            views_by_artifact.get(artifact.artifact_id, set())
        ):
            fatal.append(AuditIssueCode.STANDARD_VIEW_GENERATION_FAILED)
        render_protocols = render_protocols_by_artifact.get(artifact.artifact_id, set())
        if is_model and (len(render_protocols) != 1 or None in render_protocols):
            fatal.append(AuditIssueCode.STANDARD_VIEW_GENERATION_FAILED)

    if AuditIssueCode.MISSING_ROUND_SIMULATOR_CALL_RECORD in snapshot.attempt.source_quality_issues:
        partial.append(AuditIssueCode.MISSING_ROUND_SIMULATOR_CALL_RECORD)
    recorded_simulator_calls = sum(
        len(round_record.simulator_calls) for round_record in snapshot.rounds
    )
    if (
        snapshot.run.simulator_invocation_count is None
        or snapshot.run.simulator_invocation_count > recorded_simulator_calls
    ):
        partial.append(AuditIssueCode.MISSING_ROUND_SIMULATOR_CALL_RECORD)

    fatal = sorted(set(fatal))
    partial = sorted(set(partial))
    if fatal:
        return AuditResult(
            status=DataQualityStatus.EXCLUDED,
            issues=fatal + partial,
            eligible_analyses=[],
        )
    analyses = ["content_quality", "failure_attribution", "agent_version_ranking"]
    if not partial:
        analyses.append("simulator_cost_latency")
    return AuditResult(
        status=DataQualityStatus.PARTIAL if partial else DataQualityStatus.COMPLETE,
        issues=partial,
        eligible_analyses=analyses,
    )
