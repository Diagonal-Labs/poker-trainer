import random
from pathlib import Path

import pytest

from pokersim.calibration.simulate import build_bots
from pokersim.decision_engine.choose import choose, final_probabilities, softmax
from pokersim.decision_engine.decision import decide_postflop
from pokersim.decision_engine.decision_state import build_state
from pokersim.decision_engine.equity import EquityModel
from pokersim.decision_engine.hand_category import read_hand
from pokersim.decision_engine.scoring import Candidate
from pokersim.decision_engine.sizing import postflop_menu
from pokersim.storage.persona_library import PersonaLibrary
from tests.helpers import context, new_hand, play

DATA = Path(__file__).resolve().parent.parent / "data"
LIB = PersonaLibrary(DATA)
BOTS = {b.persona.id: b for b in build_bots(LIB, LIB.persona_ids(), 1.0)}


def _flop_context():  # type: ignore[no-untyped-def]
    hand = new_hand()
    play(hand, "fold", "fold", "fold", "call", "call", "check")
    assert len(build_state(context(hand)).board) == 3
    return context(hand)


# --- hand reading ---------------------------------------------------------------------------


def test_made_hand_categories() -> None:
    assert read_hand(("As", "Ad"), ("Ah", "7c", "2d")).made == "monster"  # set
    assert read_hand(("Ks", "Qd"), ("Kh", "7c", "2d")).made in ("strong", "medium")
    assert read_hand(("7s", "6d"), ("Ah", "Kc", "2d")).made == "air"
    assert read_hand(("2s", "2d"), ("Ah", "Kc", "9d")).made in ("weak", "medium")


def test_draws_and_board_flags() -> None:
    flush_draw = read_hand(("As", "Ks"), ("2s", "7s", "Jd"))
    assert flush_draw.draw == "strong_draw"
    assert read_hand(("As", "Ks"), ("2c", "7d", "Jh")).draw == "none"
    assert read_hand(("Ac", "Kd"), ("2s", "7s", "Js")).scary_board


# --- equity ---------------------------------------------------------------------------------


def test_equity_is_deterministic_and_ordered() -> None:
    model = EquityModel(LIB.hand_ranking())
    a = model.equity(("As", "Ad"), ("Kh", "7c", "2d"), (30,))
    assert a == EquityModel(LIB.hand_ranking()).equity(("As", "Ad"), ("Kh", "7c", "2d"), (30,))
    assert a > model.equity(("7s", "3d"), ("Kh", "9c", "2d"), (30,))
    assert 0.0 <= a <= 1.0


def test_more_opponents_means_less_equity() -> None:
    model = EquityModel(LIB.hand_ranking())
    board = ("Kh", "7c", "2d")
    assert model.equity(("As", "Kd"), board, (30,)) > model.equity(("As", "Kd"), board, (30, 30))


# --- selector -------------------------------------------------------------------------------

CANDIDATES = [
    Candidate("fold", "fold", 0, 0.0),
    Candidate("call", "call", 0, 0.2),
    Candidate("raise_3x", "raise", 30, 0.5),
    Candidate("raise_allin", "raise", 100, 0.1),
]


def test_probabilities_sum_to_one() -> None:
    probs = final_probabilities(CANDIDATES, 0.1, 0.05)
    assert sum(probs.values()) == pytest.approx(1.0)
    assert set(probs) == {c.id for c in CANDIDATES}


def test_two_step_equals_one_softmax_when_temperatures_match() -> None:
    probs = final_probabilities(CANDIDATES, 0.1, 0.1)
    one = softmax([c.score for c in CANDIDATES], 0.1)
    for c, p in zip(CANDIDATES, one, strict=True):
        assert probs[c.id] == pytest.approx(p)


def test_low_temperature_picks_the_best() -> None:
    rng = random.Random(1)
    picks = {choose(CANDIDATES, 0.001, 0.001, rng)[0].id for _ in range(50)}
    assert picks == {"raise_3x"}


# --- sizing menu ----------------------------------------------------------------------------


def test_menu_is_sorted_unique_and_within_bounds() -> None:
    ctx = _flop_context()
    bot = BOTS["solid_regular"]
    state = build_state(ctx)
    menu = postflop_menu(state, bot.tuning)
    amounts = [o.amount for o in menu]
    assert menu
    assert amounts == sorted(set(amounts))
    assert all(state.legal.min_raise_to <= a <= state.legal.max_raise_to for a in amounts)


def test_deep_stack_does_not_offer_all_in_into_a_small_pot() -> None:
    ctx = _flop_context()
    menu = postflop_menu(build_state(ctx), BOTS["solid_regular"].tuning)
    assert not any(o.id.endswith("allin") for o in menu)  # 200 behind into a 6 pot


# --- the decision ---------------------------------------------------------------------------


@pytest.mark.parametrize("persona_id", sorted(BOTS))
def test_postflop_decision_is_legal_and_has_a_record(persona_id: str) -> None:
    bot = BOTS[persona_id]
    ctx = _flop_context()
    action = decide_postflop(ctx, bot.profile, bot.tuning, bot.model)[0]
    legal = ctx.legal
    assert action.kind in legal.kinds
    if action.kind in ("bet", "raise"):
        assert legal.min_raise_to <= action.amount <= legal.max_raise_to


def test_postflop_decision_is_deterministic_for_a_seed() -> None:
    bot = BOTS["lag_regular"]
    first = decide_postflop(_flop_context(), bot.profile, bot.tuning, bot.model)
    second = decide_postflop(_flop_context(), bot.profile, bot.tuning, bot.model)
    assert first[0] == second[0]
    assert first[1].probabilities == second[1].probabilities
