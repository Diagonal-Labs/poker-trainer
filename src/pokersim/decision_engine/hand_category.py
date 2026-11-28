"""Reading a made hand and its draws, the way a person would describe it ("top pair, good kicker").

Used by the perception layer for Levels 1 and 2. The reading is true; the persona's level decides
what it makes of it. Categories: monster, strong, medium, weak, air for made hands, and
strong_draw (a flush draw or open-ended straight draw) or weak_draw (a gutshot) for draws.
"""

from __future__ import annotations

from dataclasses import dataclass

from pokersim.decision_engine.eval7_adapter import RANKS, evaluate, hand_type


@dataclass(frozen=True)
class HandReading:
    made: str  # monster, strong, medium, weak or air
    draw: str  # strong_draw, weak_draw or none
    is_pair: bool  # the made hand is one pair that uses a hole card
    ace_high: bool  # no pair, and holding an ace
    scary_board: bool  # a flush or straight is possible on the board and this hand does not have it
    wet_board: bool  # flush or straight draws are possible on the board (a reason to protect)


def _rank(c: str) -> int:
    return RANKS.index(c[0])


def _straight_outs(ranks: set[int], hole: set[int]) -> int:
    """How many ranks complete a five-card straight that uses at least one hole card."""
    with_ace_low: set[int] = set(ranks)
    if 12 in ranks:
        with_ace_low.add(-1)
    outs = 0
    for r in range(13):
        if r in ranks:
            continue
        trial: set[int] = with_ace_low | {r}
        if r == 12:
            trial.add(-1)
        for low in range(-1, 9):
            window = set(range(low, low + 5))
            if (
                window <= trial
                and (r in window)
                and (window & (hole | ({-1} if 12 in hole else set())))
            ):
                outs += 1
                break
    return outs


def _board_features(board: tuple[str, ...]) -> tuple[bool, bool, bool, bool]:
    """(flush possible, four to a straight, two-tone or connected, paired)."""
    suits = [c[1] for c in board]
    ranks = sorted({_rank(c) for c in board})
    flush_possible = max(suits.count(s) for s in set(suits)) >= 3
    two_tone = max(suits.count(s) for s in set(suits)) == 2
    span_windows = [
        sum(1 for r in ranks if low <= r < low + 5) for low in range(-1, 9)
    ]  # ace-low handled by treating the ace as rank -1 below
    if 12 in ranks:
        span_windows += [sum(1 for r in [-1, *ranks] if low <= r < low + 5) for low in range(-1, 1)]
    four_straight = max(span_windows) >= 4
    connected = max(span_windows) >= 3
    paired = len({_rank(c) for c in board}) < len(board)
    return flush_possible, four_straight, two_tone or connected, paired


def read_hand(hole: tuple[str, str], board: tuple[str, ...]) -> HandReading:
    """Classify a hand on a flop, turn or river."""
    value = evaluate((*hole, *board))
    kind = hand_type(value)
    hole_ranks = [_rank(c) for c in hole]
    board_ranks = [_rank(c) for c in board]
    top, second = (
        sorted(set(board_ranks), reverse=True)[:2]
        if len(set(board_ranks)) > 1
        else (
            board_ranks[0],
            -1,
        )
    )
    flush_possible, four_straight, texture, _paired = _board_features(board)
    suit_counts = {s: sum(1 for c in (*hole, *board) if c[1] == s) for s in "cdhs"}
    has_flush = kind in ("Flush", "Straight Flush")
    has_straight = kind in ("Straight", "Straight Flush")
    board_plays = False
    if len(board) == 5:
        board_plays = evaluate(board) == value

    made = "air"
    is_pair = False
    if board_plays:
        made = "air"
    elif kind in ("Straight Flush", "Quads", "Full House", "Flush", "Straight"):
        made = "monster"
    elif kind == "Trips":
        trip_rank = max(
            r for r in set(board_ranks + hole_ranks) if (board_ranks + hole_ranks).count(r) >= 3
        )
        if trip_rank not in hole_ranks:
            made = "air"  # the board holds the trips
        elif hole_ranks[0] == hole_ranks[1]:
            made = "monster"  # a set
        else:
            made = "strong"
    elif kind == "Two Pair":
        all_ranks = board_ranks + hole_ranks
        pairs = sorted((r for r in set(all_ranks) if all_ranks.count(r) >= 2), reverse=True)
        involved = [r for r in pairs if r in hole_ranks]
        if len(involved) >= 2:
            made = "monster" if involved[0] == top else "strong"
        elif involved:
            made, is_pair = _pair_strength(involved[0], hole_ranks, top, second), True
        else:
            made = "air"
    elif kind == "Pair":
        all_ranks = board_ranks + hole_ranks
        pair_rank = next(r for r in set(all_ranks) if all_ranks.count(r) >= 2)
        if pair_rank in hole_ranks:
            made, is_pair = _pair_strength(pair_rank, hole_ranks, top, second), True
    ace_high = made == "air" and 12 in hole_ranks and not board_plays

    draw = "none"
    if len(board) < 5 and made != "monster":
        flush_draw = any(suit_counts[s] == 4 and any(c[1] == s for c in hole) for s in "cdhs")
        outs = _straight_outs(set(hole_ranks + board_ranks), set(hole_ranks))
        if flush_draw or outs >= 2:
            draw = "strong_draw"
        elif outs == 1:
            draw = "weak_draw"

    scary = False
    if made != "monster":
        if flush_possible and not has_flush:
            scary = True
        if four_straight and not has_straight:
            scary = True
    return HandReading(made, draw, is_pair, ace_high, scary, texture)


def _pair_strength(pair_rank: int, hole_ranks: list[int], top: int, second: int) -> str:
    if hole_ranks[0] == hole_ranks[1]:  # a pocket pair
        if pair_rank > top:
            return "strong"  # overpair
        return "medium" if pair_rank > second else "weak"
    kicker = hole_ranks[0] if hole_ranks[1] == pair_rank else hole_ranks[1]
    if pair_rank == top:
        return "strong" if kicker >= RANKS.index("J") else "medium"
    if pair_rank == second:
        return "medium"
    return "weak"
