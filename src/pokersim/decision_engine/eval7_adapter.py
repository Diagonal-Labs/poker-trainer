# pyright: basic
"""The only module that imports eval7. eval7 has no type information, so this adapter gives the
rest of the Decision engine typed functions: ``evaluate`` (higher is better) and ``hand_type``."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import eval7

RANKS = "23456789TJQKA"
_CARDS: dict[str, Any] = {r + s: eval7.Card(r + s) for r in RANKS for s in "cdhs"}


def evaluate(cards: Sequence[str]) -> int:
    """Strength of the best five of five to seven cards such as 'Ah'. Higher wins."""
    return int(eval7.evaluate([_CARDS[c] for c in cards]))


def hand_type(strength: int) -> str:
    """'High Card', 'Pair', 'Two Pair', 'Trips', 'Straight', 'Flush', 'Full House', 'Quads' or
    'Straight Flush'."""
    return str(eval7.handtype(strength))
