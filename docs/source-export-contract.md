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
