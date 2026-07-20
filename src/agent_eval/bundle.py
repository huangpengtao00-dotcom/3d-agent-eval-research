from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from agent_eval import __version__
from agent_eval.artifacts import (
    EvidenceHashMismatch,
    UnsafeSourcePath,
    import_artifacts,
    import_standard_views,
)
from agent_eval.audit import audit_snapshot
from agent_eval.canonical import (
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    write_checksum_file,
)
from agent_eval.contracts import (
    BundleManifest,
    DataQualityStatus,
    DisclosureClass,
    FileRecord,
    SourceSnapshot,
    load_source_snapshot,
)
from agent_eval.mapping import AmbiguousRoundTurnMapping, resolve_round_turns


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _write_jsonl(path: Path, values: Iterable[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(canonical_json_bytes(value) + b"\n" for value in values))


def _file_record(root: Path, path: Path, media_type: str) -> FileRecord:
    return FileRecord(
        relative_path=path.relative_to(root).as_posix(),
        sha256=sha256_file(path),
        byte_length=path.stat().st_size,
        media_type=media_type,
    )


def _import_available_evidence(
    source_root: Path,
    bundle: Path,
    snapshot: SourceSnapshot,
) -> list[FileRecord]:
    records: list[FileRecord] = []
    for artifact in snapshot.artifacts:
        try:
            records.extend(import_artifacts(source_root, bundle, [artifact]))
        except (EvidenceHashMismatch, FileNotFoundError, UnsafeSourcePath):
            continue
    for view in snapshot.standard_views:
        try:
            records.extend(import_standard_views(source_root, bundle, [view]))
        except (EvidenceHashMismatch, FileNotFoundError, UnsafeSourcePath):
            continue
    return records


def build_bundle(
    source_root: Path,
    output_root: Path,
    disclosure_class: DisclosureClass,
) -> Path:
    snapshot_path = source_root / "snapshot.json"
    snapshot = load_source_snapshot(snapshot_path)
    audit = audit_snapshot(snapshot, source_root)
    try:
        round_turns = resolve_round_turns(snapshot)
    except AmbiguousRoundTurnMapping:
        round_turns = None
    bundle = output_root / snapshot.trajectory_id
    if bundle.exists():
        raise FileExistsError(f"bundle already exists: {bundle}")
    bundle.mkdir(parents=True)

    normalized_rounds = [
        round_record
        if round_turns is None
        else round_record.model_copy(update={"turn_ids": list(round_turns[round_record.round_no])})
        for round_record in snapshot.rounds
    ]
    source_files: list[tuple[Path, str]] = [
        (bundle / "source/experiment.json", "application/json"),
        (bundle / "source/run.json", "application/json"),
        (bundle / "source/attempt.json", "application/json"),
        (bundle / "source/rounds.jsonl", "application/x-ndjson"),
        (bundle / "source/turns.jsonl", "application/x-ndjson"),
        (bundle / "source/steps.jsonl", "application/x-ndjson"),
        (bundle / "source/events.jsonl", "application/x-ndjson"),
        (bundle / "source/lineage.json", "application/json"),
    ]
    _write_json(source_files[0][0], snapshot.experiment.model_dump(mode="json"))
    _write_json(source_files[1][0], snapshot.run.model_dump(mode="json"))
    _write_json(source_files[2][0], snapshot.attempt.model_dump(mode="json"))
    _write_jsonl(source_files[3][0], (item.model_dump(mode="json") for item in normalized_rounds))
    _write_jsonl(source_files[4][0], (item.model_dump(mode="json") for item in snapshot.turns))
    _write_jsonl(source_files[5][0], (item.model_dump(mode="json") for item in snapshot.steps))
    _write_jsonl(source_files[6][0], (item.model_dump(mode="json") for item in snapshot.events))
    _write_json(
        source_files[7][0],
        [item.model_dump(mode="json") for item in snapshot.lineage],
    )

    inventory_path = bundle / "artifacts/inventory.json"
    render_manifest_path = bundle / "views/render_manifest.json"
    _write_json(
        inventory_path,
        [item.model_dump(mode="json") for item in snapshot.artifacts],
    )
    _write_json(
        render_manifest_path,
        [item.model_dump(mode="json") for item in snapshot.standard_views],
    )

    records = [_file_record(bundle, path, media_type) for path, media_type in source_files]
    records.extend(
        [
            _file_record(bundle, inventory_path, "application/json"),
            _file_record(bundle, render_manifest_path, "application/json"),
        ]
    )
    records.extend(_import_available_evidence(source_root, bundle, snapshot))

    audit_path = bundle / "quality" / "audit.json"
    _write_json(audit_path, audit.model_dump(mode="json"))
    records.append(_file_record(bundle, audit_path, "application/json"))

    manifest = BundleManifest(
        trajectory_id=snapshot.trajectory_id,
        source_schema_version=snapshot.schema_version,
        case_family_key=snapshot.case_family_key,
        split_group_key=snapshot.split_group_key,
        source_snapshot_at=snapshot.experiment.snapshot_at,
        source_snapshot_sha256=sha256_bytes(
            canonical_json_bytes(snapshot.model_dump(mode="json"))
        ),
        content_inventory_sha256=sha256_bytes(
            canonical_json_bytes([record.model_dump(mode="json") for record in records])
        ),
        agent_version=snapshot.run.agent_version,
        agent_config_digest=snapshot.run.agent_config_digest,
        toolset_digest=snapshot.run.toolset_digest,
        skill_digests=snapshot.run.skill_digests,
        simulator_config_sha256=sha256_bytes(canonical_json_bytes(snapshot.run.simulator)),
        exporter_version=__version__,
        exporter_parameters={"disclosure_class": disclosure_class.value},
        disclosure_class=disclosure_class,
        files=records,
        data_quality=audit,
    )
    manifest_path = bundle / "manifest.json"
    _write_json(manifest_path, manifest.model_dump(mode="json"))
    write_checksum_file(bundle, [path for path in bundle.rglob("*") if path.is_file()])
    if audit.status is DataQualityStatus.EXCLUDED:
        exclusion_path = output_root / "excluded" / f"{snapshot.trajectory_id}.json"
        _write_json(
            exclusion_path,
            {
                "trajectory_id": snapshot.trajectory_id,
                "source_snapshot_sha256": manifest.source_snapshot_sha256,
                "data_quality": audit.model_dump(mode="json"),
            },
        )
    return bundle
