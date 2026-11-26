"""The acting player's decision state: what a real player could see, nothing hidden.

Built from the public snapshot, the player's own cards and the action log. Opponents are described
by a range bucket read from how they have played this hand, never by their real cards.
"""

from __future__ import annotations

from dataclasses import dataclass

from pokersim.decision_engine.equity import nearest_bucket
from pokersim.game_engine.rules import LegalOptions
from pokersim.game_engine.seats import DecisionContext

# Share of starting hands (percent) an opponent is assumed to hold after a preflop action.
_RAISE_RANGE = (30, 12, 6, 4)  # first raise, 3-bet, 4-bet, 5-bet and up
_CALL_RANGE = (35, 20, 12)  # a call of the first raise, of a 3-bet, of more
_LIMP_RANGE = 60
_BLIND_RANGE = 65
_BET_NARROWS = 0.8  # a postflop bet or raise keeps this share of the range
_CALL_NARROWS = 0.9
_BET_FLOOR = 30  # a bettor's range always includes some bluffs and thin value


@dataclass(frozen=True)
class Opponent:
    seat: int
    position: str
    stack: int
    all_in: bool
    range_percent: int  # one of equity.BUCKETS


@dataclass(frozen=True)
class DecisionState:
    street: str
    hole: tuple[str, str]
    board: tuple[str, ...]
    pot: int  # including bets on this street
    to_call: int
    my_bet: int  # chips already put in on this street
    stack: int  # chips behind
    big_blind: int
    bet_ratio: float  # the bet faced, as a share of the pot before it (0 when none)
    opponents: tuple[Opponent, ...]  # players still in the hand
    in_position: bool  # last to act among the players left
    spr: float  # effective stack divided by the pot
    invested: int  # chips put in over the whole hand
    preflop_aggressor: bool
    legal: LegalOptions

    @property
    def facing_bet(self) -> bool:
        return self.to_call > 0

    @property
    def active_opponents(self) -> tuple[Opponent, ...]:
        return tuple(o for o in self.opponents if not o.all_in)


def opponent_ranges(ctx: DecisionContext) -> tuple[dict[int, int], int | None]:
    """Range percent per seat from the action log, and the last preflop raiser."""
    pct: dict[int, float] = {s.seat: _BLIND_RANGE for s in ctx.snapshot.seats}
    raises = 0
    raiser: int | None = None
    streets = ctx.history_streets or ("preflop",) * len(ctx.history)
    for (seat, action), street in zip(ctx.history, streets, strict=True):
        if street == "preflop":
            if action.kind in ("bet", "raise"):
                raises += 1
                raiser = seat
                pct[seat] = _RAISE_RANGE[min(raises - 1, 3)]
            elif action.kind == "call":
                pct[seat] = _LIMP_RANGE if raises == 0 else _CALL_RANGE[min(raises - 1, 2)]
        elif action.kind in ("bet", "raise"):
            pct[seat] = max(min(pct[seat], _BET_FLOOR), pct[seat] * _BET_NARROWS)
        elif action.kind == "call":
            pct[seat] *= _CALL_NARROWS
    return {seat: nearest_bucket(p) for seat, p in pct.items()}, raiser


def _in_position(ctx: DecisionContext) -> bool:
    """Postflop the first seat left of the button acts first and the button last."""
    snap = ctx.snapshot
    in_hand = [s.seat for s in snap.seats if s.in_hand]
    seats = sorted(s.seat for s in snap.seats)
    order = [x for x in seats if x > snap.button] + [x for x in seats if x <= snap.button]
    left = [x for x in order if x in in_hand]
    return bool(left) and left[-1] == ctx.seat


def build_state(ctx: DecisionContext) -> DecisionState:
    snap = ctx.snapshot
    me = next(s for s in snap.seats if s.seat == ctx.seat)
    ranges, raiser = opponent_ranges(ctx)
    opponents = tuple(
        Opponent(s.seat, s.position, s.stack, s.all_in, ranges[s.seat])
        for s in snap.seats
        if s.in_hand and s.seat != ctx.seat
    )
    to_call = ctx.legal.call_amount
    pot_before = snap.pot - to_call
    bet_ratio = to_call / pot_before if to_call > 0 and pot_before > 0 else 0.0
    covering = max((o.stack for o in opponents if not o.all_in), default=0)
    effective = min(me.stack, covering) if covering else me.stack
    return DecisionState(
        street=snap.street,
        hole=ctx.hole_cards,
        board=snap.board,
        pot=snap.pot,
        to_call=to_call,
        my_bet=me.bet,
        stack=me.stack,
        big_blind=snap.big_blind,
        bet_ratio=bet_ratio,
        opponents=opponents,
        in_position=_in_position(ctx),
        spr=effective / snap.pot if snap.pot else 0.0,
        invested=me.invested,
        preflop_aggressor=raiser == ctx.seat,
        legal=ctx.legal,
    )
