# Evidence-Grounded Evaluation for Long-Horizon 3D Creation Agents

**Status:** Approved research design; implementation has not started

**Date:** 2026-07-20

**Scope:** Research data consumption, annotation, judging, calibration, and reporting

**Primary unit of analysis:** One immutable trajectory attempt

## 1. Purpose

This project studies how to evaluate long-horizon 3D creation agents that converse with a user, call tools, generate and revise artifacts, and may fail at several distinct stages before producing a final result.

The research contribution is not a new conversation runner or an internal operations dashboard. The contribution is a reliable automatic evaluation method that:

1. separates upstream execution failures from final 3D quality failures;
2. grounds every verdict in inspectable trajectory and artifact evidence;
3. produces calibrated confidence rather than an unsupported score;
4. abstains when the available evidence is incomplete, conflicting, or unsupported;
5. preserves version-ranking conclusions across agents, judges, simulators, random seeds, and repeated attempts.

The upstream production evaluation platform remains the only source of execution truth. This repository consumes frozen exports from that platform and never reimplements or independently drives the agent under test.

## 2. Publication and Confidentiality Boundary

All public-facing material must remain organization-neutral.

### 2.1 Public terminology

Use the following terms in papers, preprints, figures, repositories, talks, and released data:

- “long-horizon 3D creation agent” for the evaluated system;
- “upstream evaluation platform” for the proprietary execution system;
- “production feedback store” for user feedback data;
- “proprietary production system” when implementation provenance must be disclosed;
- “synthetic user simulator” for the model that drives multi-turn cases.

### 2.2 Prohibited public content

Public artifacts must not contain:

- organization or product names;
- internal issue identifiers, repository names, URLs, hosts, ports, or environment names;
- employee names, internal team structure, or ownership records;
- database table names, internal API paths, service topology, or deployment details;
- secrets, tokens, credentials, account identifiers, or access instructions;
- unapproved production conversations or proprietary prompts;
- implementation details that would identify the source system by themselves or in combination.

### 2.3 Release review

Before any public release, a disclosure review must classify every field and artifact as one of:

- `public`: approved for verbatim release;
- `derived_public`: released only after approved transformation or aggregation;
- `private_reproducible`: retained internally for audit but not released;
- `restricted`: excluded from the research repository and publication package.

Public paper claims must be reproducible either from released material or from an explicitly described private evaluation protocol. Private evidence may support aggregate claims only when disclosure approval allows those claims.

## 3. Research Questions and Hypotheses

### RQ1 — Misattribution

How often does an outcome-only judge incorrectly classify an upstream failure as poor final 3D quality?

**H1:** A judge that only sees the final response and rendered views will produce materially more failure-attribution errors than a judge with execution and lineage evidence.

### RQ2 — Evidence grounding

Does a hierarchical, evidence-grounded judge improve agreement with expert human annotations?

**H2:** Separating requirement understanding, planning and authorization, tool execution, artifact delivery, and final 3D quality will improve both verdict agreement and failure-attribution F1.

### RQ3 — Calibration and abstention

Can calibration and abstention reduce the human review burden while preserving an agreed maximum error rate?

**H3:** Calibrated confidence with explicit abstention will dominate raw judge confidence on the coverage–risk curve.

### RQ4 — Stability

Are conclusions stable across evaluated agent versions, judge models, simulators, random seeds, and repeated attempts?

**H4:** Evidence-grounded judging will yield more stable agent-version rankings than outcome-only judging.

## 4. Scope and Non-Goals

### In scope

- consuming completed trajectory attempts from the upstream platform;
- freezing source records and artifact bytes into immutable research bundles;
- auditing data quality before a trajectory enters an experiment;
- generating standardized 3D views from fixed artifact bytes;
- creating expert human gold labels;
- implementing and comparing automatic judge methods;
- calibrating confidence and defining abstention policies;
- evaluating agreement, attribution, ranking, stability, cost, and review coverage;
- releasing an approved reproducibility package.

### Out of scope

- rebuilding the upstream case runner, scheduler, or administration UI;
- changing production agent behavior;
- treating simulator termination as a quality label;
- treating user thumbs, downloads, retries, or other weak signals as gold labels;
- modifying production data or writing automatic decisions back during the research phase;
- training a new model when the available sample size does not justify it;
- publishing proprietary system identifiers or unapproved user data.

## 5. End-to-End Architecture

```text
Approved cases and weak production signals
                    |
                    v
       Upstream evaluation platform
   dataset -> experiment -> run -> attempt
                    |
                    v
       Immutable source snapshot export
                    |
                    v
          Data quality gate and audit
             |                  |
             v                  v
      accepted bundles     excluded records
             |
             v
   Standardized evidence construction
    trajectory + lineage + fixed 3D views
             |
             +--------------------+
             |                    |
             v                    v
       Human gold          Automatic judges
             |                    |
             +---------+----------+
                       v
        Calibration, abstention, and analysis
                       |
                       v
       Ranking, ablation, stability, publication
                       |
                       v
       Optional approved aggregate write-back
```

There is one direction of authority: upstream execution facts flow into immutable research snapshots. Research annotations and judge outputs are derived records. They never rewrite source evidence.

## 6. Unit of Analysis and Identity

The primary unit is one **trajectory attempt**: a single execution attempt of one case within one run.

An attempt identity must remain distinct from:

- the mutable source case;
- the frozen experiment;
- the batch run;
- the current/latest result pointer;
- the conversation thread;
- another retry or repeated attempt of the same case.

The research identifier is derived from the upstream attempt identifier using a one-way, repository-local mapping. Public exports use a separate pseudonymous identifier. The private mapping is never committed to a public repository.

Every retry and repeated attempt remains a separate observation. A “latest result” view may be used for operational dashboards, but it must never replace append-only attempt history in research analysis.

## 7. Upstream Source Contract

For each selected attempt, the exporter must acquire the following source facts in one consistent snapshot window.

### 7.1 Experiment inputs

- frozen case specification;
- case-family identifier;
- source dataset fingerprint;
- evaluated variant declaration;
- simulator declaration;
- experiment creation time;
- source schema versions.

### 7.2 Effective run configuration

- explicit evaluated agent version;
- immutable agent configuration digest;
- model and endpoint identity without credentials;
- tool-set digest;
- skill-content digests;
- simulator model and decoding parameters;
- runtime limits and policies;
- random seed when supported;
- environment/configuration snapshot digest;
- run start and end times.

An agent version label alone is insufficient because a labeled version may be mutable. A paper-eligible attempt must carry immutable digests of the effective prompt/configuration, tools, skills, and relevant runtime policy.

The evaluated agent version must be explicit. Advisory environment-active or cohort resolution is not sufficient for the main experiment because it may drift during a run.

### 7.3 Attempt execution

- attempt identity and attempt number;
- terminal state and machine-readable termination reason;
- complete checkpoint history when available;
- thread identity;
- exact round-to-turn mapping;
- timing and resource-usage records;
- retry, cancellation, and recovery records;
- source record timestamps.

### 7.4 Full trajectory

- submitted user content blocks, not only flattened text;
- agent messages;
- tool calls and validated arguments;
- tool results and error states;
- interactive questions and exact answers;
- turn and step states;
- internal evidence permitted for research use;
- a stable ordering key for all events.

Simulator decisions and termination labels must be stored outside the judge-visible trajectory. They remain available for simulator analysis but are treated as hidden labels during judging.

### 7.5 Artifact evidence

- artifact identity and kind;
- immutable source bytes or an immutable content-addressed reference;
- content hash, byte length, and media type;
- creation time;
- producing turn, step, and tool call;
- parent/derived relationships;
- all source metadata needed to interpret the artifact;
- availability and extraction status.

Signed URLs, mutable object identifiers, and live database pointers are not sufficient research evidence.

## 8. Immutable Evidence Bundle

Each accepted or excluded attempt is represented by one versioned bundle.

```text
bundles/<trajectory_id>/
├── manifest.json
├── source/
│   ├── experiment.json
│   ├── run.json
│   ├── attempt.json
│   ├── rounds.jsonl
│   ├── turns.jsonl
│   ├── steps.jsonl
│   ├── events.jsonl
│   └── lineage.json
├── artifacts/
│   ├── originals/
│   └── inventory.json
├── views/
│   ├── standard/
│   └── render_manifest.json
├── quality/
│   └── audit.json
└── checksums.sha256
```

### 8.1 Manifest requirements

`manifest.json` must contain:

- bundle schema version;
- pseudonymous trajectory identity;
- upstream attempt identity in the private bundle only;
- case-family and split-group keys;
- source snapshot timestamp;
- effective agent, simulator, and configuration digests;
- file inventory;
- bundle-level checksum;
- disclosure classification;
- data-quality status;
- exporter version and execution parameters.

### 8.2 Immutability rules

- Source records are never edited after bundle creation.
- Corrections create a new bundle revision with a new checksum.
- Derived views, labels, and judge outputs reference the source checksum.
- A changed source checksum invalidates all dependent derived records until regenerated.
- No credential, direct user identifier, or unapproved raw production content enters the bundle.

## 9. Data Quality Gate

An attempt enters the main experiment only if all required checks pass.

### 9.1 Required gates

- the evaluated agent version is explicit;
- the effective prompt/configuration, tools, and skills have immutable digests;
- the experiment snapshot and dataset hash are present;
- round-to-turn mapping is unambiguous;
- all required artifacts are readable;
- every required artifact has a fixed content hash;
- artifact lineage resolves to producing steps and turns;
- standardized multi-view generation succeeds;
- judge input contains no simulator termination label, gold label, or hidden verdict;
- the record contains no unapproved user data;
- every declared file is covered by the bundle checksum;
- source and derived schema versions are supported;
- all timestamps and ordering keys form a consistent trajectory.

### 9.2 Quality states

- `complete`: all gates required by the selected analysis pass;
- `partial`: content-quality evidence is usable, but one or more optional analysis dimensions are unavailable;
- `excluded`: a required gate for the intended analysis fails.

Quality is analysis-specific. A trajectory may be valid for content-quality evaluation while invalid for cost or latency analysis.

### 9.3 Machine-readable issue codes

At minimum, the audit vocabulary includes:

- `missing_explicit_agent_version`;
- `missing_agent_config_digest`;
- `missing_experiment_snapshot`;
- `ambiguous_round_turn_mapping`;
- `missing_required_artifact`;
- `artifact_hash_mismatch`;
- `broken_artifact_lineage`;
- `standard_view_generation_failed`;
- `label_leakage_in_judge_input`;
- `unapproved_user_data`;
- `bundle_checksum_incomplete`;
- `unsupported_source_schema`;
- `missing_round_simulator_call_record`;
- `invalid_evidence_reference`;
- `unsupported_artifact_format`.

### 9.4 Partial-data rule for simulator-call inconsistency

If aggregate usage records a simulator invocation but the corresponding round contains no simulator-call record, mark:

```json
{
  "data_quality": {
    "status": "partial",
    "issues": ["missing_round_simulator_call_record"]
  }
}
```

The trajectory may participate in agent content-quality experiments. It must not participate in simulator cost, latency, or per-call stability analyses. This is a data-quality issue, not an agent failure.

### 9.5 Exclusion records

Failures are never silently deleted. Store one machine-readable record per excluded trajectory:

```text
excluded/<trajectory_id>.json
```

The paper reports exclusion counts by reason and experiment stage.

## 10. Round-to-Turn and Evidence Mapping

Every completed round must map to the exact turn or ordered set of retry turns that produced its observations.

The mapping uses, in priority order:

1. an explicit source round-to-turn field;
2. a unique idempotency-key relationship;
3. event ordering plus turn identity;
4. a documented deterministic reconstruction rule.

If retries, recovery, or multiple turns make more than one mapping plausible, the attempt fails with `ambiguous_round_turn_mapping`. The research exporter must not guess.

Every judge-visible claim must resolve through:

```text
evidence reference
  -> bundle file and record
  -> turn / step / artifact
  -> checksum-covered source
```

References that do not resolve are invalid evidence, even if the natural-language verdict is otherwise plausible.

## 11. Standardized 3D Evidence

Final 3D quality must be evaluated from a fixed rendering protocol, not from whichever preview images happened to be visible during execution.

### 11.1 Source and simulator views

Keep two view classes separate:

- `observed_views`: images actually available to the agent or simulator during the trajectory;
- `standard_views`: research-generated views rendered after export from the fixed final artifact bytes.

Observed views are process evidence. Standard views are controlled outcome evidence. A judge must be told which class each image belongs to.

### 11.2 Standard render protocol

The render manifest fixes:

- renderer name and version;
- camera convention and poses;
- projection type and field of view;
- object normalization and scale policy;
- background and lighting;
- material and texture loading policy;
- image dimensions and encoding;
- failure behavior for unsupported or corrupt assets;
- source artifact checksum;
- checksum of every rendered view.

The minimum view set covers front, back, left, right, top, and an isometric view. Extra task-specific views may be added, but the core set remains identical across compared versions.

### 11.3 Geometry-derived evidence

When supported, compute deterministic structural features such as:

- mesh and component counts;
- triangle and vertex counts;
- bounding box and aspect ratios;
- watertightness and non-manifold indicators;
- disconnected components;
- texture/material presence;
- file parse validity.

These features are evidence, not automatic quality labels. Unsupported formats trigger `unsupported_artifact_format` for analyses that require them.

## 12. Human Gold

### 12.1 Annotation population

- Use two independent annotators for every gold trajectory.
- Use a third adjudicator for disagreements or a predeclared high-risk subset.
- Ensure a meaningful subset is reviewed by annotators with practical 3D expertise.
- Keep annotators blind to agent version, simulator verdict, production feedback, and automatic judge outputs.

### 12.2 Hierarchical rubric

Annotate five evidence layers independently:

1. **Requirement understanding** — whether the agent correctly understood explicit and implied user constraints.
2. **Planning and authorization** — whether the plan, confirmations, and permission-sensitive actions were appropriate.
3. **Tool execution** — whether tool choice, arguments, retries, and failure handling were correct.
4. **Artifact delivery and lineage** — whether the promised artifact was produced, correctly linked, and delivered to the user.
5. **Final 3D quality** — task compliance, geometry, appearance, usability, and task-specific constraints visible in standardized evidence.

Each layer records:

- categorical verdict;
- ordinal or continuous quality score where defined;
- failure type;
- evidence references;
- annotation confidence;
- `not_judgable` with a reason when evidence is insufficient.

### 12.3 Failure taxonomy

The common top-level taxonomy includes:

- `requirement_misunderstanding`;
- `planning_or_authorization_error`;
- `wrong_tool_or_arguments`;
- `tool_execution_failure`;
- `recovery_failure`;
- `artifact_missing_or_wrong`;
- `lineage_or_delivery_failure`;
- `geometry_quality_failure`;
- `appearance_quality_failure`;
- `task_constraint_failure`;
- `unsupported_artifact_format`;
- `invalid_evidence_reference`;
- `insufficient_evidence`;
- `no_material_failure`.

### 12.4 Agreement and adjudication

Report agreement separately for:

- top-level outcome;
- each rubric layer;
- failure type;
- final 3D quality;
- evidence-reference validity.

Use an agreement statistic appropriate to each label scale. Do not collapse all dimensions into one agreement number. Adjudication produces the final gold record while preserving the original independent annotations.

## 13. Automatic Judge Methods

### 13.1 Baselines

1. **Outcome-only judge**

   Receives the case request, final response, and standardized final views. It receives no tool or lineage evidence.

2. **Rubric-only judge**

   Receives the complete user-visible conversation and hierarchical rubric, but no structured execution or lineage bundle.

3. **Evidence-grounded hierarchical judge**

   Receives layer-specific evidence packs, produces layer verdicts with references, then combines them using a deterministic attribution policy.

### 13.2 Evidence-grounded judge stages

1. A deterministic extractor constructs facts from turns, steps, tools, states, artifacts, lineage, and fixed views.
2. Layer judges assess only the evidence relevant to their rubric layer.
3. An attribution stage reconciles process and outcome evidence.
4. A reference validator rejects nonexistent, out-of-scope, or checksum-mismatched references.
5. A confidence stage emits raw confidence features.
6. A calibration stage converts raw confidence into calibrated correctness probability.
7. An abstention policy decides whether the verdict remains automatic or goes to human review.

### 13.3 Judge output contract

Every judge output includes:

- method and version;
- judge model and parameters;
- source bundle checksum;
- per-layer verdicts and scores;
- failure attribution;
- evidence references;
- raw confidence;
- calibrated confidence when available;
- abstention decision and reason;
- token, latency, and cost data;
- machine-readable validation errors.

Required abstention reasons include:

- `low_calibrated_confidence`;
- `judge_disagreement`;
- `invalid_evidence_reference`;
- `unsupported_artifact_format`;
- `insufficient_evidence`;
- `conflicting_evidence`.

## 14. Calibration and Abstention

Calibration parameters and abstention thresholds are fit only on the calibration split.

Report before and after calibration:

- expected calibration error;
- Brier score;
- reliability plots;
- selective risk at fixed coverage;
- coverage at fixed risk;
- human-review rate.

The primary operating metric is the **coverage–risk curve**: as the fraction sent to human review increases, measure how quickly the error rate among the remaining automatic decisions decreases.

The paper must predeclare the primary error definition used for coverage–risk analysis. Secondary curves may separately cover outcome correctness, attribution correctness, and agent-version ordering.

## 15. Data Splitting

Default proportions:

```text
train/dev      40%
calibration    20%
test           40%
```

The split algorithm must satisfy all of the following simultaneously:

- one real user never crosses splits;
- one case family never crosses splits;
- attempts from one thread or trajectory never cross splits;
- retries and repeated attempts remain grouped;
- real-user data additionally uses a chronological holdout;
- rubric wording, prompts, models, aggregation rules, and thresholds may be adjusted only on train/dev and calibration;
- test gold is frozen before the final evaluation run;
- no test statistics are used for method selection.

When the sample is small, train/dev is used for rubric, prompt, and extraction development rather than model training.

## 16. Real-User Calibration Track

Synthetic cases measure controlled capabilities. Real-user data measures simulator-to-production distribution shift. The two tracks must not be silently mixed.

The real-user pipeline is:

```text
production signals
  -> earliest-stage de-identification
  -> session filtering and segmentation
  -> failure clustering
  -> stratified sampling
  -> expert annotation
  -> judge calibration
  -> chronological held-out evaluation
```

Candidate weak signals include thumbs, complaints, refunds, regeneration, undo, restatement, abandonment, downloads, exports, continued editing, and system failures.

Weak signals are used only for discovery, stratification, and distribution analysis. They are never treated as gold labels without expert annotation.

Selection-bias documentation must cover at least:

- which product states expose a feedback control;
- which users can submit feedback;
- which outputs are eligible for feedback;
- missing positive-feedback reasons;
- optional negative-feedback categories;
- differences between users who provide feedback and those who do not.

## 17. Minimum Experimental Matrix

### 17.1 Data quality audit

- missing fields;
- source and schema version drift;
- round-to-turn mapping;
- artifact availability and checksum validity;
- standard-view success rate;
- exclusion counts by reason.

### 17.2 Human gold

- layer-level agreement;
- failure-type agreement;
- 3D-quality agreement;
- adjudication rate;
- evidence-reference agreement.

### 17.3 Judge baselines

- outcome-only;
- rubric-only;
- evidence-grounded hierarchical judge.

### 17.4 Calibration

- uncalibrated versus calibrated ECE;
- uncalibrated versus calibrated Brier score;
- coverage–risk curves;
- human-review savings at fixed risk.

### 17.5 Agent-version ranking

- automatic versus human version ranking;
- Spearman rank correlation;
- Kendall rank correlation;
- pairwise version preference accuracy;
- uncertainty intervals over ranking metrics.

### 17.6 Ablations

Remove one component at a time:

- tool evidence;
- artifact lineage;
- standardized multi-view evidence;
- hierarchical rubric;
- confidence calibration;
- abstention;
- real-user calibration.

### 17.7 Stability

Measure variation across:

- at least three evaluated agent versions or configurations;
- multiple judge models;
- simulator models or personas;
- random seeds;
- repeated attempts;
- source schema versions when applicable.

## 18. Metrics

### Primary metrics

- coverage–risk area and selected operating points;
- failure-attribution macro F1;
- agreement with adjudicated human gold;
- agent-version rank correlation.

### Secondary metrics

- per-layer accuracy, F1, and ordinal agreement;
- invalid evidence-reference rate;
- abstention rate by reason;
- ECE and Brier score;
- pairwise version preference accuracy;
- judge cost and latency;
- human-review time saved;
- exclusion and partial-data rates;
- result variance across repeated attempts.

Report confidence intervals using a resampling unit that respects case-family and trajectory grouping. Do not bootstrap individual turns as independent observations.

## 19. Minimum Study Scale

The target minimum is:

- 100–200 difficulty-stratified dynamic cases;
- 300–500 complete multi-turn trajectory attempts;
- at least three evaluated agent versions or configurations;
- three judge methods;
- two or three human annotators;
- a meaningful expert-reviewed 3D subset;
- repeated attempts for a declared stability subset.

If the final sample is smaller, the study must narrow its claims rather than compensate with unvalidated model training.

## 20. Reproducibility and Leakage Prevention

Every reported experiment freezes:

- source bundle checksums;
- split manifest;
- rubric version;
- annotation-guide version;
- deterministic extractor version;
- view-renderer version and parameters;
- judge prompts and aggregation policy;
- judge model and decoding parameters;
- calibration method and fitted parameters;
- abstention thresholds;
- analysis code revision;
- random seeds;
- exclusion manifest.

Judge inputs are generated by a dedicated projection that removes:

- gold annotations;
- simulator finish reasons and goal labels;
- production thumbs and weak labels;
- agent-version labels when blind comparison requires them;
- filenames or metadata that reveal the evaluated condition;
- internal identifiers unrelated to the evidence task.

A leakage test must fail if any prohibited field enters a judge request.

## 21. Derived Results and Optional Write-Back

The canonical research record for every annotation and judge run lives in access-controlled private research storage adjacent to this repository, keyed by source bundle checksum and method version. Raw or restricted bundles must never be committed to the public code repository.

An approved integration may later write a reduced derived projection to an internal evaluation store for dashboards. Such write-back must:

- never modify source trajectory records;
- identify the judge and method version;
- point back to the immutable private result;
- preserve per-attempt identity;
- avoid exposing restricted evidence;
- occur only after explicit production authorization;
- remain unnecessary for paper reproduction.

The research pipeline is complete without write-back.

## 22. Publication Package

Subject to disclosure approval, release:

- the hierarchical rubric and annotation guide;
- the public failure taxonomy;
- source-neutral bundle and judge schemas;
- deterministic evidence-extraction code;
- standard rendering protocol;
- baseline and evidence-grounded judge implementations;
- calibration and coverage–risk evaluation code;
- split and leakage-prevention protocol;
- a de-identified benchmark subset or fully synthetic proxy set;
- aggregate statistics and exclusion counts;
- experiment manifests sufficient to reproduce public claims.

If real trajectories cannot be released, publish a synthetic proxy set and the same protocol, and clearly distinguish public reproducibility from private validation.

## 23. Phased Delivery

### Phase A — Source contract and audit

Deliver the source inventory, immutable bundle contract, checksum rules, quality-gate vocabulary, and one manually verified end-to-end sample.

### Phase B — Gold pilot

Deliver the rubric, annotation guide, blinded annotation workflow, pilot agreement results, and revised failure taxonomy.

### Phase C — Judge baselines

Deliver outcome-only, rubric-only, and evidence-grounded judge outputs on train/dev with validated evidence references.

### Phase D — Calibration and frozen test

Freeze split manifests and test gold, fit calibration and abstention on calibration data, then run the final test once.

### Phase E — Stability and publication

Complete ranking, ablation, stability, real-user holdout, disclosure review, and the approved publication package.

## 24. Acceptance Criteria for the Research Design

The design is ready for implementation planning only when all of the following are accepted:

- the upstream platform remains the sole execution source;
- the trajectory attempt is the unit of analysis;
- source evidence is exported once and frozen by checksum;
- explicit version and effective configuration digests are mandatory;
- round-to-turn mapping cannot rely on an undocumented guess;
- standardized views are distinct from simulator-observed images;
- weak production signals are not gold;
- simulator labels and gold cannot leak into judge input;
- calibration uses a separate split;
- coverage–risk is the primary selective-prediction metric;
- partial data is excluded only from the analyses it cannot support;
- public artifacts remain organization-neutral;
- write-back is optional, derived, and independently authorized;
- implementation code remains out of this design phase.

## 25. Decisions Fixed by This Specification

1. Do not build a second runner in the research repository.
2. Consume immutable exports of individual trajectory attempts.
3. Preserve all retries and repetitions as separate history.
4. Treat operational current-result pointers as convenience views only.
5. Require full effective configuration digests, not version labels alone.
6. Keep observed views and standardized evaluation views separate.
7. Build gold labels before claiming automatic evaluation quality.
8. Use evidence-grounded hierarchical judging as the proposed method.
9. Use calibration and abstention, with coverage–risk as the primary operating analysis.
10. Keep all public descriptions source-neutral and remove identifying internal details.
