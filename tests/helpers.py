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
