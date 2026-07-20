import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_eval.contracts import DataQualityStatus, load_source_snapshot
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
