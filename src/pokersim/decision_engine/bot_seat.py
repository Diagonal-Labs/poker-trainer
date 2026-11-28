"""BotSeat: a seat played by a persona. Calls the Decision engine and keeps its decision records.

Preflop it plays its chart; postflop it runs the full pipeline. At showdown it always shows (a
show-or-muck habit comes later).
"""

from __future__ import annotations

from pokersim.decision_engine.decision import (
    DecisionRecord,
    PostflopRecord,
    decide_postflop,
    decide_preflop,
)
from pokersim.decision_engine.equity import EquityModel
from pokersim.decision_engine.preflop import ChartPolicy
from pokersim.decision_engine.presets import Profile, Tuning
from pokersim.game_engine.rules import Action
from pokersim.game_engine.seats import DecisionContext
from pokersim.schemas.persona import Persona


class BotSeat:
    def __init__(
        self,
        persona: Persona,
        policy: ChartPolicy,
        profile: Profile,
        tuning: Tuning,
        model: EquityModel,
    ) -> None:
        self.persona = persona
        self.policy = policy
        self.profile = profile
        self.tuning = tuning
        self.model = model
        self.records: list[DecisionRecord] = []  # preflop decisions
        self.postflop_records: list[PostflopRecord] = []

    def act(self, ctx: DecisionContext) -> Action | None:
        if "show" in ctx.legal.kinds:
            return Action("show")
        if ctx.snapshot.street == "preflop":
            action, record = decide_preflop(ctx, self.persona, self.policy)
            self.records.append(record)
            return action
        action, post = decide_postflop(ctx, self.profile, self.tuning, self.model)
        self.postflop_records.append(post)
        return action
