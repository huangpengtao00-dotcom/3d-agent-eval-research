from pathlib import Path

from agent_eval.audit import audit_snapshot
from agent_eval.contracts import DataQualityStatus, SourceSnapshot
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
