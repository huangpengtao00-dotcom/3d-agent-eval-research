from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksum_file(root: Path, files: Iterable[Path]) -> Path:
    checksum_path = root / "checksums.sha256"
    lines = [
        f"{sha256_file(path)}  {path.relative_to(root).as_posix()}"
        for path in sorted(files, key=lambda item: item.relative_to(root).as_posix())
    ]
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return checksum_path


def verify_checksum_file(root: Path) -> list[str]:
    root = root.resolve()
    checksum_path = root / "checksums.sha256"
    if not checksum_path.is_file():
        return ["checksums.sha256"]
    failures: list[str] = []
    declared: set[str] = set()
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        parts = line.split("  ", maxsplit=1)
        if len(parts) != 2:
            failures.append("checksums.sha256")
            continue
        expected, relative_path = parts
        path = (root / relative_path).resolve()
        if (
            relative_path in declared
            or not path.is_relative_to(root)
            or not path.is_file()
            or sha256_file(path) != expected
        ):
            failures.append(relative_path)
        declared.add(relative_path)
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != checksum_path
    }
    failures.extend(sorted(actual - declared))
    return sorted(set(failures))
