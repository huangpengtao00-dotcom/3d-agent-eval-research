import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_eval.contracts import DataQualityStatus, SourceSnapshot, load_source_snapshot
from tests.helpers import minimum_snapshot


def test_load_source_snapshot_is_strict(tmp_path: Path) -> None:
    payload = minimum_snapshot()
    source = tmp_path / "snapshot.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    snapshot = load_source_snapshot(source)
    assert snapshot.attempt.attempt_id == "attempt-001"
    assert DataQualityStatus.COMPLETE.value == "complete"


def test_unknown_source_field_is_rejected(tmp_path: Path) -> None:
    payload = minimum_snapshot()
    payload["secret_internal_field"] = "must not pass"
    source = tmp_path / "snapshot.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_source_snapshot(source)


def test_output_identifiers_cannot_escape_bundle_roots(tmp_path: Path) -> None:
    payload = minimum_snapshot()
    payload["trajectory_id"] = "../outside"
    source = tmp_path / "snapshot.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_source_snapshot(source)


def test_duplicate_evidence_destinations_are_rejected() -> None:
    payload = minimum_snapshot()
    artifact = {
        "artifact_id": "artifact-001",
        "kind": "model",
        "relative_path": "files/model.glb",
        "media_type": "model/gltf-binary",
        "sha256": "0" * 64,
        "byte_length": 0,
        "producing_turn_id": "turn-001",
        "producing_step_id": "step-001",
        "required": True,
    }
    payload["artifacts"] = [artifact, artifact]
    with pytest.raises(ValidationError, match="duplicate artifact_id"):
        SourceSnapshot.model_validate(payload)


def test_duplicate_standard_view_destinations_are_rejected() -> None:
    payload = minimum_snapshot()
    view = {
        "artifact_id": "artifact-001",
        "view_name": "front",
        "relative_path": "views/front.png",
        "source_artifact_sha256": "0" * 64,
        "sha256": "0" * 64,
        "byte_length": 0,
        "renderer": "fixed-renderer",
        "renderer_version": "1.0.0",
        "render_protocol_digest": "f" * 64,
        "parameters": {},
    }
    payload["standard_views"] = [view, view]
    with pytest.raises(ValidationError, match="duplicate standard view"):
        SourceSnapshot.model_validate(payload)


def test_casefolded_artifact_destinations_are_rejected() -> None:
    payload = minimum_snapshot()
    artifact = {
        "kind": "model",
        "relative_path": "files/model.glb",
        "media_type": "model/gltf-binary",
        "sha256": "0" * 64,
        "byte_length": 0,
        "producing_turn_id": "turn-001",
        "producing_step_id": "step-001",
        "required": True,
    }
    payload["artifacts"] = [
        {**artifact, "artifact_id": "Artifact"},
        {**artifact, "artifact_id": "artifact"},
    ]
    with pytest.raises(ValidationError, match="case-insensitive artifact_id"):
        SourceSnapshot.model_validate(payload)
