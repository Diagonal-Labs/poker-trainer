"""One bot decision. In this slice that is the preflop chart step; postflop arrives in slice 4.

The steps follow "How the decision engine uses a chart" in the design doc: find the spot and rule,
check chart adherence, read the hand's weights (looseness is already applied in the ChartPolicy),
apply mix fidelity, then draw the action with the seat's seeded generator.

Chart adherence: with probability 1 minus the persona's chartAdherence the doc sends the bot to the
full perception pipeline. That pipeline does not exist yet, so the stand-in is the cautious
default: check if it is free, otherwise fold. Slice 4 replaces it.
"""

from __future__ import annotations

from dataclasses import dataclass

from pokersim.decision_engine.preflop import (
    RAISE_ACTIONS,
    SPOT_ACTIONS,
    ChartPolicy,
    action_probabilities,
    hand_class,
)
from pokersim.decision_engine.sizing import preflop_raise_to
from pokersim.decision_engine.spot import SpotInfo, find_spot
from pokersim.game_engine.rules import Action
from pokersim.game_engine.seats import DecisionContext
from pokersim.schemas.persona import Persona


@dataclass(frozen=True)
class DecisionRecord:
    """Why a bot acted, so every preflop action traces back to a line in a chart."""

    spot: SpotInfo
    rule_index: int
    hand: str
    chart_used: bool  # False when adherence sent the bot to the stand-in
    probabilities: dict[str, float]
    chosen: str  # the chart action drawn: raise, limp, call, 3bet, ..., or fold
    action: Action
    to_call: int  # chips needed to call when the bot acted


def _safe(ctx: DecisionContext) -> Action:
    """Check if free, otherwise fold."""
    return Action("check") if "check" in ctx.legal.kinds else Action("fold")


def _as_action(chosen: str, info: SpotInfo, ctx: DecisionContext) -> Action:
    kinds = ctx.legal.kinds
    if chosen in RAISE_ACTIONS:
        if "raise" in kinds or "bet" in kinds:
            return Action("raise" if "raise" in kinds else "bet", preflop_raise_to(info, ctx))
        chosen = "call"  # cannot raise (for example, already all-in or capped), so just call
    if chosen in ("limp", "call"):
        return Action("check" if "check" in kinds else "call")
    return _safe(ctx)


def decide_preflop(
    ctx: DecisionContext, persona: Persona, policy: ChartPolicy
) -> tuple[Action, DecisionRecord]:
    info = find_spot(ctx)
    rule_index = policy.rule_index(info.spot, info.position_group)
    hand = hand_class(ctx.hole_cards)
    rng = ctx.rng
    uses_chart = rng.random() < persona.chart_adherence()
    if not uses_chart:
        action = _safe(ctx)
        record = DecisionRecord(
            info, rule_index, hand, False, {}, "fold", action, ctx.legal.call_amount
        )
        return action, record
    probs = action_probabilities(
        policy.stated(info.spot, rule_index, hand), SPOT_ACTIONS[info.spot], persona.mix_fidelity()
    )
    roll = rng.random()
    chosen = "fold"
    cumulative = 0.0
    for name, p in probs.items():
        cumulative += p
        if roll < cumulative:
            chosen = name
            break
    action = _as_action(chosen, info, ctx)
    return action, DecisionRecord(
        info, rule_index, hand, True, probs, chosen, action, ctx.legal.call_amount
    )
