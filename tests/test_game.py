"""Tests for the game loop: determinism, replay parity, human turns and chip accounting."""

from __future__ import annotations

import time

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pokersim.game_engine.game import (
    derive_rng,
    next_button,
    play_hand,
    replay_hand,
    run_until_human_turn,
    start_hand,
)
from pokersim.game_engine.rules import Action, HandSetup, SeatEntry
from pokersim.game_engine.seats import CheckCallSeat, HumanSeat, RandomSeat, Seat


def table(stacks: dict[int, int], button: int, straddle: int | None = None) -> HandSetup:
    return HandSetup(tuple(SeatEntry(s, v) for s, v in stacks.items()), button, 1, 2, straddle)


def random_seats(setup: HandSetup) -> dict[int, Seat]:
    return {e.seat: RandomSeat() for e in setup.seats}


def test_derive_rng_is_stable_and_streams_differ() -> None:
    assert derive_rng(7, 3, "deck").random() == derive_rng(7, 3, "deck").random()
    assert derive_rng(7, 3, "deck").random() != derive_rng(7, 4, "deck").random()
    assert derive_rng(7, 3, "deck").random() != derive_rng(7, 3, "action").random()
    assert derive_rng(7, 3, "action", 1).random() != derive_rng(7, 3, "action", 2).random()


def test_next_button_skips_empty_seats_and_wraps() -> None:
    assert next_button([1, 3, 4, 9], 3) == 4
    assert next_button([1, 3, 4, 9], 4) == 9
    assert next_button([1, 3, 4, 9], 9) == 1
    assert next_button([1, 3, 4, 9], 2) == 3  # the previous button's seat may have left


def test_same_seed_plays_the_same_hand_and_other_seeds_differ() -> None:
    setup = table({s: 200 for s in range(6)}, button=2)
    a, ra = play_hand(setup, random_seats(setup), seed=11, hand_number=1)
    b, rb = play_hand(setup, random_seats(setup), seed=11, hand_number=1)
    c, _ = play_hand(setup, random_seats(setup), seed=11, hand_number=2)
    assert a.history == b.history
    assert ra == rb
    assert a.history != c.history


def test_game_stops_at_a_human_seat_and_resumes() -> None:
    setup = table({0: 100, 1: 100, 2: 100}, button=2)
    seats: dict[int, Seat] = {0: HumanSeat(), 1: CheckCallSeat(), 2: CheckCallSeat()}
    hand = start_hand(setup, seed=1, hand_number=1)
    step = run_until_human_turn(hand, seats, 1, 1)  # the button limps, then the small blind is up
    assert not step.complete
    assert step.waiting_for == 0
    assert hand.actor == 0
    hand.apply(Action("fold"))  # the human folds the small blind
    step = run_until_human_turn(hand, seats, 1, 1)
    assert step.complete
    assert hand.result().payoffs[0] == -1


def test_play_hand_rejects_human_seats() -> None:
    setup = table({0: 100, 1: 100}, button=1)
    with pytest.raises(ValueError, match="human"):
        play_hand(setup, {0: CheckCallSeat(), 1: HumanSeat()}, seed=1, hand_number=1)


def test_replay_of_a_26_action_style_hand_is_fast() -> None:
    setup = table({s: 300 for s in range(6)}, button=0)
    hand, _ = play_hand(setup, random_seats(setup), seed=5, hand_number=1)
    actions = hand.actions
    start = time.perf_counter()
    for _ in range(50):
        replay_hand(setup, 5, 1, actions)
    per_replay_ms = (time.perf_counter() - start) / 50 * 1000
    assert per_replay_ms < 25, f"replay took {per_replay_ms:.1f} ms for {len(actions)} actions"


@st.composite
def tables(draw: st.DrawFn) -> HandSetup:
    n = draw(st.integers(min_value=2, max_value=9))
    seat_numbers = draw(st.lists(st.integers(0, 9), min_size=n, max_size=n, unique=True))
    stacks = draw(st.lists(st.integers(1, 600), min_size=n, max_size=n))
    button = draw(st.sampled_from(seat_numbers))
    straddle = draw(st.sampled_from([None, 4, 6])) if n >= 4 else None
    return HandSetup(
        tuple(SeatEntry(s, v) for s, v in zip(seat_numbers, stacks, strict=True)),
        button,
        1,
        2,
        straddle,
    )


@settings(
    max_examples=150,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(setup=tables(), seed=st.integers(0, 10_000), hand_number=st.integers(1, 50))
def test_random_hands_conserve_chips_and_replay_exactly(
    setup: HandSetup, seed: int, hand_number: int
) -> None:
    hand, result = play_hand(setup, random_seats(setup), seed, hand_number)

    # chips are conserved and nobody goes negative
    assert sum(result.payoffs.values()) == 0
    start = {e.seat: e.stack for e in setup.seats}
    assert result.final_stacks == {s: start[s] + p for s, p in result.payoffs.items()}
    assert all(v >= 0 for v in result.final_stacks.values())

    # every dealt card is unique
    cards = [c for e in setup.seats for c in hand.hole_cards(e.seat)] + list(result.board)
    assert len(cards) == len(set(cards))

    # rebuilding from setup, seed and the action list gives the identical hand
    again = replay_hand(setup, seed, hand_number, hand.actions)
    assert again.history == hand.history
    assert again.result() == result
    assert again.snapshot() == hand.snapshot()


@pytest.mark.parametrize(
    ("stacks", "button", "seed"),
    [
        ([37, 146], 0, 13),  # all-in preflop: the board is dealt only after the showdown starts
        ([16, 137, 42, 52, 116, 28], 5, 11),  # side pot whose last contender must not muck
        ([2, 26, 36], 0, 38),  # a stack no bigger than the big blind
    ],
)
def test_known_pokerkit_edge_cases_play_to_completion(
    stacks: list[int], button: int, seed: int
) -> None:
    setup = HandSetup(tuple(SeatEntry(i, s) for i, s in enumerate(stacks)), button)
    seats = {i: RandomSeat() for i in range(len(stacks))}
    _, result = play_hand(setup, seats, seed, 1)
    assert sum(result.final_stacks.values()) == sum(stacks)
