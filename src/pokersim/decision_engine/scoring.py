"""The baseline EV engine: every candidate action scored as a rational player would, given what
this bot believes (its perceived equity and price). Scores are in pot units, so one temperature
works at every pot size. Biases and habits adjust these scores afterwards; they are relative to this
baseline ("calls more than he should").

V1 formulas from the design doc, ignoring later streets. callBonus is a small flat stand-in for
the implied odds and showdown value those formulas leave out; without it every bot over-folds:
  fold   0
  check  realization x equity
  call   realization x equity x (pot + call) / pot - perceived call cost + callBonus
  raise  FE + (1 - FE) x (realization x equity-when-called x final pot / pot - cost)
"""

from __future__ import annotations

from dataclasses import dataclass

from pokersim.decision_engine.decision_state import DecisionState
from pokersim.decision_engine.perception import Perception
from pokersim.decision_engine.presets import Tuning
from pokersim.decision_engine.sizing import SizeOption


@dataclass(frozen=True)
class Candidate:
    id: str  # fold, check, call, or a size id from the menu
    kind: str  # fold, check, call, bet or raise
    amount: int  # total to bet or raise to; 0 for the others
    score: float  # pot units

    def moved(self, delta: float) -> Candidate:
        return Candidate(self.id, self.kind, self.amount, self.score + delta)

    @property
    def is_aggressive(self) -> bool:
        return self.kind in ("bet", "raise")


def realization(state: DecisionState, category: str, tuning: Tuning) -> float:
    base = tuning.baseline
    r = base["realizationInPosition"] if state.in_position else base["realizationOutOfPosition"]
    return r * base["weakDrawRealization"] if category == "weak_draw" else r


def fold_equity(state: DecisionState, extra_ratio: float, tuning: Tuning) -> float:
    """Chance every active opponent folds: the product of each one's fold chance, which grows with
    the bet relative to the pot. Raising over a bet is less likely to fold the bettor out, because
    the bet showed some strength (raiseFoldFactor)."""
    base = tuning.baseline
    each = base["foldEquityScale"] * extra_ratio / (1 + extra_ratio)
    if state.facing_bet:
        each *= base["raiseFoldFactor"]
    each = min(each, base["maxFoldPerOpponent"])
    return each ** len(state.active_opponents) if state.active_opponents else 0.0


def baseline_scores(
    state: DecisionState, perception: Perception, tuning: Tuning, options: list[SizeOption]
) -> list[Candidate]:
    pot = max(state.pot, 1)
    eq = perception.equity
    r = realization(state, perception.category, tuning)
    kinds = state.legal.kinds
    out: list[Candidate] = []
    if "fold" in kinds:
        out.append(Candidate("fold", "fold", 0, 0.0))
    if "check" in kinds:
        out.append(Candidate("check", "check", 0, r * eq))
    base = tuning.baseline
    if "call" in kinds:
        value = r * eq * (pot + state.to_call) / pot - perception.call_cost + base["callBonus"]
        out.append(Candidate("call", "call", 0, value))
    for option in options:
        added = option.amount - state.my_bet  # chips this action puts in
        extra = added - state.to_call  # the part opponents must call
        ratio = extra / (pot + state.to_call)
        fe = fold_equity(state, ratio, tuning)
        discount = base["calledDiscountBase"] + base["calledDiscountBetSize"] * ratio / (1 + ratio)
        if state.facing_bet:
            discount += base["raiseCalledPenalty"]  # whoever bet first already showed strength
        called_eq = max(eq - discount, 0.0)
        final_pot = pot + 2 * added - state.to_call
        score = fe + (1 - fe) * (r * called_eq * final_pot / pot - added / pot)
        kind = "raise" if state.facing_bet else "bet"
        out.append(Candidate(option.id, kind, option.amount, score))
    return out
