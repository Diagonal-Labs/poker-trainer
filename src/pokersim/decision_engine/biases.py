"""Biases: what the bot likes to do given its reading. Each slider runs from -1 to 1 and shifts
action scores in pot units, by an amount set in data/bias_scales.json. Biases never touch the
perceived state. Sizing style and tell leakage are biases too and live in sizing.style_bonus.

  looseness      bonus for continuing: calling or raising instead of folding to a bet
  aggression     moves value from checking and calling toward betting and raising
  stickiness     calling-station pull: a call bonus that grows with the size of the bet faced
  riskAversion   penalty on putting a large share of the stack at risk without a strong hand
"""

from __future__ import annotations

from pokersim.decision_engine.decision_state import DecisionState
from pokersim.decision_engine.perception import Perception
from pokersim.decision_engine.presets import Profile, Tuning
from pokersim.decision_engine.scoring import Candidate


def apply_biases(
    candidates: list[Candidate],
    state: DecisionState,
    perception: Perception,
    profile: Profile,
    tuning: Tuning,
) -> list[Candidate]:
    scale = tuning.bias_scales
    out: list[Candidate] = []
    for c in candidates:
        delta = 0.0
        if state.facing_bet and c.kind in ("call", "raise"):
            delta += scale.get("looseness", 0.0) * profile.looseness
        if c.is_aggressive:
            delta += scale.get("aggression", 0.0) * profile.aggression
        elif c.kind in ("check", "call"):
            delta -= 0.5 * scale.get("aggression", 0.0) * profile.aggression
        if c.kind == "call":
            pull = min(state.bet_ratio + 0.25, 1.0)
            delta += scale.get("stickiness", 0.0) * profile.stickiness * pull
        if c.kind in ("call", "bet", "raise") and state.stack > 0:
            added = (c.amount - state.my_bet) if c.is_aggressive else state.to_call
            share = min(added / state.stack, 1.0)
            delta -= (
                scale.get("riskAversion", 0.0)
                * profile.risk_aversion
                * share
                * (1.0 - perception.equity)
            )
        out.append(c.moved(delta))
    return out
