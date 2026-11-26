"""Preflop raise sizes, using live-game norms. Charts say whether to raise, not how much.

Open raises are 3, 4 or 5 big blinds, an isolation raise adds 2.5 big blinds per limper, a 3-bet is
3x the raise in position and 4x out of position, a 4-bet is about 2.3x, and a 5-bet is all-in. A
raise that would commit more than half the stack becomes all-in.

Postflop, ``postflop_menu`` builds the size menu from the design doc (bets of 33%, 66%, 100% and
150% of the pot and all-in; raises of the minimum, 3x and 3.5x the bet and all-in) with the live
constraints: legal limits, chip rounding, near-stack sizes becoming all-in, and merging sizes
that round to the same amount. ``style_bonus`` is the sizing-style and tell-leakage bias.
"""

from __future__ import annotations

from dataclasses import dataclass

from pokersim.decision_engine.decision_state import DecisionState
from pokersim.decision_engine.perception import Perception
from pokersim.decision_engine.presets import Profile, Tuning
from pokersim.decision_engine.spot import SpotInfo
from pokersim.game_engine.seats import DecisionContext

_IN_POSITION = ("button", "cutoff")
OPEN_MULTIPLES = (3, 4, 5)


def preflop_raise_to(info: SpotInfo, ctx: DecisionContext) -> int:
    """Total amount to raise to, between the legal minimum and the whole stack."""
    snap, legal = ctx.snapshot, ctx.legal
    bb = snap.big_blind
    facing = max(s.bet for s in snap.seats)
    me = next(s for s in snap.seats if s.seat == ctx.seat)
    committed_if_called = me.stack + me.bet  # the whole stack as a total bet-to
    open_size = bb * ctx.rng.choice(OPEN_MULTIPLES)
    if info.spot == "open":
        target = open_size
    elif info.spot == "vs_limp":
        target = open_size + round(2.5 * bb) * info.limpers
    elif info.spot == "vs_raise":
        target = facing * (3 if info.position_group in _IN_POSITION else 4)
    elif info.spot == "vs_3bet":
        target = round(facing * 2.3)
    else:
        target = committed_if_called
    if target * 2 > committed_if_called:  # committing over half the stack: just shove
        target = committed_if_called
    return max(legal.min_raise_to, min(target, legal.max_raise_to))


@dataclass(frozen=True)
class SizeOption:
    id: str  # one of schemas.persona.SIZE_IDS
    amount: int  # total to bet or raise to


_BET_FRACTIONS = (("bet_33", 0.33), ("bet_66", 0.66), ("bet_100", 1.0), ("bet_150", 1.5))
_RAISE_MULTIPLES = (("raise_3x", 3.0), ("raise_35x", 3.5))


def _round_chips(amount: float, tuning: Tuning) -> int:
    below = tuning.baseline["sizeRoundBelow"]
    step = 1 if amount < below else int(tuning.baseline["sizeRoundStep"])
    return max(round(amount / step) * step, 1)


def postflop_menu(state: DecisionState, tuning: Tuning) -> list[SizeOption]:
    """The bet or raise sizes a bot considers, lowest first. Empty when it cannot bet or raise."""
    legal = state.legal
    if not ({"bet", "raise"} & set(legal.kinds)) or legal.max_raise_to < legal.min_raise_to:
        return []
    lo, hi = legal.min_raise_to, legal.max_raise_to
    facing_total = state.my_bet + state.to_call
    raw: list[tuple[str, float]]
    if state.facing_bet:
        raw = [("raise_min", lo)] + [(i, facing_total * m) for i, m in _RAISE_MULTIPLES]
        shove = "raise_allin"
    else:
        raw = [(i, state.pot * f) for i, f in _BET_FRACTIONS]
        shove = "bet_allin"
    # Deep stacks do not shove into a small pot: all-in is on the menu only when the stack is no
    # more than shoveMaxPotMultiple times the pot (and always when it is all that is left).
    shove_ok = hi <= tuning.baseline["shoveMaxPotMultiple"] * max(state.pot, 1) or hi <= lo
    options: list[SizeOption] = []
    seen: set[int] = set()
    for size_id, target in raw:
        amount = _round_chips(target, tuning)
        amount = max(lo, min(amount, hi))
        if shove_ok and amount >= tuning.baseline["shoveFraction"] * hi:
            continue  # close to the whole stack: the all-in option covers it
        if amount not in seen:
            seen.add(amount)
            options.append(SizeOption(size_id, amount))
    if shove_ok and hi not in seen:
        options.append(SizeOption(shove, hi))
    return sorted(options, key=lambda o: o.amount)


def style_bonus(
    options: list[SizeOption],
    profile: Profile,
    perception: Perception,
    tuning: Tuning,
) -> dict[str, float]:
    """Sizing-style and tell-leakage bias per size id, in pot units.

    Style: favored sizes get a bonus and the others a smaller penalty, scaled by the persona's
    strength. Leakage: stronger perceived hands lean toward larger sizes and weaker toward smaller,
    and the protect flag (read here and nowhere else) pushes a vulnerable hand toward larger.
    """
    out: dict[str, float] = {}
    style_unit = tuning.bias_scales.get("sizingStyle", 0.0)
    leak_unit = tuning.bias_scales.get("tellLeakage", 0.0)
    signal = (perception.equity - 0.5) * 2
    if perception.protect:
        signal += 0.5
    signal = max(-1.0, min(1.0, signal))
    count = len(options)
    for rank, option in enumerate(options):
        bonus = 0.0
        if profile.favored_sizes:
            favored = option.id in profile.favored_sizes
            bonus += profile.size_strength * style_unit * (1.0 if favored else -0.5)
        if count > 1:
            lean = 2 * rank / (count - 1) - 1
            bonus += profile.tell_leakage * leak_unit * signal * lean
        out[option.id] = bonus
    return out
