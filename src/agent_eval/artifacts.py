from __future__ import annotations

import shutil
from collections.abc import Iterable
from pathlib import Path

from agent_eval.canonical import sha256_file
from agent_eval.contracts import ArtifactSource, FileRecord, StandardViewSource


class UnsafeSourcePath(ValueError):
    pass


class EvidenceHashMismatch(ValueError):
    pass


def resolve_source_path(root: Path, relative_path: str) -> Path:
    if Path(relative_path).is_absolute():
        raise UnsafeSourcePath(relative_path)
    root = root.resolve()
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root):
        raise UnsafeSourcePath(relative_path)
    return candidate


def _copy(
    source: Path,
    destination: Path,
    media_type: str,
    root: Path,
    expected_sha256: str,
    expected_byte_length: int,
) -> FileRecord:
    if source.stat().st_size != expected_byte_length or sha256_file(source) != expected_sha256:
        raise EvidenceHashMismatch(source.as_posix())
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return FileRecord(
        relative_path=destination.relative_to(root).as_posix(),
        sha256=sha256_file(destination),
        byte_length=destination.stat().st_size,
        media_type=media_type,
    )


def import_artifacts(
    source_root: Path,
    bundle_root: Path,
    artifacts: Iterable[ArtifactSource],
) -> list[FileRecord]:
    records: list[FileRecord] = []
    for artifact in artifacts:
        source = resolve_source_path(source_root, artifact.relative_path)
        suffix = source.suffix.lower()
        destination = bundle_root / "artifacts" / "originals" / f"{artifact.artifact_id}{suffix}"
        records.append(
            _copy(
                source,
                destination,
                artifact.media_type,
                bundle_root,
                artifact.sha256,
                artifact.byte_length,
            )
        )
    return records


def import_standard_views(
    source_root: Path,
    bundle_root: Path,
    views: Iterable[StandardViewSource],
) -> list[FileRecord]:
    records: list[FileRecord] = []
    for view in views:
        source = resolve_source_path(source_root, view.relative_path)
        suffix = source.suffix.lower()
        destination = (
            bundle_root / "views" / "standard" / view.artifact_id / f"{view.view_name}{suffix}"
        )
        records.append(
            _copy(
                source,
                destination,
                "image/png",
                bundle_root,
                view.sha256,
                view.byte_length,
            )
        )
    return records
