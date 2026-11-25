"""Which preflop spot a decision is in, read from the public action log.

The five spots are defined in the design doc ("Preflop chart format"): open, vs_limp, vs_raise,
vs_3bet and vs_4bet. A forced blind or straddle is not an action, so it never counts as a limp
or a raise.
"""

from __future__ import annotations

from dataclasses import dataclass

from pokersim.game_engine.positions import chart_group
from pokersim.game_engine.seats import DecisionContext


@dataclass(frozen=True)
class SpotInfo:
    spot: str
    position_group: str  # early, middle, cutoff, button, sb or bb
    raises: int  # raises made so far this hand, by anyone
    limpers: int  # calls before the first raise


def find_spot(ctx: DecisionContext) -> SpotInfo:
    raises = limpers = 0
    for _, action in ctx.history:
        if action.kind in ("bet", "raise"):
            raises += 1
        elif action.kind == "call" and raises == 0:
            limpers += 1
    if raises == 0:
        spot = "vs_limp" if limpers else "open"
    elif raises == 1:
        spot = "vs_raise"
    elif raises == 2:
        spot = "vs_3bet"
    else:
        spot = "vs_4bet"
    position = next(s.position for s in ctx.snapshot.seats if s.seat == ctx.seat)
    return SpotInfo(spot, chart_group(position), raises, limpers)
