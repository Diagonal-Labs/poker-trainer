"""Preflop raise sizes, using live-game norms. Charts say whether to raise, not how much.

Open raises are 3, 4 or 5 big blinds, an isolation raise adds 2.5 big blinds per limper, a 3-bet is
3x the raise in position and 4x out of position, a 4-bet is about 2.3x, and a 5-bet is all-in. A
raise that would commit more than half the stack becomes all-in. Level-based sizing styles and
the favored-size biases from the design doc arrive with the sizing step in a later slice.
"""

from __future__ import annotations

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
