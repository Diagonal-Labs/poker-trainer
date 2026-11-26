"""Perception: the bot's reading of the situation, which may be wrong.

Level 1 and 2 bots sort their hand into a category, apply situation flags that move it down, and
map the category to an equity with the level's table. Level 3 bots use their true equity against
the ranges they believe in. The perception layer changes what the bot sees (category, perceived
equity, perceived price, flags). It never touches action scores.

Dials gate what each level notices: handStrength 3 uses real equity; boardTexture 2 applies the
scary_board flag; money 2 applies the big_bet flag and mixes dollar amounts into the price;
multiway 2 adds a lottery bonus per extra opponent. A dial of 3 on the last three needs no special
rule here because equity against the real field already covers it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from pokersim.decision_engine.decision_state import DecisionState
from pokersim.decision_engine.equity import EquityModel
from pokersim.decision_engine.hand_category import HandReading, read_hand
from pokersim.decision_engine.presets import Profile, Tuning

ORDER = ("air", "weak", "medium", "strong", "monster")  # made-hand categories, worst first


@dataclass(frozen=True)
class Perception:
    category: str  # what the bot calls its hand; "equity" for Level 3
    equity: float  # perceived equity, 0 to 1
    call_cost: float  # perceived cost of the call, in pots
    flags: dict[str, float]  # flag name -> strength actually applied
    protect: bool  # a vulnerable made hand on a wet board; read only by sizing (leakage)


def _table_equity(table: dict[str, float], position: float) -> float:
    """Equity of a made-hand category at a (possibly fractional) place in ORDER."""
    position = max(0.0, min(position, len(ORDER) - 1.0))
    low = int(position)
    high = min(low + 1, len(ORDER) - 1)
    frac = position - low
    return table[ORDER[low]] * (1 - frac) + table[ORDER[high]] * frac


def _read_category(reading: HandReading, profile: Profile) -> tuple[str, float]:
    """Category name and its place in ORDER if it is a made hand (else -1 for a draw)."""
    table = profile.category_table
    made_equity = table[reading.made]
    draw_equity = table.get(reading.draw, 0.0) if reading.draw != "none" else 0.0
    if profile.level == 1 and reading.draw == "weak_draw":
        draw_equity = table["air"]  # a Level 1 bot has no category for a gutshot
    if draw_equity > made_equity:
        return reading.draw, -1.0
    return reading.made, float(ORDER.index(reading.made))


def perceive(
    state: DecisionState, profile: Profile, tuning: Tuning, model: EquityModel, rng: random.Random
) -> Perception:
    to_pot = state.to_call / max(state.pot - state.to_call, 1)
    cost = _perceived_cost(state, profile, tuning, to_pot)
    n_opp = len(state.opponents)
    reading = read_hand(state.hole, state.board)
    wet_hand = reading.made in ("strong", "medium") and reading.wet_board
    if profile.hand_strength >= 3:
        buckets = tuple(o.range_percent for o in state.opponents)
        equity = model.equity(state.hole, state.board, buckets, tuning.equity_samples)
        category = "equity"
        flags: dict[str, float] = {}
    else:
        category, place = _read_category(reading, profile)
        flags = {}
        table = profile.category_table
        if place < 0:
            equity = table[category]
        else:
            applied: dict[str, float] = {}
            shift = 0.0
            if profile.board_texture == 2 and reading.scary_board:
                strength = profile.flags.get("scary_board", 0.0)
                shift += strength
                applied["scary_board"] = strength
            if profile.money == 2 and state.bet_ratio >= tuning.money["bigBetRatio"]:
                strength = profile.flags.get("big_bet", 0.0)
                shift += strength
                applied["big_bet"] = strength
            equity = _table_equity(table, place - shift) if shift else table[category]
            flags = {k: v for k, v in applied.items() if v}
        if reading.is_pair and reading.made != "monster":
            equity += profile.misreads.get("pairOvervalue", 0.0)
        elif reading.ace_high and category == "air":
            equity += profile.misreads.get("aceHighOvervalue", 0.0)
        per_extra = tuning.multiway["equityPerExtraOpponent"][profile.multiway]
        equity += per_extra * max(n_opp - 1, 0)
    if profile.noise:
        equity += rng.uniform(-profile.noise, profile.noise)
    return Perception(category, min(max(equity, 0.0), 1.0), cost, flags, wet_hand)


def _perceived_cost(
    state: DecisionState, profile: Profile, tuning: Tuning, true_ratio: float
) -> float:
    """What a call costs in the bot's eyes: true price blended with how big the dollars feel,
    less a sunk-cost discount for money already in."""
    if state.to_call == 0:
        return 0.0
    index = profile.money
    weight = tuning.money["dollarWeight"][index]
    feel = state.to_call / (tuning.money["dollarReferenceBB"] * state.big_blind)
    cost = (1 - weight) * true_ratio + weight * feel
    sunk = tuning.money["sunkCost"][index] * state.invested / max(state.pot, 1)
    return max(cost - sunk, 0.0)
