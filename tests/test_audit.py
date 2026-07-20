from pathlib import Path

from agent_eval.audit import audit_snapshot
from agent_eval.contracts import DataQualityStatus, EventSnapshot, SourceSnapshot
from tests.helpers import minimum_snapshot

MODEL_SHA256 = "9372c470eeadd5ecd9c3c74c2b3cb633f8e2f2fad799250a0f70d652b6b825e4"
VIEW_SHA256 = "8f8cbb7dcf46e0bc7d53265749a6c17d116093a6ba95e442764060c76fd4a86c"


def snapshot() -> SourceSnapshot:
    payload = minimum_snapshot()
    payload["steps"] = [
        {"step_id": "step-001", "turn_id": "turn-001", "payload": {"tool": "generate"}}
    ]
    payload["lineage"] = [
        {"parent_id": "step-001", "child_id": "artifact-001", "relation": "produced"}
    ]
    payload["artifacts"] = [
        {
            "artifact_id": "artifact-001",
            "kind": "model",
            "relative_path": "files/model.glb",
            "media_type": "model/gltf-binary",
            "sha256": MODEL_SHA256,
            "byte_length": 5,
            "producing_turn_id": "turn-001",
            "producing_step_id": "step-001",
            "required": True,
        }
    ]
    payload["standard_views"] = [
        {
            "artifact_id": "artifact-001",
            "view_name": name,
            "relative_path": f"views/{name}.png",
            "source_artifact_sha256": MODEL_SHA256,
            "sha256": VIEW_SHA256,
            "byte_length": 3,
            "renderer": "fixed-renderer",
            "renderer_version": "1.0.0",
            "render_protocol_digest": "f" * 64,
            "parameters": {"projection": "perspective"},
        }
        for name in ("front", "back", "left", "right", "top", "isometric")
    ]
    return SourceSnapshot.model_validate(payload)


def write_evidence(source: SourceSnapshot, root: Path) -> None:
    (root / "files").mkdir()
    (root / "files/model.glb").write_bytes(b"model")
    (root / "views").mkdir()
    for view in source.standard_views:
        (root / view.relative_path).write_bytes(b"png")


def test_complete_snapshot_is_eligible_for_main_analyses(tmp_path: Path) -> None:
    source = snapshot()
    write_evidence(source, tmp_path)
    result = audit_snapshot(source, tmp_path)
    assert result.status is DataQualityStatus.COMPLETE
    assert "content_quality" in result.eligible_analyses
    assert "simulator_cost_latency" in result.eligible_analyses


def test_missing_round_call_is_partial_only_for_cost_analysis(tmp_path: Path) -> None:
    source = snapshot()
    write_evidence(source, tmp_path)
    attempt = source.attempt.model_copy(
        update={"source_quality_issues": ["missing_round_simulator_call_record"]}
    )
    result = audit_snapshot(source.model_copy(update={"attempt": attempt}), tmp_path)
    assert result.status is DataQualityStatus.PARTIAL
    assert "missing_round_simulator_call_record" in result.issues
    assert "content_quality" in result.eligible_analyses
    assert "simulator_cost_latency" not in result.eligible_analyses


def test_ambiguous_round_mapping_is_excluded(tmp_path: Path) -> None:
    source = snapshot()
    broken_round = source.rounds[0].model_copy(update={"turn_ids": ["missing-turn"]})
    result = audit_snapshot(source.model_copy(update={"rounds": [broken_round]}), tmp_path)
    assert result.status is DataQualityStatus.EXCLUDED
    assert "ambiguous_round_turn_mapping" in result.issues
    assert result.eligible_analyses == []


def test_missing_required_artifact_is_excluded(tmp_path: Path) -> None:
    result = audit_snapshot(snapshot(), tmp_path)
    assert result.status is DataQualityStatus.EXCLUDED
    assert "missing_required_artifact" in result.issues


def test_artifact_hash_mismatch_is_excluded(tmp_path: Path) -> None:
    source = snapshot()
    (tmp_path / "files").mkdir()
    (tmp_path / "files/model.glb").write_bytes(b"changed")
    result = audit_snapshot(source, tmp_path)
    assert result.status is DataQualityStatus.EXCLUDED
    assert "artifact_hash_mismatch" in result.issues


def test_unsupported_source_schema_is_excluded(tmp_path: Path) -> None:
    source = snapshot().model_copy(update={"schema_version": 2})
    result = audit_snapshot(source, tmp_path)
    assert result.status is DataQualityStatus.EXCLUDED
    assert "unsupported_source_schema" in result.issues


def test_snapshot_without_model_evidence_is_excluded(tmp_path: Path) -> None:
    source = SourceSnapshot.model_validate(minimum_snapshot())
    result = audit_snapshot(source, tmp_path)
    assert result.status is DataQualityStatus.EXCLUDED
    assert "missing_required_artifact" in result.issues


def test_unapproved_research_data_is_excluded(tmp_path: Path) -> None:
    source = snapshot().model_copy(update={"research_data_approved": False})
    write_evidence(source, tmp_path)
    result = audit_snapshot(source, tmp_path)
    assert result.status is DataQualityStatus.EXCLUDED
    assert "unapproved_user_data" in result.issues


def test_judge_label_leakage_is_excluded(tmp_path: Path) -> None:
    source = snapshot()
    leaked_round = source.rounds[0].model_copy(
        update={"submitted_blocks": [{"type": "text", "metadata": [{"Gold_Label": "pass"}]}]}
    )
    leaked = source.model_copy(update={"rounds": [leaked_round]})
    write_evidence(leaked, tmp_path)
    result = audit_snapshot(leaked, tmp_path)
    assert result.status is DataQualityStatus.EXCLUDED
    assert "label_leakage_in_judge_input" in result.issues


def test_secret_like_user_data_is_excluded(tmp_path: Path) -> None:
    source = snapshot()
    leaked_round = source.rounds[0].model_copy(
        update={"submitted_blocks": [{"type": "text", "password": "not-approved"}]}
    )
    leaked = source.model_copy(update={"rounds": [leaked_round]})
    write_evidence(leaked, tmp_path)
    result = audit_snapshot(leaked, tmp_path)
    assert result.status is DataQualityStatus.EXCLUDED
    assert "unapproved_user_data" in result.issues


def test_artifact_step_must_belong_to_declared_turn(tmp_path: Path) -> None:
    source = snapshot()
    extra_turn = source.turns[0].model_copy(update={"turn_id": "turn-other"})
    wrong_step = source.steps[0].model_copy(update={"turn_id": "turn-other"})
    broken = source.model_copy(update={"turns": [*source.turns, extra_turn], "steps": [wrong_step]})
    write_evidence(broken, tmp_path)
    result = audit_snapshot(broken, tmp_path)
    assert result.status is DataQualityStatus.EXCLUDED
    assert "broken_artifact_lineage" in result.issues


def test_event_references_and_order_are_validated(tmp_path: Path) -> None:
    source = snapshot()
    events = [
        EventSnapshot(event_id="event-a", turn_id="missing", order_key=1, payload={}),
        EventSnapshot(event_id="event-b", turn_id="turn-001", order_key=1, payload={}),
    ]
    broken = source.model_copy(update={"events": events})
    write_evidence(broken, tmp_path)
    result = audit_snapshot(broken, tmp_path)
    assert result.status is DataQualityStatus.EXCLUDED
    assert "broken_trajectory_reference" in result.issues
    assert "inconsistent_trajectory_order" in result.issues


def test_standard_views_must_share_one_render_protocol(tmp_path: Path) -> None:
    source = snapshot()
    changed = source.standard_views[-1].model_copy(update={"render_protocol_digest": "0" * 64})
    broken = source.model_copy(update={"standard_views": [*source.standard_views[:-1], changed]})
    write_evidence(broken, tmp_path)
    result = audit_snapshot(broken, tmp_path)
    assert result.status is DataQualityStatus.EXCLUDED
    assert "standard_view_generation_failed" in result.issues


def test_missing_round_call_is_detected_from_aggregate_usage(tmp_path: Path) -> None:
    source = snapshot()
    run = source.run.model_copy(update={"simulator_invocation_count": 1})
    write_evidence(source, tmp_path)
    result = audit_snapshot(source.model_copy(update={"run": run}), tmp_path)
    assert result.status is DataQualityStatus.PARTIAL
    assert "missing_round_simulator_call_record" in result.issues


def test_legacy_v1_hardening_fields_are_audited_instead_of_rejected(tmp_path: Path) -> None:
    payload = snapshot().model_dump(mode="json")
    del payload["research_data_approved"]
    del payload["run"]["simulator_invocation_count"]
    for view in payload["standard_views"]:
        del view["render_protocol_digest"]
    source = SourceSnapshot.model_validate(payload)
    write_evidence(source, tmp_path)
    result = audit_snapshot(source, tmp_path)
    assert result.status is DataQualityStatus.EXCLUDED
    assert "unapproved_user_data" in result.issues
    assert "standard_view_generation_failed" in result.issues
    assert "missing_round_simulator_call_record" in result.issues


def test_mixed_case_model_kind_cannot_bypass_standard_views(tmp_path: Path) -> None:
    source = snapshot()
    model = source.artifacts[0].model_copy(update={"kind": "Model"})
    broken = source.model_copy(update={"artifacts": [model], "standard_views": []})
    (tmp_path / "files").mkdir()
    (tmp_path / "files/model.glb").write_bytes(b"model")
    result = audit_snapshot(broken, tmp_path)
    assert result.status is DataQualityStatus.EXCLUDED
    assert "standard_view_generation_failed" in result.issues


def test_duplicate_event_identity_is_inconsistent_trajectory_order(tmp_path: Path) -> None:
    source = snapshot()
    events = [
        EventSnapshot(event_id="event-a", turn_id="turn-001", order_key=1, payload={}),
        EventSnapshot(event_id="event-a", turn_id="turn-001", order_key=2, payload={}),
    ]
    broken = source.model_copy(update={"events": events})
    write_evidence(broken, tmp_path)
    result = audit_snapshot(broken, tmp_path)
    assert result.status is DataQualityStatus.EXCLUDED
    assert "inconsistent_trajectory_order" in result.issues
