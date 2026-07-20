import json
from pathlib import Path

from typer.testing import CliRunner

from agent_eval.cli import app
from tests.helpers import minimum_snapshot

runner = CliRunner()
MODEL_SHA256 = "9372c470eeadd5ecd9c3c74c2b3cb633f8e2f2fad799250a0f70d652b6b825e4"
VIEW_SHA256 = "8f8cbb7dcf46e0bc7d53265749a6c17d116093a6ba95e442764060c76fd4a86c"


def write_complete_source(source: Path) -> None:
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
    (source / "files").mkdir(parents=True)
    (source / "files/model.glb").write_bytes(b"model")
    (source / "views").mkdir()
    for name in ("front", "back", "left", "right", "top", "isometric"):
        (source / f"views/{name}.png").write_bytes(b"png")
    (source / "snapshot.json").write_text(json.dumps(payload), encoding="utf-8")


def test_bundle_command_prints_machine_readable_result(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    write_complete_source(source)
    result = runner.invoke(app, ["bundle", str(source), str(output)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["trajectory_id"] == "trajectory-001"
    assert payload["status"] == "complete"


def test_audit_command_fails_on_tampered_bundle(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "checksums.sha256").write_text(f"{'0' * 64}  payload.json\n", encoding="utf-8")
    (bundle / "payload.json").write_text("{}\n", encoding="utf-8")
    result = runner.invoke(app, ["audit", str(bundle)])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["issues"] == ["bundle_checksum_incomplete"]


def test_audit_command_fails_cleanly_when_manifest_is_missing(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "checksums.sha256").write_text("", encoding="utf-8")
    result = runner.invoke(app, ["audit", str(bundle)])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["issues"] == ["bundle_checksum_incomplete"]


def test_complete_fixture_builds_clean_bundle(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["bundle", "tests/fixtures/source_complete", str(tmp_path / "bundles")],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "complete"
    assert payload["issues"] == []


def test_partial_fixture_preserves_content_quality_eligibility(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["bundle", "tests/fixtures/source_partial", str(tmp_path / "bundles")],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "partial"
    assert payload["issues"] == ["missing_round_simulator_call_record"]
