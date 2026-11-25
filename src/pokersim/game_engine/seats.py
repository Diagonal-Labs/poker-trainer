"""Seat controllers: who makes the decision at each seat.

A seat gets a ``DecisionContext`` and returns an ``Action``, or None to say "wait for the human".
The same interface covers betting decisions and the show-or-muck choice at showdown: the legal
options in the context say which one is being asked.

Persona bots live in decision_engine (BotSeat). The seats here are the human player and simple
ones used for tests and simulation baselines.
"""

from __future__ import annotations

import random
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from pokersim.game_engine.rules import Action, HandSnapshot, LegalOptions


@dataclass(frozen=True)
class DecisionContext:
    seat: int
    snapshot: HandSnapshot
    hole_cards: tuple[str, str]
    legal: LegalOptions
    rng: random.Random
    history: tuple[tuple[int, Action], ...] = ()  # the public action log for this hand so far


class Seat(Protocol):
    def act(self, ctx: DecisionContext) -> Action | None: ...


class HumanSeat:
    """Makes no decision: the game loop stops and waits for the player."""

    def act(self, ctx: DecisionContext) -> Action | None:
        return None


class CheckCallSeat:
    """Checks or calls everything and shows its hand at showdown. A neutral baseline."""

    def act(self, ctx: DecisionContext) -> Action | None:
        kinds = ctx.legal.kinds
        if "show" in kinds:
            return Action("show")
        return Action("check" if "check" in kinds else "call")


class RandomSeat:
    """Picks a random legal action, using the context's random generator. For tests and fuzzing."""

    def act(self, ctx: DecisionContext) -> Action | None:
        kinds, rng, legal = ctx.legal.kinds, ctx.rng, ctx.legal
        if "show" in kinds:
            muck = "muck" in kinds and rng.random() < 0.3
            return Action("muck" if muck else "show")
        roll = rng.random()
        if ("bet" in kinds or "raise" in kinds) and roll < 0.25:
            kind = "bet" if "bet" in kinds else "raise"
            if rng.random() < 0.15:
                return Action(kind, legal.max_raise_to)  # shove
            return Action(kind, rng.randint(legal.min_raise_to, legal.max_raise_to))
        if "fold" in kinds and roll > 0.85:
            return Action("fold")
        return Action("check" if "check" in kinds else "call")


class ScriptedSeat:
    """Plays a fixed list of actions in order, then checks or calls. For tests."""

    def __init__(self, actions: Iterable[Action]) -> None:
        self._actions = list(actions)

    def act(self, ctx: DecisionContext) -> Action | None:
        if self._actions:
            return self._actions.pop(0)
        return CheckCallSeat().act(ctx)
