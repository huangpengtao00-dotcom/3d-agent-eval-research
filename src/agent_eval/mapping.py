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
            raise AmbiguousRoundTurnMapping(f"duplicate round number {round_record.round_no}")
        if round_record.turn_ids:
            turn_ids = tuple(round_record.turn_ids)
            if (
                len(set(turn_ids)) != len(turn_ids)
                or not set(turn_ids) <= known_turns
                or not set(turn_ids).isdisjoint(claimed_turns)
            ):
                raise AmbiguousRoundTurnMapping(
                    f"round {round_record.round_no} has invalid turn ids"
                )
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
