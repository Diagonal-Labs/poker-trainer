"""Tests for the preflop chart module and the shipped starter charts."""

import json
from pathlib import Path

import pytest

from pokersim.decision_engine.preflop import (
    ChartPolicy,
    action_probabilities,
    all_hand_classes,
    combos,
    hand_class,
    implied_stats,
    parse_range,
    pick_rule,
    pick_rule_index,
    validate_chart,
)

DATA = Path(__file__).resolve().parent.parent / "data"
MIX = json.loads((DATA / "spot_mix.json").read_text())
CHART_FILES = sorted((DATA / "charts").glob("*.json"))

# VPIP / PFR target midpoints from the starter persona table in the design doc.
TARGETS = {
    "l1_basic": (24.0, 6.5),
    "l2_nit": (12.0, 9.5),
    "l2_loose_passive": (60.0, 5.0),
    "l2_wide_aggressive": (60.0, 37.5),
    "l3_solid": (23.0, 17.5),
    "l3_lag": (34.0, 27.0),
}


def test_hand_class_counts() -> None:
    classes = all_hand_classes()
    assert len(classes) == 169
    assert sum(combos(h) for h in classes) == 1326


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("77+", {r * 2: 1.0 for r in "789TJQKA"}),
        ("ATs+", {"ATs": 1.0, "AJs": 1.0, "AQs": 1.0, "AKs": 1.0}),
        ("A5s-A2s", {"A5s": 1.0, "A4s": 1.0, "A3s": 1.0, "A2s": 1.0}),
        ("T9s-65s", {"T9s": 1.0, "98s": 1.0, "87s": 1.0, "76s": 1.0, "65s": 1.0}),
        ("AJo:0.5", {"AJo": 0.5}),
        ("AK", {"AKs": 1.0, "AKo": 1.0}),
        ("TT-88", {"TT": 1.0, "99": 1.0, "88": 1.0}),
        ("", {}),
    ],
)
def test_parse_range(text: str, expected: dict[str, float]) -> None:
    assert parse_range(text) == expected


@pytest.mark.parametrize("bad", ["AXs", "KA", "77s", "A2s-K2s", "JJ-", "AKs:1.5", "AKs:0"])
def test_parse_range_rejects(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_range(bad)


def _minimal_chart() -> dict:
    rule = {"ranges": {"raise": "AA"}}
    return {
        "spots": {
            "open": {"rules": [rule]},
            "vs_limp": {"rules": [rule]},
            "vs_raise": {"rules": [{"ranges": {"3bet": "AA"}}]},
            "vs_3bet": {"rules": [{"ranges": {"4bet": "AA"}}]},
            "vs_4bet": {"rules": [{"ranges": {"5bet": "AA"}}]},
        }
    }


def test_validate_accepts_minimal_chart() -> None:
    assert validate_chart(_minimal_chart()) == []


def test_validate_rejects_overlapping_weights() -> None:
    chart = _minimal_chart()
    chart["spots"]["open"]["rules"] = [{"ranges": {"raise": "AA", "limp": "AA:0.5"}}]
    assert any("AA weights add to" in e for e in validate_chart(chart))


def test_validate_rejects_missing_default_rule() -> None:
    chart = _minimal_chart()
    chart["spots"]["open"]["rules"] = [{"when": {"pos": ["early"]}, "ranges": {"raise": "AA"}}]
    assert any("default rule" in e for e in validate_chart(chart))


def test_validate_rejects_wrong_action_for_spot() -> None:
    chart = _minimal_chart()
    chart["spots"]["open"]["rules"] = [{"ranges": {"3bet": "AA"}}]
    assert any("not allowed" in e for e in validate_chart(chart))


def test_pick_rule_first_match_wins() -> None:
    chart = _minimal_chart()
    early = {"when": {"pos": ["early"]}, "ranges": {"raise": "KK+"}}
    chart["spots"]["open"]["rules"] = [early, {"ranges": {"raise": "AA"}}]
    assert pick_rule(chart, "open", "early") is early
    assert pick_rule(chart, "open", "button")["ranges"] == {"raise": "AA"}


def test_there_are_six_starter_charts() -> None:
    assert {p.stem for p in CHART_FILES} == set(TARGETS)


@pytest.mark.parametrize("path", CHART_FILES, ids=lambda p: p.stem)
def test_starter_chart_is_valid(path: Path) -> None:
    chart = json.loads(path.read_text())
    assert chart["id"] == path.stem
    assert validate_chart(chart) == []


@pytest.mark.parametrize("path", CHART_FILES, ids=lambda p: p.stem)
def test_starter_chart_hits_its_targets(path: Path) -> None:
    chart = json.loads(path.read_text())
    stats = implied_stats(chart, MIX)
    vpip, pfr = TARGETS[path.stem]
    assert stats.vpip * 100 == pytest.approx(vpip, abs=0.5)
    assert stats.pfr * 100 == pytest.approx(pfr, abs=0.5)


# -- slice 3: hand classes, looseness and mix fidelity ---------------------------------------------

RANKING = ["AA", "KK", "AKs", "QQ", "AKo", "JJ", "TT", "99", "88", "77", "66", "55", "44"]
SMALL_CHART = {
    "spots": {
        "open": {"rules": [{"ranges": {"raise": "QQ+,AKs", "limp": "JJ-99:0.5"}}]},
        "vs_raise": {"rules": [{"ranges": {"3bet": "KK+", "call": "QQ-TT"}}]},
    }
}


@pytest.mark.parametrize(
    ("cards", "expected"),
    [
        (("Ah", "Ks"), "AKo"),
        (("Ks", "Ah"), "AKo"),
        (("Ah", "Kh"), "AKs"),
        (("7c", "7d"), "77"),
        (("2d", "Td"), "T2s"),
        (("9s", "Js"), "J9s"),
    ],
)
def test_hand_class(cards: tuple[str, str], expected: str) -> None:
    assert hand_class(cards) == expected


def test_policy_without_looseness_reads_the_chart() -> None:
    policy = ChartPolicy(SMALL_CHART, RANKING)
    assert policy.stated("open", 0, "AA") == {"raise": 1.0}
    assert policy.stated("open", 0, "99") == {"limp": 0.5}
    assert policy.stated("open", 0, "77") == {}


def test_positive_looseness_adds_the_next_classes_with_the_weakest_weights() -> None:
    policy = ChartPolicy(SMALL_CHART, RANKING, looseness_shift=2)
    # the weakest class played is 99 (limp 0.5), so 88 and 77 now limp at 0.5 too
    assert policy.stated("open", 0, "88") == {"limp": 0.5}
    assert policy.stated("open", 0, "77") == {"limp": 0.5}
    assert policy.stated("open", 0, "66") == {}
    assert policy.stated("open", 0, "AA") == {"raise": 1.0}  # the rest is unchanged


def test_negative_looseness_drops_the_weakest_classes() -> None:
    policy = ChartPolicy(SMALL_CHART, RANKING, looseness_shift=-2)
    assert policy.stated("open", 0, "99") == {}
    assert policy.stated("open", 0, "TT") == {}
    assert policy.stated("open", 0, "JJ") == {"limp": 0.5}


def test_looseness_does_not_overwrite_a_class_the_chart_already_lists() -> None:
    policy = ChartPolicy(SMALL_CHART, RANKING, looseness_shift=20)
    assert policy.stated("open", 0, "QQ") == {"raise": 1.0}
    assert policy.stated("open", 0, "44") == {"limp": 0.5}


def test_pick_rule_index_uses_the_position_then_the_default() -> None:
    chart = {
        "spots": {
            "open": {
                "rules": [
                    {"when": {"pos": ["early"]}, "ranges": {}},
                    {"ranges": {}},
                ]
            }
        }
    }
    assert pick_rule_index(chart, "open", "early") == 0
    assert pick_rule_index(chart, "open", "button") == 1


def test_full_mix_fidelity_uses_the_stated_mix() -> None:
    probs = action_probabilities({"call": 0.75}, ("3bet", "call"), 1.0)
    assert probs == {"3bet": 0.0, "call": 0.75, "fold": 0.25}


def test_zero_mix_fidelity_rounds_to_the_most_likely_action() -> None:
    assert action_probabilities({"call": 0.75}, ("3bet", "call"), 0.0) == {
        "3bet": 0.0,
        "call": 1.0,
        "fold": 0.0,
    }
    assert action_probabilities({"call": 0.4}, ("3bet", "call"), 0.0)["fold"] == 1.0
    assert action_probabilities({}, ("3bet", "call"), 0.0)["fold"] == 1.0


def test_partial_mix_fidelity_blends_and_sums_to_one() -> None:
    probs = action_probabilities({"call": 0.75}, ("3bet", "call"), 0.5)
    assert probs["call"] == pytest.approx(0.875)
    assert probs["fold"] == pytest.approx(0.125)
    assert sum(probs.values()) == pytest.approx(1.0)
