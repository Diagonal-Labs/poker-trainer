"""BotSeat: a seat played by a persona. Calls the Decision engine and keeps its decision records.

Until the postflop decision engine arrives (slice 4), a bot checks when it can and folds to any bet
after the flop, and always shows its hand at showdown.
"""

from __future__ import annotations

from pokersim.decision_engine.decision import DecisionRecord, decide_preflop
from pokersim.decision_engine.preflop import ChartPolicy
from pokersim.game_engine.rules import Action
from pokersim.game_engine.seats import DecisionContext
from pokersim.schemas.persona import Persona


class BotSeat:
    def __init__(self, persona: Persona, policy: ChartPolicy) -> None:
        self.persona = persona
        self.policy = policy
        self.records: list[DecisionRecord] = []

    def act(self, ctx: DecisionContext) -> Action | None:
        if "show" in ctx.legal.kinds:
            return Action("show")
        if ctx.snapshot.street == "preflop":
            action, record = decide_preflop(ctx, self.persona, self.policy)
            self.records.append(record)
            return action
        return Action("check") if "check" in ctx.legal.kinds else Action("fold")
