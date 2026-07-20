import json
from pathlib import Path

from agent_eval.bundle import build_bundle
from agent_eval.canonical import verify_checksum_file
from agent_eval.contracts import DisclosureClass
from tests.helpers import minimum_snapshot


def test_build_bundle_freezes_source_and_bytes(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    (source / "files").mkdir(parents=True)
    (source / "files/model.glb").write_bytes(b"fixed-model-bytes")
    payload = minimum_snapshot()
    payload["steps"] = [
        {"step_id": "step-001", "turn_id": "turn-001", "payload": {"tool": "generate"}}
    ]
    payload["artifacts"] = [
        {
            "artifact_id": "artifact-001",
            "kind": "model",
            "relative_path": "files/model.glb",
            "media_type": "model/gltf-binary",
            "sha256": "f69215cbe5a2b0ed49bceb5c5e2effddc9ecb63cae968335e240a912f6a58e17",
            "byte_length": 17,
            "producing_turn_id": "turn-001",
            "producing_step_id": "step-001",
            "required": True,
        }
    ]
    (source / "snapshot.json").write_text(json.dumps(payload), encoding="utf-8")

    bundle = build_bundle(source, output, DisclosureClass.PRIVATE_REPRODUCIBLE)

    assert bundle.name == "trajectory-001"
    assert (bundle / "source/attempt.json").is_file()
    assert (bundle / "artifacts/originals/artifact-001.glb").is_file()
    assert (bundle / "artifacts/inventory.json").is_file()
    assert (bundle / "views/render_manifest.json").is_file()
    assert verify_checksum_file(bundle) == []
