"""Equity by sampling, with eval7, against opponents holding hands from range buckets.

A bucket is "the top N percent of starting hands" (by the hand ranking). Opponents are described
by a bucket each, never by their real cards. The estimate is a pure function of its inputs: the
sampling generator is seeded from them, so the cache cannot change a result and runs replay exactly.
"""

from __future__ import annotations

import random
from itertools import combinations

from pokersim.decision_engine.eval7_adapter import RANKS, evaluate

BUCKETS = (3, 6, 10, 15, 20, 30, 40, 55, 75, 100)  # percent of starting hands
_ALL_CARDS = [r + s for r in RANKS for s in "cdhs"]


def nearest_bucket(percent: float) -> int:
    return min(BUCKETS, key=lambda b: abs(b - percent))


def _class_combos(hand_class: str) -> list[tuple[str, str]]:
    hi, lo = hand_class[0], hand_class[1]
    if hi == lo:
        return [(a, b) for a, b in combinations([hi + s for s in "cdhs"], 2)]
    if hand_class.endswith("s"):
        return [(hi + s, lo + s) for s in "cdhs"]
    return [(hi + a, lo + b) for a in "cdhs" for b in "cdhs" if a != b]


class EquityModel:
    def __init__(self, ranking: list[str]) -> None:
        self._ranking = ranking
        self._buckets: dict[int, list[tuple[str, str]]] = {}
        self._cache: dict[tuple[object, ...], float] = {}

    def bucket_combos(self, percent: int) -> list[tuple[str, str]]:
        cached = self._buckets.get(percent)
        if cached is not None:
            return cached
        target = 1326 * percent / 100
        built: list[tuple[str, str]] = []
        for hand_class in self._ranking:
            built += _class_combos(hand_class)
            if len(built) >= target:
                break
        self._buckets[percent] = built
        return built

    def equity(
        self,
        hole: tuple[str, str],
        board: tuple[str, ...],
        opponents: tuple[int, ...],
        samples: int = 300,
    ) -> float:
        """Chance to win (a tie counts half) against one hand from each opponent bucket."""
        key = (tuple(sorted(hole)), board, tuple(sorted(opponents)), samples)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        rng = random.Random(f"equity:{key}")
        known = set(hole) | set(board)
        wins = 0.0
        done = 0
        pools = [self.bucket_combos(b) for b in key[2]]
        for _ in range(samples):
            dead = set(known)
            hands: list[tuple[str, str]] = []
            for pool in pools:
                for _try in range(30):
                    pick = rng.choice(pool)
                    if pick[0] not in dead and pick[1] not in dead:
                        break
                else:
                    break
                hands.append(pick)
                dead.update(pick)
            if len(hands) != len(pools):
                continue
            rest = [c for c in _ALL_CARDS if c not in dead]
            full = [*board, *rng.sample(rest, 5 - len(board))]
            mine = evaluate([*hole, *full])
            best = max(evaluate([*h, *full]) for h in hands)
            wins += 1.0 if mine > best else 0.5 if mine == best else 0.0
            done += 1
        result = wins / done if done else 0.5
        self._cache[key] = result
        return result
