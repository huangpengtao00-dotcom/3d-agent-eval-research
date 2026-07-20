from __future__ import annotations

from pathlib import Path

from agent_eval.artifacts import UnsafeSourcePath, resolve_source_path
from agent_eval.canonical import sha256_file
from agent_eval.contracts import AuditIssueCode, AuditResult, DataQualityStatus, SourceSnapshot
from agent_eval.mapping import AmbiguousRoundTurnMapping, resolve_round_turns

REQUIRED_VIEWS = {"front", "back", "left", "right", "top", "isometric"}


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
    try:
        resolve_round_turns(snapshot)
    except AmbiguousRoundTurnMapping:
        fatal.append(AuditIssueCode.AMBIGUOUS_ROUND_TURN_MAPPING)

    step_ids = {step.step_id for step in snapshot.steps}
    turn_ids = {turn.turn_id for turn in snapshot.turns}
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
        if artifact.producing_step_id not in step_ids or artifact.producing_turn_id not in turn_ids:
            fatal.append(AuditIssueCode.BROKEN_ARTIFACT_LINEAGE)
        if (artifact.producing_step_id, artifact.artifact_id) not in lineage_pairs:
            fatal.append(AuditIssueCode.BROKEN_ARTIFACT_LINEAGE)

    artifact_hashes = {artifact.artifact_id: artifact.sha256 for artifact in snapshot.artifacts}
    views_by_artifact: dict[str, set[str]] = {}
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
    for artifact in snapshot.artifacts:
        if artifact.kind == "model" and not REQUIRED_VIEWS.issubset(
            views_by_artifact.get(artifact.artifact_id, set())
        ):
            fatal.append(AuditIssueCode.STANDARD_VIEW_GENERATION_FAILED)

    if AuditIssueCode.MISSING_ROUND_SIMULATOR_CALL_RECORD in snapshot.attempt.source_quality_issues:
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
