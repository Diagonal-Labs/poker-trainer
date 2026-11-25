"""The game engine: plays a hand forward by asking each seat to act.

``run_until_human_turn`` applies bot decisions seat by seat and stops when a human seat must act or
the hand ends. Calibration calls the same function with no human seat. Randomness is derived from
the session seed, the hand number and the action index, so a hand can always be rebuilt exactly.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pokersim.engine.rules import Action, HandResult, HandSetup, RulesHand
from pokersim.engine.seats import DecisionContext, Seat

MAX_STEPS = 2000  # a hand has far fewer actions; this only guards against a seat that never ends it


def derive_rng(seed: int, hand_number: int, stream: str, index: int = 0) -> random.Random:
    """A generator that depends only on its arguments. Separate streams never share draws."""
    return random.Random(f"{seed}:{hand_number}:{stream}:{index}")


def start_hand(setup: HandSetup, seed: int, hand_number: int) -> RulesHand:
    return RulesHand.start(setup, derive_rng(seed, hand_number, "deck"))


def replay_hand(
    setup: HandSetup, seed: int, hand_number: int, actions: Sequence[Action]
) -> RulesHand:
    """Rebuild a hand from its setup, seed and action list. Bots do not decide again."""
    return RulesHand.replay(setup, derive_rng(seed, hand_number, "deck"), list(actions))


@dataclass(frozen=True)
class StepResult:
    """Where the hand stands after running: waiting for a human, or finished."""

    waiting_for: int | None  # the seat the game is waiting on
    complete: bool


def run_until_human_turn(
    hand: RulesHand, seats: Mapping[int, Seat], seed: int, hand_number: int
) -> StepResult:
    """Play on until a seat returns no action (a human) or the hand is complete."""
    for _ in range(MAX_STEPS):
        phase = hand.phase
        if phase == "complete":
            return StepResult(None, True)
        if phase == "runout":
            hand.apply(Action("runout", 1))  # V1 always uses a single runout
            continue
        legal = hand.legal()
        actor = hand.actor
        if legal is None or actor is None:
            raise RuntimeError("no legal options for the current actor")  # pragma: no cover
        ctx = DecisionContext(
            seat=actor,
            snapshot=hand.snapshot(),
            hole_cards=hand.hole_cards(actor),
            legal=legal,
            rng=derive_rng(seed, hand_number, "action", len(hand.history)),
        )
        action = seats[actor].act(ctx)
        if action is None:
            return StepResult(actor, False)
        hand.apply(action)
    raise RuntimeError("hand did not finish")  # pragma: no cover


def play_hand(
    setup: HandSetup, seats: Mapping[int, Seat], seed: int, hand_number: int
) -> tuple[RulesHand, HandResult]:
    """Play a whole hand with no human seat. Used by tests and simulation."""
    hand = start_hand(setup, seed, hand_number)
    step = run_until_human_turn(hand, seats, seed, hand_number)
    if not step.complete:
        raise ValueError(f"seat {step.waiting_for} is a human seat; play_hand needs bots only")
    return hand, hand.result()


def next_button(active_seats: Sequence[int], previous: int) -> int:
    """The next seat clockwise from ``previous`` that is still playing."""
    ordered = sorted(active_seats)
    for seat in ordered:
        if seat > previous:
            return seat
    return ordered[0]
