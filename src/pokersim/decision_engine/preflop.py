"""Preflop charts: range-string parser, chart validation and implied-stat reporting.

Pure functions on plain dicts. Loading chart files from disk happens outside the Decision engine.
Format reference: the "Preflop chart format" section of the design doc.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, TypeAlias

RANKS = "23456789TJQKA"
POSITIONS = ("early", "middle", "cutoff", "button", "sb", "bb")
SPOT_ACTIONS: dict[str, tuple[str, str]] = {
    "open": ("raise", "limp"),
    "vs_limp": ("raise", "call"),
    "vs_raise": ("3bet", "call"),
    "vs_3bet": ("4bet", "call"),
    "vs_4bet": ("5bet", "call"),
}
RAISE_ACTIONS = frozenset({"raise", "3bet", "4bet", "5bet"})
TOTAL_COMBOS = 1326

_TOKEN = re.compile(
    r"^([2-9TJQKA])([2-9TJQKA])([so]?)(?:(\+)|-([2-9TJQKA])([2-9TJQKA])([so]?))?"
    r"(?::(\d(?:\.\d+)?))?$"
)

Chart: TypeAlias = dict[str, Any]
Rule: TypeAlias = dict[str, Any]


def combos(hand: str) -> int:
    """Number of card combinations in a hand class such as 'AA', 'AKs' or 'AKo'."""
    if len(hand) == 2:
        return 6
    return 4 if hand[2] == "s" else 12


def all_hand_classes() -> list[str]:
    """All 169 hand classes, pairs and high cards first."""
    out: list[str] = []
    for i in range(12, -1, -1):
        for j in range(i, -1, -1):
            if i == j:
                out.append(RANKS[i] * 2)
            else:
                out += [RANKS[i] + RANKS[j] + "s", RANKS[i] + RANKS[j] + "o"]
    return out


def parse_range(text: str) -> dict[str, float]:
    """Turn a range string into {hand class: weight}. Raises ValueError naming the bad token."""
    out: dict[str, float] = {}
    if not text:
        return out
    for raw in text.split(","):
        tok = raw.strip()
        m = _TOKEN.match(tok)
        if not m:
            raise ValueError(f"bad token {tok!r}")
        a, b, suit, plus, a2, b2, suit2, w_text = m.groups()
        weight = float(w_text) if w_text is not None else 1.0
        if not 0 < weight <= 1:
            raise ValueError(f"weight out of range in {tok!r}")
        ia, ib = RANKS.index(a), RANKS.index(b)
        hands: list[str]
        if a == b:
            hands = _pair_span(tok, ia, plus, a2, b2, suit)
        else:
            if ia < ib:
                raise ValueError(f"high card first in {tok!r}")
            if suit == "":  # 'AK' means suited and offsuit
                hands = []
                for sx in "so":
                    sub = f"{a}{b}{sx}" + ("+" if plus else "") + (f"-{a2}{b2}{sx}" if a2 else "")
                    hands += list(parse_range(sub))
            else:
                hands = _span(tok, ia, ib, suit, plus, a2, b2, suit2)
        for hand in hands:
            out[hand] = out.get(hand, 0.0) + weight
    return out


def _pair_span(
    tok: str, ia: int, plus: str | None, a2: str | None, b2: str | None, suit: str
) -> list[str]:
    if suit:
        raise ValueError(f"pair with suit in {tok!r}")
    if plus:
        lo, hi = ia, 12
    elif a2:
        if a2 != b2:
            raise ValueError(f"bad pair span {tok!r}")
        lo, hi = sorted((ia, RANKS.index(a2)))
    else:
        lo = hi = ia
    return [RANKS[i] * 2 for i in range(lo, hi + 1)]


def _span(
    tok: str,
    ia: int,
    ib: int,
    suit: str,
    plus: str | None,
    a2: str | None,
    b2: str | None,
    suit2: str,
) -> list[str]:
    if plus:
        seq = [(ia, j) for j in range(ib, ia)]
    elif a2 and b2:
        ia2, ib2 = RANKS.index(a2), RANKS.index(b2)
        if suit2 != suit:
            raise ValueError(f"mixed suit span {tok!r}")
        if ia2 == ia:
            seq = [(ia, j) for j in range(min(ib, ib2), max(ib, ib2) + 1)]
        elif ia - ib == ia2 - ib2:
            gap = ia - ib
            seq = [(i, i - gap) for i in range(min(ia, ia2), max(ia, ia2) + 1)]
        else:
            raise ValueError(f"span must share the first card or the gap: {tok!r}")
    else:
        seq = [(ia, ib)]
    return [RANKS[i] + RANKS[j] + suit for i, j in seq]


def validate_chart(chart: Chart) -> list[str]:
    """Return a list of error messages. An empty list means the chart is valid."""
    errs: list[str] = []
    spots: dict[str, Any] = chart.get("spots", {})
    if set(spots) != set(SPOT_ACTIONS):
        errs.append("spots must be exactly " + ", ".join(SPOT_ACTIONS))
    for spot, body in spots.items():
        rules: list[Rule] = body.get("rules", [])
        if not rules or "when" in rules[-1]:
            errs.append(f"spots.{spot}: last rule must be a default rule with no 'when'")
        for k, rule in enumerate(rules):
            errs += _validate_rule(spot, k, rule)
    return errs


def _validate_rule(spot: str, k: int, rule: Rule) -> list[str]:
    errs: list[str] = []
    totals: dict[str, float] = {}
    where = f"spots.{spot}.rules[{k}]"
    for action, text in rule.get("ranges", {}).items():
        if action not in SPOT_ACTIONS.get(spot, ()):
            errs.append(f"{where}: action {action!r} not allowed in this spot")
        try:
            for hand, w in parse_range(text).items():
                totals[hand] = totals.get(hand, 0.0) + w
        except ValueError as e:
            errs.append(f"{where}.{action}: {e}")
    errs += [f"{where}: {h} weights add to {w:.2f}" for h, w in totals.items() if w > 1.0001]
    return errs


def pick_rule_index(chart: Chart, spot: str, pos: str) -> int:
    """Index of the first rule in the spot whose conditions match. The last rule is the default.

    Only the ``pos`` condition is read so far. ``raiserPos``, ``callers``/``limpers`` and ``depth``
    are in the chart format but no starter chart uses them yet.
    """
    rules: list[Rule] = chart["spots"][spot]["rules"]
    for k, rule in enumerate(rules):
        when = rule.get("when")
        if when is None or pos in when.get("pos", [pos]):
            return k
    raise ValueError(f"no default rule in spot {spot!r}")


def pick_rule(chart: Chart, spot: str, pos: str) -> Rule:
    """The rule that applies to a position in a spot."""
    rule: Rule = chart["spots"][spot]["rules"][pick_rule_index(chart, spot, pos)]
    return rule


def action_frequencies(rule: Rule) -> dict[str, float]:
    """Share of all hands that take each action in a rule (fold is the remainder)."""
    return {
        action: sum(w * combos(h) for h, w in parse_range(text).items()) / TOTAL_COMBOS
        for action, text in rule["ranges"].items()
    }


@dataclass(frozen=True)
class ImpliedStats:
    """A chart's implied VPIP and PFR under an assumed spot mix, as fractions of hands."""

    vpip: float
    pfr: float
    by_position: dict[str, tuple[float, float]]


def implied_stats(chart: Chart, spot_mix: dict[str, Any]) -> ImpliedStats:
    """Implied VPIP and PFR. ``spot_mix`` has the shape of data/spot_mix.json."""
    weights: dict[str, float] = spot_mix["positionWeights"]
    total_weight = sum(weights.values())
    vpip = pfr = 0.0
    by_pos: dict[str, tuple[float, float]] = {}
    for pos in POSITIONS:
        v = p = 0.0
        for spot, prob in spot_mix["mix"][pos].items():
            if prob == 0:
                continue
            freqs = action_frequencies(pick_rule(chart, spot, pos))
            raising = sum(x for a, x in freqs.items() if a in RAISE_ACTIONS)
            continuing = raising if (pos == "bb" and spot == "vs_limp") else sum(freqs.values())
            v += prob * continuing  # a free check from the big blind is not VPIP
            p += prob * raising
        by_pos[pos] = (v, p)
        vpip += weights[pos] * v / total_weight
        pfr += weights[pos] * p / total_weight
    return ImpliedStats(vpip, pfr, by_pos)


def hand_class(cards: tuple[str, str]) -> str:
    """The hand class of two cards such as ('Ah', 'Ks'): 'AKo'. Pairs are 'QQ'."""
    (r1, s1), (r2, s2) = cards[0], cards[1]
    if r1 == r2:
        return r1 + r2
    hi, lo = (r1, r2) if RANKS.index(r1) > RANKS.index(r2) else (r2, r1)
    return hi + lo + ("s" if s1 == s2 else "o")


class ChartPolicy:
    """A chart prepared for fast lookups, with the persona's looseness applied.

    ``looseness_shift`` is a number of hand classes. Positive: for every rule, the next classes
    down ``ranking`` (strongest first) are treated as if they were in the range, with the action
    weights of the weakest class the rule already plays. Negative: the weakest classes it plays
    are dropped. See "How the decision engine uses a chart" in the design doc.
    """

    def __init__(self, chart: Chart, ranking: list[str], looseness_shift: int = 0) -> None:
        self.chart = chart
        self._rank = {hand: i for i, hand in enumerate(ranking)}
        self._ranking = ranking
        self._shift = looseness_shift
        self._tables: dict[tuple[str, int], dict[str, dict[str, float]]] = {}

    def rule_index(self, spot: str, pos: str) -> int:
        return pick_rule_index(self.chart, spot, pos)

    def stated(self, spot: str, rule_index: int, hand: str) -> dict[str, float]:
        """The chart's action weights for a hand in a rule, after looseness. Fold is the rest."""
        key = (spot, rule_index)
        table = self._tables.get(key)
        if table is None:
            table = self._tables[key] = self._build(self.chart["spots"][spot]["rules"][rule_index])
        return table.get(hand, {})

    def _build(self, rule: Rule) -> dict[str, dict[str, float]]:
        table: dict[str, dict[str, float]] = {}
        for action, text in rule["ranges"].items():
            for hand, weight in parse_range(text).items():
                if weight > 0:
                    table.setdefault(hand, {})[action] = weight
        if not table or self._shift == 0:
            return table
        by_strength = sorted(table, key=lambda h: self._rank[h])
        if self._shift < 0:
            for hand in by_strength[self._shift :]:
                del table[hand]
            return table
        weakest = by_strength[-1]
        start = self._rank[weakest] + 1
        for hand in self._ranking[start : start + self._shift]:
            table.setdefault(hand, dict(table[weakest]))
        return table


def action_probabilities(
    stated: dict[str, float], actions: tuple[str, ...], mix_fidelity: float
) -> dict[str, float]:
    """Final action probabilities, fold included, after mix fidelity.

    At fidelity 1 the chart's mix is used as written. At 0 the mix is rounded to its most likely
    action (call 75% / fold 25% becomes always call). In between, the two are blended.
    """
    probs = {a: stated.get(a, 0.0) for a in actions}
    probs["fold"] = max(0.0, 1.0 - sum(probs.values()))
    if mix_fidelity >= 1.0:
        return probs
    top = max(probs, key=lambda a: probs[a])  # ties keep the first, so a raise beats a fold
    return {
        a: mix_fidelity * p + (1.0 - mix_fidelity) * (1.0 if a == top else 0.0)
        for a, p in probs.items()
    }
