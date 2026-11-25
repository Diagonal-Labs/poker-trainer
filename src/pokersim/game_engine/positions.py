"""Table position names.

Names are listed in PokerKit's player-index order for a hand: the seat after the button first (the
small blind), the button last. Heads-up the button is the small blind, so the order is BB then BTN.
"""

from __future__ import annotations

_LATE = ("LJ", "HJ", "CO", "BTN")


def position_names(players: int) -> tuple[str, ...]:
    """Position names for a hand with ``players`` players (2 to 10), starting after the button."""
    if not 2 <= players <= 10:
        raise ValueError(f"players must be 2 to 10, got {players}")
    if players == 2:
        return ("BB", "BTN")
    others = players - 2  # everyone except the two blinds
    if others <= 3:
        tail = ("HJ", "CO", "BTN")[3 - others :]
    elif others == 4:
        tail = ("UTG", "HJ", "CO", "BTN")
    else:
        early = ("UTG", *(f"UTG+{k}" for k in range(1, others - 4)))
        tail = (*early, *_LATE)
    return ("SB", "BB", *tail)


def chart_group(position: str) -> str:
    """Map a position name to the position group used by preflop charts."""
    if position.startswith("UTG"):
        return "early"
    return {
        "SB": "sb",
        "BB": "bb",
        "BTN": "button",
        "CO": "cutoff",
        "HJ": "middle",
        "LJ": "middle",
    }[position]
