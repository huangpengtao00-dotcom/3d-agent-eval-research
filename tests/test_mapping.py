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
