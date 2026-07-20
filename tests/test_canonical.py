from pathlib import Path

from agent_eval.canonical import (
    canonical_json_bytes,
    verify_checksum_file,
    write_checksum_file,
)


def test_canonical_json_sorts_object_keys_but_not_arrays() -> None:
    left = {"z": [2, 1], "a": {"y": 2, "x": 1}}
    right = {"a": {"x": 1, "y": 2}, "z": [2, 1]}
    assert canonical_json_bytes(left) == canonical_json_bytes(right)
    assert canonical_json_bytes({"z": [1, 2]}) != canonical_json_bytes({"z": [2, 1]})


def test_checksum_manifest_detects_tampering(tmp_path: Path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text('{"ok":true}\n', encoding="utf-8")
    write_checksum_file(tmp_path, [payload])
    assert verify_checksum_file(tmp_path) == []
    payload.write_text('{"ok":false}\n', encoding="utf-8")
    assert verify_checksum_file(tmp_path) == ["payload.json"]


def test_checksum_manifest_rejects_unlisted_and_unsafe_paths(tmp_path: Path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text("{}\n", encoding="utf-8")
    write_checksum_file(tmp_path, [payload])
    (tmp_path / "unlisted.json").write_text("{}\n", encoding="utf-8")
    assert verify_checksum_file(tmp_path) == ["unlisted.json"]

    payload.unlink()
    (tmp_path / "unlisted.json").unlink()
    (tmp_path / "checksums.sha256").write_text(
        f"{'0' * 64}  ../outside.json\n",
        encoding="utf-8",
    )
    assert verify_checksum_file(tmp_path) == ["../outside.json"]
