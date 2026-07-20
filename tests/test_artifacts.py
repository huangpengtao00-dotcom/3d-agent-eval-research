from pathlib import Path

import pytest

from agent_eval.artifacts import EvidenceHashMismatch, UnsafeSourcePath, import_artifacts
from agent_eval.contracts import ArtifactSource


def test_import_artifact_copies_bytes_and_records_hash(tmp_path: Path) -> None:
    source = tmp_path / "source"
    bundle = tmp_path / "bundle"
    (source / "files").mkdir(parents=True)
    (source / "files/model.glb").write_bytes(b"fixed-model-bytes")
    records = import_artifacts(
        source,
        bundle,
        [
            ArtifactSource(
                artifact_id="artifact-001",
                kind="model",
                relative_path="files/model.glb",
                media_type="model/gltf-binary",
                sha256="f69215cbe5a2b0ed49bceb5c5e2effddc9ecb63cae968335e240a912f6a58e17",
                byte_length=17,
                producing_turn_id="turn-001",
                producing_step_id="step-001",
            )
        ],
    )
    assert (bundle / "artifacts/originals/artifact-001.glb").read_bytes() == b"fixed-model-bytes"
    assert records[0].byte_length == 17


def test_import_rejects_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(UnsafeSourcePath):
        import_artifacts(
            tmp_path,
            tmp_path / "bundle",
            [
                ArtifactSource(
                    artifact_id="artifact-001",
                    kind="model",
                    relative_path="../secret.txt",
                    media_type="application/octet-stream",
                    sha256="0" * 64,
                    byte_length=0,
                    producing_turn_id="turn-001",
                    producing_step_id="step-001",
                )
            ],
        )


def test_import_rejects_bytes_that_do_not_match_source_inventory(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "files").mkdir(parents=True)
    (source / "files/model.glb").write_bytes(b"changed")
    artifact = ArtifactSource(
        artifact_id="artifact-001",
        kind="model",
        relative_path="files/model.glb",
        media_type="model/gltf-binary",
        sha256="0" * 64,
        byte_length=7,
        producing_turn_id="turn-001",
        producing_step_id="step-001",
    )
    with pytest.raises(EvidenceHashMismatch):
        import_artifacts(source, tmp_path / "bundle", [artifact])
