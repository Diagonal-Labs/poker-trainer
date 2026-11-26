"""One bot decision: the preflop chart step, or the postflop pipeline.

The steps follow "How the decision engine uses a chart" in the design doc: find the spot and rule,
check chart adherence, read the hand's weights (looseness is already applied in the ChartPolicy),
apply mix fidelity, then draw the action with the seat's seeded generator.

Chart adherence: with probability 1 minus the persona's chartAdherence the doc sends the bot to the
full perception pipeline. That pipeline works from a board, so a preflop decision that skips the
chart still uses a stand-in: check if it is free, otherwise fold.

Postflop: decision state -> perception -> baseline EV over the size menu -> biases -> sizing
style and tell leakage -> action selector. Habits and tells arrive in a later slice.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from pokersim.decision_engine.biases import apply_biases
from pokersim.decision_engine.choose import choose
from pokersim.decision_engine.decision_state import DecisionState, build_state
from pokersim.decision_engine.equity import EquityModel
from pokersim.decision_engine.perception import Perception, perceive
from pokersim.decision_engine.preflop import (
    RAISE_ACTIONS,
    SPOT_ACTIONS,
    ChartPolicy,
    action_probabilities,
    hand_class,
)
from pokersim.decision_engine.presets import Profile, Tuning
from pokersim.decision_engine.scoring import Candidate, baseline_scores
from pokersim.decision_engine.sizing import (
    SizeOption,
    postflop_menu,
    preflop_raise_to,
    style_bonus,
)
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


@dataclass(frozen=True)
class PostflopRecord:
    """Why a bot acted postflop: what it saw, every candidate's score, and the odds it drew from."""

    street: str
    state: DecisionState
    perception: Perception
    baseline: dict[str, float]  # candidate id -> baseline EV, pot units
    final: dict[str, float]  # candidate id -> score after biases and sizing style
    probabilities: dict[str, float]
    chosen: str
    action: Action


def _to_action(candidate: Candidate) -> Action:
    if candidate.kind in ("bet", "raise"):
        return Action("bet" if candidate.kind == "bet" else "raise", candidate.amount)
    return Action(candidate.kind)  # type: ignore[arg-type]  # fold, check or call


def decide_postflop(
    ctx: DecisionContext, profile: Profile, tuning: Tuning, model: EquityModel
) -> tuple[Action, PostflopRecord]:
    rng: random.Random = ctx.rng
    state = build_state(ctx)
    perception = perceive(state, profile, tuning, model, rng)
    options: list[SizeOption] = postflop_menu(state, tuning)
    baseline = baseline_scores(state, perception, tuning, options)
    adjusted = apply_biases(baseline, state, perception, profile, tuning)
    bonus = style_bonus(options, profile, perception, tuning)
    final = [c.moved(bonus.get(c.id, 0.0)) for c in adjusted]
    picked, probabilities = choose(final, profile.temperature, profile.size_temperature, rng)
    action = _to_action(picked)
    record = PostflopRecord(
        street=state.street,
        state=state,
        perception=perception,
        baseline={c.id: c.score for c in baseline},
        final={c.id: c.score for c in final},
        probabilities=probabilities,
        chosen=picked.id,
        action=action,
    )
    return action, record
