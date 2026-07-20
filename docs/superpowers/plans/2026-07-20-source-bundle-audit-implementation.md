# Source Bundle and Data Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the source-neutral Phase A pipeline that imports one approved trajectory-attempt snapshot, freezes its records and artifacts into a checksum-covered evidence bundle, and assigns a machine-readable data-quality result.

**Architecture:** A private adapter outside this repository exports a source-neutral JSON directory that implements the public `SourceSnapshot` contract. This repository validates that directory, resolves round-to-turn identity, copies artifact and view bytes into an immutable bundle, computes checksums, and runs analysis-specific quality gates. The code never connects to a production database or contains proprietary identifiers.

**Tech Stack:** Python 3.12, uv, Pydantic 2, Typer, pytest, Ruff, mypy

## Global Constraints

- The upstream evaluation platform remains the sole execution source; this repository never drives the evaluated agent.
- The trajectory attempt is the unit of analysis; retries and repetitions remain distinct.
- Raw or restricted bundles live in access-controlled private storage and are ignored by git.
- Public code and fixtures contain no organization names, product names, internal issue IDs, repository names, hosts, URLs, table names, API paths, employee names, or credentials.
- Effective agent version, prompt/configuration digest, tool-set digest, skill-content digests, experiment snapshot hash, and dataset hash are mandatory for a complete main-experiment bundle.
- Round-to-turn mapping must be explicit or uniquely reconstructed; ambiguous mappings are excluded rather than guessed.
- Artifact and standardized-view bytes are copied into the bundle and covered by SHA-256 checksums.
- Simulator termination labels, gold annotations, and production weak labels never enter judge-visible projections.
- `missing_round_simulator_call_record` produces `partial` for content-quality analysis and excludes simulator cost/latency analysis; it is not an agent failure.
- Implementation follows TDD and commits after each independently testable task.
- Phase A does not implement human annotation, automatic judges, calibration, 3D rendering, production write-back, or paper statistics. Those receive separate implementation plans after this phase passes review.

---

## File Structure

```text
pyproject.toml                         # Python package, tools, and dependencies
.gitignore                             # Blocks private bundles and local research data
src/agent_eval/__init__.py             # Package version
src/agent_eval/contracts.py            # Strict source and bundle schemas
src/agent_eval/canonical.py            # Canonical JSON and SHA-256 helpers
src/agent_eval/mapping.py              # Deterministic round-to-turn resolution
src/agent_eval/artifacts.py            # Safe byte import and artifact inventories
src/agent_eval/bundle.py               # Immutable bundle assembly
src/agent_eval/audit.py                # Quality gates and analysis eligibility
src/agent_eval/cli.py                  # `agent-eval bundle` and `agent-eval audit`
tests/fixtures/source_complete/         # Synthetic approved source snapshot
tests/fixtures/source_partial/          # Synthetic simulator-call inconsistency
tests/__init__.py
tests/helpers.py                        # Shared synthetic snapshot factory
tests/test_contracts.py
tests/test_canonical.py
tests/test_mapping.py
tests/test_artifacts.py
tests/test_bundle.py
tests/test_audit.py
tests/test_cli.py
docs/source-export-contract.md          # Source-neutral handoff documentation
```

Private source adapters are not files in this repository. They must emit the documented directory contract and run inside the approved source environment.

---

### Task 1: Bootstrap the Public Research Package

**Files:**

- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/agent_eval/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_package.py`

**Interfaces:**

- Consumes: Python 3.12 and uv.
- Produces: importable package `agent_eval`, console entry point `agent-eval`, and standard verification commands used by every later task.

- [ ] **Step 1: Write the failing package smoke test**

```python
# tests/test_package.py
from agent_eval import __version__


def test_package_version_is_explicit() -> None:
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Run the smoke test and verify the package is absent**

Run:

```bash
uv run pytest tests/test_package.py -q
```

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'agent_eval'`.

- [ ] **Step 3: Add package metadata and tool configuration**

```toml
# pyproject.toml
[project]
name = "evidence-grounded-3d-agent-eval"
version = "0.1.0"
description = "Source-neutral research pipeline for evidence-grounded 3D agent evaluation"
requires-python = ">=3.12"
dependencies = [
  "pydantic>=2.11,<3",
  "typer>=0.16,<1",
]

[project.scripts]
agent-eval = "agent_eval.cli:app"

[dependency-groups]
dev = [
  "mypy>=1.17,<2",
  "pytest>=8.4,<9",
  "ruff>=0.12,<1",
]

[build-system]
requires = ["hatchling>=1.27"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/agent_eval"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.12"
strict = true
packages = ["agent_eval"]
```

```python
# src/agent_eval/__init__.py
__version__ = "0.1.0"
```

Create an empty `tests/__init__.py` so test helpers have one unambiguous import path.

```gitignore
# .gitignore
.worktrees/
.venv/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
dist/
build/

# Raw and restricted research data must stay in access-controlled storage.
data/private/
bundles/
excluded/
*.secrets.json
```

- [ ] **Step 4: Sync dependencies and run the package smoke test**

Run:

```bash
uv sync
uv run pytest tests/test_package.py -q
```

Expected: PASS with `1 passed`.

- [ ] **Step 5: Run static verification**

Run:

```bash
uv run ruff check .
uv run mypy src
```

Expected: both commands exit 0.

- [ ] **Step 6: Commit the bootstrap**

```bash
git add pyproject.toml uv.lock .gitignore src/agent_eval/__init__.py tests/__init__.py tests/test_package.py
git commit -m "build: bootstrap research data package"
```

---

### Task 2: Define Strict Source and Bundle Contracts

**Files:**

- Create: `src/agent_eval/contracts.py`
- Create: `tests/helpers.py`
- Create: `tests/test_contracts.py`

**Interfaces:**

- Consumes: Pydantic 2.
- Produces: `SourceSnapshot`, `ArtifactSource`, `StandardViewSource`, `BundleManifest`, `AuditResult`, `load_source_snapshot(path)`.

- [ ] **Step 1: Write contract tests for a complete source snapshot and unknown-field rejection**

```python
# tests/helpers.py
def minimum_snapshot() -> dict[str, object]:
    return {
        "schema_version": 1,
        "trajectory_id": "trajectory-001",
        "case_family_key": "printable-character",
        "split_group_key": "family-001",
        "experiment": {
            "snapshot_hash": "a" * 64,
            "dataset_content_hash": "b" * 64,
            "snapshot_at": "2026-01-01T00:00:00Z",
            "case_spec": {"goal": "Create a printable character"},
        },
        "run": {
            "agent_version": "1.2.3",
            "agent_config_digest": "c" * 64,
            "toolset_digest": "d" * 64,
            "skill_digests": {"printability": "e" * 64},
            "simulator": {"model": "simulator-model", "temperature": 0.0},
        },
        "attempt": {
            "attempt_id": "attempt-001",
            "attempt_no": 1,
            "thread_id": "thread-001",
            "state": "succeeded",
            "termination_reason": "goal_achieved",
            "source_quality_issues": [],
        },
        "rounds": [
            {
                "round_no": 1,
                "submitted_blocks": [{"type": "text", "text": "Create it"}],
                "turn_ids": ["turn-001"],
                "observations": [],
                "simulator_calls": [],
            }
        ],
        "turns": [
            {
                "turn_id": "turn-001",
                "idempotency_key": "attempt-001:r1",
                "state": "succeeded",
            }
        ],
        "steps": [],
        "events": [],
        "lineage": [],
        "artifacts": [],
        "standard_views": [],
    }
```

```python
# tests/test_contracts.py
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
```

- [ ] **Step 2: Run the tests and verify the contracts do not exist**

Run:

```bash
uv run pytest tests/test_contracts.py -q
```

Expected: FAIL during collection because `agent_eval.contracts` does not exist.

- [ ] **Step 3: Implement the strict contracts**

```python
# src/agent_eval/contracts.py
from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SafeIdentifier = Annotated[
    str,
    Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"),
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DataQualityStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    EXCLUDED = "excluded"


class DisclosureClass(StrEnum):
    PUBLIC = "public"
    DERIVED_PUBLIC = "derived_public"
    PRIVATE_REPRODUCIBLE = "private_reproducible"
    RESTRICTED = "restricted"


class AuditIssueCode(StrEnum):
    AUDIT_NOT_RUN = "audit_not_run"
    MISSING_EXPLICIT_AGENT_VERSION = "missing_explicit_agent_version"
    MISSING_AGENT_CONFIG_DIGEST = "missing_agent_config_digest"
    MISSING_EXPERIMENT_SNAPSHOT = "missing_experiment_snapshot"
    AMBIGUOUS_ROUND_TURN_MAPPING = "ambiguous_round_turn_mapping"
    MISSING_REQUIRED_ARTIFACT = "missing_required_artifact"
    ARTIFACT_HASH_MISMATCH = "artifact_hash_mismatch"
    BROKEN_ARTIFACT_LINEAGE = "broken_artifact_lineage"
    STANDARD_VIEW_GENERATION_FAILED = "standard_view_generation_failed"
    LABEL_LEAKAGE_IN_JUDGE_INPUT = "label_leakage_in_judge_input"
    UNAPPROVED_USER_DATA = "unapproved_user_data"
    BUNDLE_CHECKSUM_INCOMPLETE = "bundle_checksum_incomplete"
    UNSUPPORTED_SOURCE_SCHEMA = "unsupported_source_schema"
    MISSING_ROUND_SIMULATOR_CALL_RECORD = "missing_round_simulator_call_record"
    INVALID_EVIDENCE_REFERENCE = "invalid_evidence_reference"
    UNSUPPORTED_ARTIFACT_FORMAT = "unsupported_artifact_format"


class ExperimentSnapshot(StrictModel):
    snapshot_hash: Sha256 | None = None
    dataset_content_hash: Sha256 | None = None
    snapshot_at: datetime
    case_spec: dict[str, Any]


class RunSnapshot(StrictModel):
    agent_version: str | None = Field(default=None, min_length=1)
    agent_config_digest: Sha256 | None = None
    toolset_digest: Sha256 | None = None
    skill_digests: dict[str, Sha256]
    simulator: dict[str, Any]
    random_seed: int | None = None


class AttemptSnapshot(StrictModel):
    attempt_id: str = Field(min_length=1)
    attempt_no: int = Field(ge=1)
    thread_id: str = Field(min_length=1)
    state: str = Field(min_length=1)
    termination_reason: str = Field(min_length=1)
    source_quality_issues: list[AuditIssueCode] = Field(default_factory=list)


class RoundSnapshot(StrictModel):
    round_no: int = Field(ge=1)
    submitted_blocks: list[dict[str, Any]]
    turn_ids: list[str] = Field(default_factory=list)
    observations: list[dict[str, Any]]
    simulator_calls: list[dict[str, Any]]


class TurnSnapshot(StrictModel):
    turn_id: str = Field(min_length=1)
    idempotency_key: str | None = None
    state: str = Field(min_length=1)


class StepSnapshot(StrictModel):
    step_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    payload: dict[str, Any]


class EventSnapshot(StrictModel):
    event_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    order_key: int = Field(ge=0)
    payload: dict[str, Any]


class LineageEdge(StrictModel):
    parent_id: str = Field(min_length=1)
    child_id: str = Field(min_length=1)
    relation: str = Field(min_length=1)


class ArtifactSource(StrictModel):
    artifact_id: SafeIdentifier
    kind: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    sha256: Sha256
    byte_length: int = Field(ge=0)
    producing_turn_id: str = Field(min_length=1)
    producing_step_id: str = Field(min_length=1)
    required: bool = True


class StandardViewSource(StrictModel):
    artifact_id: SafeIdentifier
    view_name: SafeIdentifier
    relative_path: str = Field(min_length=1)
    source_artifact_sha256: Sha256
    sha256: Sha256
    byte_length: int = Field(ge=0)
    renderer: str = Field(min_length=1)
    renderer_version: str = Field(min_length=1)
    parameters: dict[str, Any]


class SourceSnapshot(StrictModel):
    schema_version: int = Field(ge=1)
    trajectory_id: SafeIdentifier
    case_family_key: str = Field(min_length=1)
    split_group_key: str = Field(min_length=1)
    experiment: ExperimentSnapshot
    run: RunSnapshot
    attempt: AttemptSnapshot
    rounds: list[RoundSnapshot]
    turns: list[TurnSnapshot]
    steps: list[StepSnapshot]
    events: list[EventSnapshot]
    lineage: list[LineageEdge]
    artifacts: list[ArtifactSource]
    standard_views: list[StandardViewSource]


class FileRecord(StrictModel):
    relative_path: str
    sha256: Sha256
    byte_length: int = Field(ge=0)
    media_type: str


class AuditResult(StrictModel):
    status: DataQualityStatus
    issues: list[AuditIssueCode]
    eligible_analyses: list[str]


class BundleManifest(StrictModel):
    bundle_schema_version: int = 1
    trajectory_id: SafeIdentifier
    source_schema_version: int
    case_family_key: str
    split_group_key: str
    source_snapshot_at: datetime
    source_snapshot_sha256: Sha256
    content_inventory_sha256: Sha256
    agent_version: str | None
    agent_config_digest: Sha256 | None
    toolset_digest: Sha256 | None
    skill_digests: dict[str, Sha256]
    simulator_config_sha256: Sha256
    exporter_version: str
    exporter_parameters: dict[str, Any]
    disclosure_class: DisclosureClass
    files: list[FileRecord]
    data_quality: AuditResult


def load_source_snapshot(path: Path) -> SourceSnapshot:
    return SourceSnapshot.model_validate(json.loads(path.read_text(encoding="utf-8")))
```

- [ ] **Step 4: Run contract tests**

Run:

```bash
uv run pytest tests/test_contracts.py -q
uv run mypy src
```

Expected: tests pass and mypy exits 0.

- [ ] **Step 5: Commit the contracts**

```bash
git add src/agent_eval/contracts.py tests/helpers.py tests/test_contracts.py
git commit -m "feat: define source-neutral snapshot contracts"
```

---

### Task 3: Implement Canonical JSON and Checksum Verification

**Files:**

- Create: `src/agent_eval/canonical.py`
- Create: `tests/test_canonical.py`

**Interfaces:**

- Consumes: JSON-compatible values and filesystem paths.
- Produces: `canonical_json_bytes(value)`, `sha256_bytes(data)`, `sha256_file(path)`, `write_checksum_file(root, files)`, `verify_checksum_file(root)`.

- [ ] **Step 1: Write failing determinism and tamper-detection tests**

```python
# tests/test_canonical.py
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
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/test_canonical.py -q
```

Expected: FAIL because `agent_eval.canonical` does not exist.

- [ ] **Step 3: Implement canonical serialization and checksums**

```python
# src/agent_eval/canonical.py
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


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
```

- [ ] **Step 4: Run checksum tests and static checks**

Run:

```bash
uv run pytest tests/test_canonical.py -q
uv run ruff check src/agent_eval/canonical.py tests/test_canonical.py
uv run mypy src
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit checksum support**

```bash
git add src/agent_eval/canonical.py tests/test_canonical.py
git commit -m "feat: add canonical serialization and checksums"
```

---

### Task 4: Resolve Round-to-Turn Identity Without Guessing

**Files:**

- Create: `src/agent_eval/mapping.py`
- Create: `tests/test_mapping.py`

**Interfaces:**

- Consumes: `SourceSnapshot`.
- Produces: `resolve_round_turns(snapshot) -> dict[int, tuple[str, ...]]` and `AmbiguousRoundTurnMapping`.

- [ ] **Step 1: Write tests for explicit, reconstructed, and ambiguous mappings**

```python
# tests/test_mapping.py
import pytest

from agent_eval.contracts import RoundSnapshot, SourceSnapshot, TurnSnapshot
from agent_eval.mapping import AmbiguousRoundTurnMapping, resolve_round_turns
from tests.helpers import minimum_snapshot


def snapshot() -> SourceSnapshot:
    return SourceSnapshot.model_validate(minimum_snapshot())


def test_explicit_round_turn_mapping_wins() -> None:
    assert resolve_round_turns(snapshot()) == {1: ("turn-001",)}


def test_unique_idempotency_key_reconstructs_mapping() -> None:
    source = snapshot()
    rounds = [RoundSnapshot.model_validate({**source.rounds[0].model_dump(), "turn_ids": []})]
    rebuilt = source.model_copy(update={"rounds": rounds})
    assert resolve_round_turns(rebuilt) == {1: ("turn-001",)}


def test_ambiguous_mapping_is_rejected() -> None:
    source = snapshot()
    rounds = [RoundSnapshot.model_validate({**source.rounds[0].model_dump(), "turn_ids": []})]
    turns = [
        TurnSnapshot(turn_id="turn-a", idempotency_key="attempt-001:r1", state="failed"),
        TurnSnapshot(turn_id="turn-b", idempotency_key="attempt-001:r1", state="succeeded"),
    ]
    rebuilt = source.model_copy(update={"rounds": rounds, "turns": turns})
    with pytest.raises(AmbiguousRoundTurnMapping):
        resolve_round_turns(rebuilt)


def test_duplicate_round_numbers_are_rejected() -> None:
    source = snapshot()
    rebuilt = source.model_copy(update={"rounds": [source.rounds[0], source.rounds[0]]})
    with pytest.raises(AmbiguousRoundTurnMapping):
        resolve_round_turns(rebuilt)
```

- [ ] **Step 2: Run mapping tests and verify failure**

Run:

```bash
uv run pytest tests/test_mapping.py -q
```

Expected: FAIL because `agent_eval.mapping` does not exist.

- [ ] **Step 3: Implement deterministic mapping**

```python
# src/agent_eval/mapping.py
from __future__ import annotations

from agent_eval.contracts import SourceSnapshot


class AmbiguousRoundTurnMapping(ValueError):
    pass


def resolve_round_turns(snapshot: SourceSnapshot) -> dict[int, tuple[str, ...]]:
    known_turns = {turn.turn_id for turn in snapshot.turns}
    resolved: dict[int, tuple[str, ...]] = {}
    claimed_turns: set[str] = set()
    for round_record in snapshot.rounds:
        if round_record.round_no in resolved:
            raise AmbiguousRoundTurnMapping(
                f"duplicate round number {round_record.round_no}"
            )
        if round_record.turn_ids:
            turn_ids = tuple(round_record.turn_ids)
            if (
                len(set(turn_ids)) != len(turn_ids)
                or not set(turn_ids) <= known_turns
                or not set(turn_ids).isdisjoint(claimed_turns)
            ):
                raise AmbiguousRoundTurnMapping(f"round {round_record.round_no} has invalid turn ids")
            resolved[round_record.round_no] = turn_ids
            claimed_turns.update(turn_ids)
            continue

        expected_key = f"{snapshot.attempt.attempt_id}:r{round_record.round_no}"
        candidates = tuple(
            turn.turn_id for turn in snapshot.turns if turn.idempotency_key == expected_key
        )
        if len(candidates) != 1:
            raise AmbiguousRoundTurnMapping(
                f"round {round_record.round_no} resolves to {len(candidates)} turns"
            )
        if not set(candidates).isdisjoint(claimed_turns):
            raise AmbiguousRoundTurnMapping(
                f"round {round_record.round_no} reuses an already claimed turn"
            )
        resolved[round_record.round_no] = candidates
        claimed_turns.update(candidates)
    return resolved
```

- [ ] **Step 4: Correct the test import and run all mapping tests**

Replace the unused `dataclasses` import in `tests/test_mapping.py` with no import, then run:

```bash
uv run pytest tests/test_contracts.py tests/test_mapping.py -q
uv run ruff check src/agent_eval/mapping.py tests/test_mapping.py
```

Expected: all tests pass and Ruff exits 0.

- [ ] **Step 5: Commit mapping resolution**

```bash
git add src/agent_eval/mapping.py tests/test_mapping.py
git commit -m "feat: resolve round to turn identity"
```

---

### Task 5: Import Artifact and Standard-View Bytes Safely

**Files:**

- Create: `src/agent_eval/artifacts.py`
- Create: `tests/test_artifacts.py`

**Interfaces:**

- Consumes: source directory, bundle directory, `ArtifactSource`, `StandardViewSource`.
- Produces: `resolve_source_path(...) -> Path`, `import_artifacts(...) -> list[FileRecord]`, `import_standard_views(...) -> list[FileRecord]`, `UnsafeSourcePath`, and `EvidenceHashMismatch`.

- [ ] **Step 1: Write tests for copying, hashing, and path traversal rejection**

```python
# tests/test_artifacts.py
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
```

- [ ] **Step 2: Run artifact tests and verify failure**

Run:

```bash
uv run pytest tests/test_artifacts.py -q
```

Expected: FAIL because `agent_eval.artifacts` does not exist.

- [ ] **Step 3: Implement safe byte import**

```python
# src/agent_eval/artifacts.py
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

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
```

- [ ] **Step 4: Run artifact tests and type checks**

Run:

```bash
uv run pytest tests/test_artifacts.py -q
uv run ruff check src/agent_eval/artifacts.py tests/test_artifacts.py
uv run mypy src
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit artifact import**

```bash
git add src/agent_eval/artifacts.py tests/test_artifacts.py
git commit -m "feat: import checksum-covered evidence bytes"
```

---

### Task 6: Assemble an Immutable Evidence Bundle

**Files:**

- Create: `src/agent_eval/bundle.py`
- Create: `tests/test_bundle.py`

**Interfaces:**

- Consumes: source directory, validated `SourceSnapshot`, resolved round mapping.
- Produces: `build_bundle(source_root, output_root, disclosure_class) -> Path` containing source records, artifacts, views, manifest, and `checksums.sha256`.

- [ ] **Step 1: Write a failing end-to-end bundle test**

```python
# tests/test_bundle.py
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
```

- [ ] **Step 2: Run the bundle test and verify failure**

Run:

```bash
uv run pytest tests/test_bundle.py -q
```

Expected: FAIL because `agent_eval.bundle` does not exist.

- [ ] **Step 3: Implement deterministic bundle assembly**

```python
# src/agent_eval/bundle.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from agent_eval import __version__
from agent_eval.artifacts import import_artifacts, import_standard_views
from agent_eval.canonical import canonical_json_bytes, sha256_bytes, sha256_file, write_checksum_file
from agent_eval.contracts import (
    AuditResult,
    BundleManifest,
    DataQualityStatus,
    DisclosureClass,
    FileRecord,
    SourceSnapshot,
    load_source_snapshot,
)
from agent_eval.mapping import resolve_round_turns


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


def build_bundle(
    source_root: Path,
    output_root: Path,
    disclosure_class: DisclosureClass,
) -> Path:
    snapshot_path = source_root / "snapshot.json"
    snapshot = load_source_snapshot(snapshot_path)
    round_turns = resolve_round_turns(snapshot)
    bundle = output_root / snapshot.trajectory_id
    if bundle.exists():
        raise FileExistsError(f"bundle already exists: {bundle}")
    bundle.mkdir(parents=True)

    normalized_rounds = [
        round_record.model_copy(update={"turn_ids": list(round_turns[round_record.round_no])})
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
    records.extend(import_artifacts(source_root, bundle, snapshot.artifacts))
    records.extend(import_standard_views(source_root, bundle, snapshot.standard_views))

    provisional = BundleManifest(
        trajectory_id=snapshot.trajectory_id,
        source_schema_version=snapshot.schema_version,
        case_family_key=snapshot.case_family_key,
        split_group_key=snapshot.split_group_key,
        source_snapshot_at=snapshot.experiment.snapshot_at,
        source_snapshot_sha256=sha256_bytes(canonical_json_bytes(snapshot.model_dump(mode="json"))),
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
        data_quality=AuditResult(
            status=DataQualityStatus.PARTIAL,
            issues=["audit_not_run"],
            eligible_analyses=[],
        ),
    )
    manifest_path = bundle / "manifest.json"
    _write_json(manifest_path, provisional.model_dump(mode="json"))
    write_checksum_file(bundle, [path for path in bundle.rglob("*") if path.is_file()])
    return bundle
```

- [ ] **Step 4: Run bundle and checksum tests**

Run:

```bash
uv run pytest tests/test_bundle.py tests/test_canonical.py -q
uv run ruff check src/agent_eval/bundle.py tests/test_bundle.py
uv run mypy src
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit bundle assembly**

```bash
git add src/agent_eval/bundle.py tests/test_bundle.py
git commit -m "feat: assemble immutable evidence bundles"
```

---

### Task 7: Implement Analysis-Specific Data Quality Audits

**Files:**

- Create: `src/agent_eval/audit.py`
- Create: `tests/test_audit.py`
- Modify: `src/agent_eval/bundle.py`

**Interfaces:**

- Consumes: bundle directory and validated source snapshot.
- Produces: `audit_snapshot(snapshot, source_root) -> AuditResult`, updated `manifest.json`, `quality/audit.json`, and a machine-readable exclusion record for excluded attempts.

- [ ] **Step 1: Write failing tests for complete, partial, and excluded outcomes**

```python
# tests/test_audit.py
from pathlib import Path

from agent_eval.audit import audit_snapshot
from agent_eval.contracts import DataQualityStatus, SourceSnapshot
from tests.helpers import minimum_snapshot


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
            "sha256": "9372c470eeadd5ecd9c3c74c2b3cb633f8e2f2fad799250a0f70d652b6b825e4",
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
            "source_artifact_sha256": "9372c470eeadd5ecd9c3c74c2b3cb633f8e2f2fad799250a0f70d652b6b825e4",
            "sha256": "8f8cbb7dcf46e0bc7d53265749a6c17d116093a6ba95e442764060c76fd4a86c",
            "byte_length": 3,
            "renderer": "fixed-renderer",
            "renderer_version": "1.0.0",
            "parameters": {"projection": "perspective"},
        }
        for name in ("front", "back", "left", "right", "top", "isometric")
    ]
    return SourceSnapshot.model_validate(payload)


def test_complete_snapshot_is_eligible_for_main_analyses(tmp_path: Path) -> None:
    source = snapshot()
    (tmp_path / "files").mkdir()
    (tmp_path / "files/model.glb").write_bytes(b"model")
    (tmp_path / "views").mkdir()
    for view in source.standard_views:
        (tmp_path / view.relative_path).write_bytes(b"png")
    result = audit_snapshot(source, tmp_path)
    assert result.status is DataQualityStatus.COMPLETE
    assert "content_quality" in result.eligible_analyses
    assert "simulator_cost_latency" in result.eligible_analyses


def test_missing_round_call_is_partial_only_for_cost_analysis(tmp_path: Path) -> None:
    source = snapshot()
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
```

- [ ] **Step 2: Run audit tests and verify failure**

Run:

```bash
uv run pytest tests/test_audit.py -q
```

Expected: FAIL because `agent_eval.audit` does not exist.

- [ ] **Step 3: Implement the quality gates**

```python
# src/agent_eval/audit.py
from __future__ import annotations

from pathlib import Path

from agent_eval.artifacts import UnsafeSourcePath, resolve_source_path
from agent_eval.canonical import sha256_file
from agent_eval.contracts import AuditIssueCode, AuditResult, DataQualityStatus, SourceSnapshot
from agent_eval.mapping import AmbiguousRoundTurnMapping, resolve_round_turns

REQUIRED_VIEWS = {"front", "back", "left", "right", "top", "isometric"}


def audit_snapshot(snapshot: SourceSnapshot, source_root: Path) -> AuditResult:
    fatal: list[AuditIssueCode] = []
    partial: list[AuditIssueCode] = []

    if snapshot.schema_version != 1:
        fatal.append(AuditIssueCode.UNSUPPORTED_SOURCE_SCHEMA)
    if not snapshot.run.agent_version:
        fatal.append(AuditIssueCode.MISSING_EXPLICIT_AGENT_VERSION)
    if (
        not snapshot.run.agent_config_digest
        or not snapshot.run.toolset_digest
        or not snapshot.run.skill_digests
    ):
        fatal.append(AuditIssueCode.MISSING_AGENT_CONFIG_DIGEST)
    if not snapshot.experiment.snapshot_hash or not snapshot.experiment.dataset_content_hash:
        fatal.append(AuditIssueCode.MISSING_EXPERIMENT_SNAPSHOT)
    try:
        resolve_round_turns(snapshot)
    except AmbiguousRoundTurnMapping:
        fatal.append(AuditIssueCode.AMBIGUOUS_ROUND_TURN_MAPPING)

    step_ids = {step.step_id for step in snapshot.steps}
    turn_ids = {turn.turn_id for turn in snapshot.turns}
    lineage_pairs = {(edge.parent_id, edge.child_id) for edge in snapshot.lineage}
    for artifact in snapshot.artifacts:
        try:
            artifact_path = resolve_source_path(source_root, artifact.relative_path)
        except UnsafeSourcePath:
            artifact_path = None
        if artifact.required and (artifact_path is None or not artifact_path.is_file()):
            fatal.append(AuditIssueCode.MISSING_REQUIRED_ARTIFACT)
        elif artifact_path is not None and (
            artifact_path.stat().st_size != artifact.byte_length
            or sha256_file(artifact_path) != artifact.sha256
        ):
            fatal.append(AuditIssueCode.ARTIFACT_HASH_MISMATCH)
        if artifact.producing_step_id not in step_ids or artifact.producing_turn_id not in turn_ids:
            fatal.append(AuditIssueCode.BROKEN_ARTIFACT_LINEAGE)
        if (artifact.producing_step_id, artifact.artifact_id) not in lineage_pairs:
            fatal.append(AuditIssueCode.BROKEN_ARTIFACT_LINEAGE)

    artifact_hashes = {artifact.artifact_id: artifact.sha256 for artifact in snapshot.artifacts}
    views_by_artifact: dict[str, set[str]] = {}
    for view in snapshot.standard_views:
        try:
            view_path = resolve_source_path(source_root, view.relative_path)
        except UnsafeSourcePath:
            view_path = None
        if view_path is None or not view_path.is_file():
            fatal.append(AuditIssueCode.STANDARD_VIEW_GENERATION_FAILED)
        elif (
            view_path.stat().st_size != view.byte_length
            or sha256_file(view_path) != view.sha256
        ):
            fatal.append(AuditIssueCode.STANDARD_VIEW_GENERATION_FAILED)
        if artifact_hashes.get(view.artifact_id) != view.source_artifact_sha256:
            fatal.append(AuditIssueCode.ARTIFACT_HASH_MISMATCH)
        views_by_artifact.setdefault(view.artifact_id, set()).add(view.view_name)
    for artifact in snapshot.artifacts:
        if artifact.kind == "model" and not REQUIRED_VIEWS <= views_by_artifact.get(
            artifact.artifact_id, set()
        ):
            fatal.append(AuditIssueCode.STANDARD_VIEW_GENERATION_FAILED)

    if AuditIssueCode.MISSING_ROUND_SIMULATOR_CALL_RECORD in snapshot.attempt.source_quality_issues:
        partial.append(AuditIssueCode.MISSING_ROUND_SIMULATOR_CALL_RECORD)

    fatal = sorted(set(fatal))
    partial = sorted(set(partial))
    if fatal:
        return AuditResult(
            status=DataQualityStatus.EXCLUDED,
            issues=fatal + partial,
            eligible_analyses=[],
        )
    analyses = ["content_quality", "failure_attribution", "agent_version_ranking"]
    if not partial:
        analyses.append("simulator_cost_latency")
    return AuditResult(
        status=DataQualityStatus.PARTIAL if partial else DataQualityStatus.COMPLETE,
        issues=partial,
        eligible_analyses=analyses,
    )
```

- [ ] **Step 4: Fix the partial test so non-target gates remain valid**

In `test_missing_round_call_is_partial_only_for_cost_analysis`, create the same artifact and six view files used by the complete test before calling `audit_snapshot`. Do not weaken the audit function to make a malformed fixture pass.

- [ ] **Step 5: Integrate audit output into bundle assembly**

Add these imports to `src/agent_eval/bundle.py`:

```python
from agent_eval.artifacts import EvidenceHashMismatch, UnsafeSourcePath
from agent_eval.audit import audit_snapshot
from agent_eval.mapping import AmbiguousRoundTurnMapping
```

Remove `AuditResult` from the `agent_eval.contracts` import because bundle assembly no longer fabricates a provisional audit result.

Add a helper that copies every readable, safe evidence file while leaving every omission visible in the audit record:

```python
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
```

Run the audit before mapping normalization or evidence import can raise. Replace the start of `build_bundle` through `normalized_rounds` with:

```python
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
        else round_record.model_copy(
            update={"turn_ids": list(round_turns[round_record.round_no])}
        )
        for round_record in snapshot.rounds
    ]
```

Replace the two bulk import calls with:

```python
    records.extend(_import_available_evidence(source_root, bundle, snapshot))
```

Set `data_quality=audit`, then write a second copy before the manifest:

```python
    audit_path = bundle / "quality" / "audit.json"
    _write_json(audit_path, audit.model_dump(mode="json"))
    records.append(_file_record(bundle, audit_path, "application/json"))
```

After writing the bundle checksum, persist a sibling exclusion index entry when required. The record is deliberately outside the immutable bundle and points back to its frozen source hash:

```python
    if audit.status is DataQualityStatus.EXCLUDED:
        exclusion_path = output_root / "excluded" / f"{snapshot.trajectory_id}.json"
        _write_json(
            exclusion_path,
            {
                "trajectory_id": snapshot.trajectory_id,
                "source_snapshot_sha256": provisional.source_snapshot_sha256,
                "data_quality": audit.model_dump(mode="json"),
            },
        )
```

Do not catch schema-validation errors in this function: malformed source that cannot establish a safe trajectory identity fails closed before a bundle path is created. Valid but analysis-ineligible snapshots produce an excluded bundle and exclusion index record.

Add this regression test to `tests/test_bundle.py` so missing evidence cannot regress to an uncaught copy error:

```python
def test_missing_artifact_builds_excluded_bundle_and_index(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
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
            "relative_path": "files/missing.glb",
            "media_type": "model/gltf-binary",
            "sha256": "0" * 64,
            "byte_length": 0,
            "producing_turn_id": "turn-001",
            "producing_step_id": "step-001",
            "required": True,
        }
    ]
    (source / "snapshot.json").write_text(json.dumps(payload), encoding="utf-8")

    bundle = build_bundle(source, output, DisclosureClass.PRIVATE_REPRODUCIBLE)

    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["data_quality"]["status"] == "excluded"
    assert "missing_required_artifact" in manifest["data_quality"]["issues"]
    assert (output / "excluded/trajectory-001.json").is_file()
    assert verify_checksum_file(bundle) == []
```

- [ ] **Step 6: Run audit and bundle tests**

Run:

```bash
uv run pytest tests/test_audit.py tests/test_bundle.py -q
uv run ruff check src tests
uv run mypy src
```

Expected: all commands exit 0.

- [ ] **Step 7: Commit the audit engine**

```bash
git add src/agent_eval/audit.py src/agent_eval/bundle.py tests/test_audit.py tests/test_bundle.py
git commit -m "feat: audit trajectory evidence quality"
```

---

### Task 8: Add Safe Build and Audit CLI Commands

**Files:**

- Create: `src/agent_eval/cli.py`
- Create: `tests/test_cli.py`

**Interfaces:**

- Consumes: source directory or bundle directory supplied by the operator.
- Produces: `agent-eval bundle SOURCE OUTPUT`, `agent-eval audit BUNDLE`, stable JSON output, and nonzero exit codes for excluded or tampered bundles.

- [ ] **Step 1: Write failing CLI tests**

```python
# tests/test_cli.py
import json
from pathlib import Path

from typer.testing import CliRunner

from agent_eval.cli import app
from tests.helpers import minimum_snapshot

runner = CliRunner()


def test_bundle_command_prints_machine_readable_result(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    (source / "snapshot.json").write_text(json.dumps(minimum_snapshot()), encoding="utf-8")
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
```

- [ ] **Step 2: Run CLI tests and verify failure**

Run:

```bash
uv run pytest tests/test_cli.py -q
```

Expected: FAIL because `agent_eval.cli` does not exist.

- [ ] **Step 3: Implement the CLI**

```python
# src/agent_eval/cli.py
from __future__ import annotations

import json
from pathlib import Path

import typer

from agent_eval.bundle import build_bundle
from agent_eval.canonical import verify_checksum_file
from agent_eval.contracts import BundleManifest, DisclosureClass

app = typer.Typer(no_args_is_help=True)


@app.command()
def bundle(source: Path, output: Path) -> None:
    bundle_path = build_bundle(source, output, DisclosureClass.PRIVATE_REPRODUCIBLE)
    manifest = BundleManifest.model_validate_json(
        (bundle_path / "manifest.json").read_text(encoding="utf-8")
    )
    typer.echo(
        json.dumps(
            {
                "trajectory_id": manifest.trajectory_id,
                "status": manifest.data_quality.status.value,
                "issues": manifest.data_quality.issues,
                "bundle": str(bundle_path),
            },
            sort_keys=True,
        )
    )
    if manifest.data_quality.status.value == "excluded":
        raise typer.Exit(2)


@app.command()
def audit(bundle_path: Path) -> None:
    failures = verify_checksum_file(bundle_path)
    if failures:
        typer.echo(json.dumps({"status": "excluded", "issues": ["bundle_checksum_incomplete"]}))
        raise typer.Exit(2)
    manifest = BundleManifest.model_validate_json(
        (bundle_path / "manifest.json").read_text(encoding="utf-8")
    )
    typer.echo(manifest.data_quality.model_dump_json())
```

- [ ] **Step 4: Make the complete CLI fixture actually complete**

Extend `test_bundle_command_prints_machine_readable_result` with one synthetic model artifact, one producing step, one lineage edge, and the six required view files exactly as declared in `tests/test_audit.py`. The expected status remains `complete` because all gates pass, not because the CLI bypasses them.

- [ ] **Step 5: Run CLI and full unit tests**

Run:

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src
```

Expected: all commands exit 0.

- [ ] **Step 6: Commit CLI support**

```bash
git add src/agent_eval/cli.py tests/test_cli.py
git commit -m "feat: add evidence bundle audit CLI"
```

---

### Task 9: Document the Private-to-Public Handoff and Verify a Synthetic Sample

**Files:**

- Create: `docs/source-export-contract.md`
- Create: `tests/fixtures/source_complete/snapshot.json`
- Create: `tests/fixtures/source_complete/files/model.glb`
- Create: `tests/fixtures/source_complete/views/front.png`
- Create: `tests/fixtures/source_complete/views/back.png`
- Create: `tests/fixtures/source_complete/views/left.png`
- Create: `tests/fixtures/source_complete/views/right.png`
- Create: `tests/fixtures/source_complete/views/top.png`
- Create: `tests/fixtures/source_complete/views/isometric.png`
- Create: `tests/fixtures/source_partial/snapshot.json`
- Create: `tests/test_public_safety.py`

**Interfaces:**

- Consumes: source-neutral contract and CLI from Tasks 2–8.
- Produces: reviewable synthetic fixtures, handoff documentation, and a repository-wide public-safety test.

- [ ] **Step 1: Write a failing public-safety test**

```python
# tests/test_public_safety.py
import re
from pathlib import Path

FORBIDDEN_PATTERNS = [
    re.compile(r"https?" + r"://", re.IGNORECASE),
    re.compile(r"\b(?:PRO|ENG|MES|SUP|QA)-\d+\b"),
    re.compile(r"(?:token|api[_-]?key|password)\s*[:=]", re.IGNORECASE),
]


def test_public_files_contain_no_identifying_or_secret_patterns() -> None:
    roots = [Path("src"), Path("tests"), Path("docs")]
    failures: list[str] = []
    for root in roots:
        for path in root.rglob("*"):
            if (
                not path.is_file()
                or "__pycache__" in path.parts
                or path.suffix.lower() in {".png", ".glb", ".pyc"}
            ):
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in FORBIDDEN_PATTERNS:
                if pattern.search(text):
                    failures.append(f"{path}: {pattern.pattern}")
    assert failures == []
```

- [ ] **Step 2: Run the safety test before adding documentation**

Run:

```bash
uv run pytest tests/test_public_safety.py -q
```

Expected: PASS on the existing source-neutral repository. This establishes the guard before adding fixtures and documentation.

- [ ] **Step 3: Write the source export contract**

Create `docs/source-export-contract.md` with these exact normative sections:

```markdown
# Source Export Contract

## Boundary

The private adapter runs inside the approved source environment. It emits a source-neutral directory and does not copy credentials, direct user identifiers, internal URLs, organization names, operational table names, or hidden labels.

## Required Layout

    export/
    ├── snapshot.json
    ├── files/
    │   └── <artifact bytes>
    └── views/
        └── <standardized view bytes>

`snapshot.json` must validate against `agent_eval.contracts.SourceSnapshot`. Every `relative_path` is relative to the export root and must remain within that root after path resolution.

## Consistent Snapshot Window

Experiment, run, attempt, round, turn, step, event, lineage, artifact, and effective configuration records must be read from one consistent snapshot window. If the source cannot provide a consistent view, the adapter must stop without emitting an export.

## Identity

One directory represents exactly one trajectory attempt. Retries and repeated attempts receive separate exports. The adapter supplies a repository-local pseudonymous `trajectory_id`; any private reverse mapping remains outside the public repository.

## Required Digests

The export includes explicit agent version, immutable effective configuration digest, tool-set digest, skill-content digests, experiment snapshot hash, and dataset content hash. Version labels without content digests are insufficient.

## Round Mapping

Each round supplies exact `turn_ids`. If the source omits them, every turn must expose a unique idempotency key using `<attempt_id>:r<round_no>`. Ambiguous mappings must stop the export.

## Artifacts and Views

The adapter copies required artifact bytes and six standardized views into the export directory. Live URLs and mutable identifiers are not substitutes for bytes. The renderer implementation is private, but renderer name, version, parameters, source artifact identity, and source artifact digest are recorded.

## Label Separation

Simulator termination decisions, gold annotations, production feedback, and automatic judge outputs are never placed in judge-visible trajectory fields. If retained for private analysis, they must occupy a separately classified source field that the public projection cannot read.

## Failure Behavior

The adapter fails closed on missing required records, unsupported schema versions, path traversal, direct identifiers, credentials, or inconsistent source reads. It never fabricates a mapping or silently drops a required artifact.
```

- [ ] **Step 4: Add complete and partial synthetic fixtures**

Use the object returned by `minimum_snapshot()` as the base. For `source_complete`, add the model artifact, producing step, lineage edge, and six views from `tests/test_audit.py`. Write exactly `b"model"` to `files/model.glb` and exactly `b"png"` to each view so the declared SHA-256 and byte lengths match. For `source_partial`, copy the complete fixture byte-for-byte and change only:

```json
{
  "attempt": {
    "source_quality_issues": ["missing_round_simulator_call_record"]
  }
}
```

Preserve every other required attempt field when applying that change.

- [ ] **Step 5: Add fixture-driven integration tests to `tests/test_cli.py`**

```python
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
```

- [ ] **Step 6: Run the complete Phase A verification suite**

Run:

```bash
uv run pytest -q
uv run ruff check .
uv run mypy src
git diff --check
```

Expected: all commands exit 0; pytest reports zero failures.

- [ ] **Step 7: Run an explicit repository disclosure scan**

Run:

```bash
uv run pytest tests/test_public_safety.py -q
url_pattern='https?'':\/\/'
issue_pattern='\b(PRO|ENG|MES|SUP|QA)-[0-9]+\b'
git grep -n -E "${url_pattern}|${issue_pattern}" -- ':!uv.lock' ':!tests/test_public_safety.py'
```

Expected: the safety test passes; `git grep` prints no matches and exits 1 because no forbidden pattern is found.

- [ ] **Step 8: Manually inspect the generated bundle layout**

Run:

```bash
uv run agent-eval bundle tests/fixtures/source_complete /tmp/agent-eval-phase-a
find /tmp/agent-eval-phase-a/trajectory-001 -type f | sort
uv run agent-eval audit /tmp/agent-eval-phase-a/trajectory-001
```

Expected:

- the build command prints `"status": "complete"`;
- the file list contains manifest, source records, artifact bytes, six views, audit record, and checksum file;
- the audit command exits 0 with no issues.

- [ ] **Step 9: Commit the handoff contract and fixtures**

```bash
git add docs/source-export-contract.md tests/fixtures tests/test_cli.py tests/test_public_safety.py
git commit -m "docs: define private source export handoff"
```

---

## Phase A Completion Gate

Phase A is complete only when fresh verification proves:

1. the complete synthetic attempt builds a checksum-valid bundle;
2. a tampered byte fails bundle verification;
3. an ambiguous round mapping is excluded;
4. missing required artifact or view bytes are excluded;
5. simulator-call inconsistency is partial and remains eligible for content-quality analysis only;
6. private data directories are git-ignored;
7. the public-safety scan reports no identifying internal references or secret-like assignments;
8. pytest, Ruff, mypy, and `git diff --check` all pass;
9. no production connection or write-back code exists in the repository.

After this gate, create separate implementation plans in this order:

1. standardized 3D rendering and geometry evidence;
2. human-gold annotation and adjudication;
3. judge baselines and evidence-reference validation;
4. calibration, abstention, and coverage–risk analysis;
5. split generation, stability experiments, and publication packaging.
