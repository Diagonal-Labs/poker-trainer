"""Shared test helpers."""

from __future__ import annotations

from pokersim.game_engine.game import decision_context, start_hand
from pokersim.game_engine.rules import Action, ActionKind, HandSetup, RulesHand, SeatEntry
from pokersim.game_engine.seats import DecisionContext


def six_handed(stack: int = 200) -> HandSetup:
    """Seats 0..5 with the button on seat 5: SB 0, BB 1, UTG 2, HJ 3, CO 4, BTN 5."""
    return HandSetup(tuple(SeatEntry(i, stack) for i in range(6)), button=5)


def context(hand: RulesHand, seed: int = 1, hand_number: int = 1) -> DecisionContext:
    return decision_context(hand, seed, hand_number)


def play(hand: RulesHand, *kinds: ActionKind) -> RulesHand:
    """Apply simple actions in turn: 'call', 'fold', 'check' or 'raise' (to the minimum)."""
    for kind in kinds:
        legal = hand.legal()
        assert legal is not None
        hand.apply(Action(kind, legal.min_raise_to if kind in ("raise", "bet") else 0))
    return hand


def new_hand(setup: HandSetup | None = None, seed: int = 1) -> RulesHand:
    return start_hand(setup or six_handed(), seed, 1)
