"""Tests for the PokerKit wrapper: blinds, legal options, live rules and chip accounting."""

from __future__ import annotations

import random

import pytest

from pokersim.game_engine.rules import (
    Action,
    HandSetup,
    IllegalAction,
    RulesHand,
    SeatEntry,
)

ALL_CARDS = [r + s for r in "23456789TJQKA" for s in "cdhs"]


def setup_of(stacks: dict[int, int], button: int, **kw: int | None) -> HandSetup:
    return HandSetup(tuple(SeatEntry(s, st) for s, st in stacks.items()), button, **kw)  # type: ignore[arg-type]


def rigged(setup: HandSetup, holes: dict[int, tuple[str, str]], board: list[str]) -> RulesHand:
    """A hand with chosen hole cards and board. Dealing is round robin from the small blind, then
    a burn before each of the flop, turn and river."""
    by_seat = sorted(e.seat for e in setup.seats)
    pos = by_seat.index(setup.button)
    order = by_seat[pos + 1 :] + by_seat[: pos + 1]
    n = len(order)
    used = {c for pair in holes.values() for c in pair} | set(board)
    spare = [c for c in ALL_CARDS if c not in used]
    deck: list[str] = []
    for rnd in (0, 1):
        deck += [holes[s][rnd] for s in order]
    deck += [spare.pop(), *board[:3], spare.pop(), board[3], spare.pop(), board[4]]
    deck += spare
    hand = RulesHand(setup, deck)
    for s in order:
        assert hand.hole_cards(s) == holes[s], f"deal order assumption broken for seat {s} (n={n})"
    return hand


def finish(hand: RulesHand) -> None:
    """Check or call to the end, showing every hand."""
    while hand.phase != "complete":
        legal = hand.legal()
        assert legal is not None
        if hand.phase == "runout":
            hand.apply(Action("runout", 1))
        elif "show" in legal.kinds:
            hand.apply(Action("show"))
        else:
            hand.apply(Action("check" if "check" in legal.kinds else "call"))


def shove_all(hand: RulesHand) -> None:
    while hand.phase == "betting":
        legal = hand.legal()
        assert legal is not None
        if "raise" in legal.kinds or "bet" in legal.kinds:
            kind = "raise" if "raise" in legal.kinds else "bet"
            hand.apply(Action(kind, legal.max_raise_to))
        else:
            hand.apply(Action("call"))


# -- setup -------------------------------------------------------------------------------------


def test_setup_validation() -> None:
    with pytest.raises(ValueError, match="2 to 10"):
        setup_of({1: 100}, 1).validate()
    with pytest.raises(ValueError, match="button"):
        setup_of({1: 100, 2: 100}, 5).validate()
    with pytest.raises(ValueError, match="positive"):
        setup_of({1: 100, 2: 0}, 1).validate()
    with pytest.raises(ValueError, match="at least 4"):
        setup_of({1: 100, 2: 100, 3: 100}, 1, straddle=4).validate()
    with pytest.raises(ValueError, match="twice"):
        setup_of({i: 100 for i in range(5)}, 0, straddle=3).validate()


# -- blinds, order and legal options -----------------------------------------------------------


def test_six_handed_blinds_positions_and_first_actor() -> None:
    setup = setup_of({1: 200, 3: 200, 4: 200, 6: 200, 7: 200, 9: 200}, button=4)
    hand = RulesHand.start(setup, random.Random(1))
    snap = hand.snapshot()
    pos = {s.seat: s.position for s in snap.seats}
    assert pos == {6: "SB", 7: "BB", 9: "UTG", 1: "HJ", 3: "CO", 4: "BTN"}
    bets = {s.seat: s.bet for s in snap.seats}
    assert bets == {6: 1, 7: 2, 9: 0, 1: 0, 3: 0, 4: 0}
    assert hand.actor == 9
    legal = hand.legal()
    assert legal is not None
    assert legal.kinds == ("fold", "call", "raise")
    assert (legal.call_amount, legal.min_raise_to, legal.max_raise_to) == (2, 4, 200)


def test_straddle_posts_and_acts_last() -> None:
    setup = setup_of({s: 200 for s in range(6)}, button=5, straddle=4)
    hand = RulesHand.start(setup, random.Random(1))
    snap = hand.snapshot()
    assert {s.seat: s.bet for s in snap.seats} == {0: 1, 1: 2, 2: 4, 3: 0, 4: 0, 5: 0}
    assert hand.actor == 3  # the seat after the straddle
    legal = hand.legal()
    assert legal is not None
    assert (legal.call_amount, legal.min_raise_to) == (4, 6)
    for seat in (3, 4, 5, 0, 1):  # everyone calls
        assert hand.actor == seat
        hand.apply(Action("call"))
    assert hand.actor == 2  # the straddler has the option
    option = hand.legal()
    assert option is not None
    assert "check" in option.kinds
    assert "raise" in option.kinds


def test_heads_up_button_is_small_blind_acts_first_preflop_and_last_after() -> None:
    hand = RulesHand.start(setup_of({2: 100, 5: 100}, button=5), random.Random(3))
    snap = hand.snapshot()
    assert {s.seat: (s.position, s.bet) for s in snap.seats} == {2: ("BB", 2), 5: ("BTN", 1)}
    assert hand.actor == 5
    hand.apply(Action("call"))
    hand.apply(Action("check"))  # big blind checks the option
    assert hand.snapshot().street == "flop"
    assert hand.actor == 2  # the big blind acts first after the flop


def test_big_blind_option_after_limps_can_check_or_raise_but_not_fold() -> None:
    hand = RulesHand.start(setup_of({0: 100, 1: 100, 2: 100}, button=2), random.Random(1))
    hand.apply(Action("call"))  # button limps
    hand.apply(Action("call"))  # small blind completes
    legal = hand.legal()
    assert legal is not None
    assert hand.actor == 1
    assert legal.kinds == ("check", "raise")


@pytest.mark.parametrize(
    "action",
    [
        Action("check"),  # facing the blind
        Action("bet", 10),  # a raise, not a bet
        Action("raise", 3),  # below the minimum raise
        Action("raise", 201),  # above the stack
        Action("show"),
        Action("runout", 1),
    ],
)
def test_illegal_actions_are_rejected(action: Action) -> None:
    setup = setup_of({s: 200 for s in range(4)}, button=3)
    hand = RulesHand.start(setup, random.Random(1))
    before = hand.snapshot()
    with pytest.raises(IllegalAction):
        hand.apply(action)
    assert hand.snapshot() == before  # nothing changed


def test_cannot_call_when_a_check_is_available() -> None:
    hand = RulesHand.start(setup_of({0: 100, 1: 100}, button=1), random.Random(1))
    hand.apply(Action("call"))
    with pytest.raises(IllegalAction):
        hand.apply(Action("call"))  # the big blind may check, not call
    with pytest.raises(IllegalAction):
        hand.apply(Action("fold"))  # folding when a check is free is not allowed


# -- chips: side pots, uncalled bets, short all-ins, odd chips --------------------------------


def test_all_in_side_pots_conserve_chips() -> None:
    stacks = {0: 50, 1: 120, 2: 300, 3: 300, 4: 300, 5: 300}
    hand = RulesHand.start(setup_of(stacks, button=5), random.Random(9))
    shove_all(hand)
    assert hand.phase == "runout"
    legal = hand.legal()
    assert legal is not None
    assert legal.kinds == ("runout",)
    finish(hand)
    result = hand.result()
    assert sum(result.payoffs.values()) == 0
    assert sum(result.final_stacks.values()) == sum(stacks.values())
    assert all(v >= 0 for v in result.final_stacks.values())
    assert len(result.board) == 5


def test_only_a_single_runout_is_supported() -> None:
    hand = RulesHand.start(setup_of({0: 100, 1: 100}, button=1), random.Random(2))
    shove_all(hand)
    with pytest.raises(IllegalAction):
        hand.apply(Action("runout", 2))
    confirmations = 0
    while hand.phase == "runout":  # each remaining player confirms in turn
        hand.apply(Action("runout", 1))
        confirmations += 1
    assert confirmations == 2
    assert hand.phase == "showdown"


def test_uncalled_bet_is_returned() -> None:
    hand = RulesHand.start(setup_of({0: 100, 1: 100}, button=1), random.Random(2))
    hand.apply(Action("raise", 100))  # the button shoves
    hand.apply(Action("fold"))
    result = hand.result()
    assert result.payoffs == {0: -2, 1: 2}  # wins only the big blind
    assert not result.went_to_showdown


def test_short_all_in_does_not_reopen_raising_for_the_original_raiser() -> None:
    stacks = {0: 200, 1: 200, 2: 200, 3: 25, 4: 200, 5: 200}
    hand = RulesHand.start(setup_of(stacks, button=5), random.Random(3))
    assert hand.actor == 2
    hand.apply(Action("raise", 20))  # seat 2 opens to 20 (a raise of 18)
    assert hand.actor == 3
    hand.apply(Action("raise", 25))  # seat 3 is all-in for 25, only 5 more: not a full raise
    for seat in (4, 5, 0, 1):
        assert hand.actor == seat
        hand.apply(Action("call"))
    assert hand.actor == 2
    legal = hand.legal()
    assert legal is not None
    assert legal.kinds == ("fold", "call")  # may call 5 more, may not raise again


def test_odd_chip_goes_to_first_winner_left_of_the_button() -> None:
    setup = setup_of({0: 100, 1: 100, 2: 100}, button=2)  # 0 small blind, 1 big blind, 2 button
    hand = rigged(
        setup,
        {0: ("7c", "2d"), 1: ("As", "Kh"), 2: ("Ad", "Kc")},
        ["9h", "5s", "2c", "3d", "8h"],
    )
    hand.apply(Action("raise", 10))  # button raises
    hand.apply(Action("fold"))  # small blind folds, leaving a dead chip
    hand.apply(Action("call"))  # big blind calls
    finish(hand)  # check down, both show: an exact chop of a 21 chip pot
    result = hand.result()
    assert result.payoffs == {0: -1, 1: 1, 2: 0}  # the big blind is first left of the button
    assert sum(result.payoffs.values()) == 0


# -- showdown ---------------------------------------------------------------------------------


def test_mucking_the_best_hand_loses_and_only_shown_cards_are_published() -> None:
    setup = setup_of({0: 100, 1: 100}, button=1)
    hand = rigged(setup, {0: ("Ks", "Kd"), 1: ("As", "Ah")}, ["2c", "7d", "9h", "Jc", "3s"])
    while hand.phase == "betting":
        legal = hand.legal()
        assert legal is not None
        hand.apply(Action("check" if "check" in legal.kinds else "call"))
    assert hand.phase == "showdown"
    first = hand.actor
    assert first is not None
    other = 1 - first
    best = 1  # aces
    legal = hand.legal()
    assert legal is not None
    assert legal.kinds == ("show", "muck")
    if first == best:
        hand.apply(Action("muck"))  # the winner mucks and loses
        if hand.phase == "showdown":
            hand.apply(Action("show"))
        winner = other
    else:
        hand.apply(Action("show"))
        if hand.phase == "showdown":
            hand.apply(Action("muck"))  # aces loses by mucking
        winner = other if other != best else first
    result = hand.result()
    assert result.went_to_showdown
    assert result.payoffs[winner] > 0
    assert set(result.shown) <= {0, 1}
    assert all(len(cards) == 2 for cards in result.shown.values())


def test_no_showdown_when_everyone_folds_so_no_cards_are_shown() -> None:
    hand = RulesHand.start(setup_of({0: 100, 1: 100, 2: 100}, button=2), random.Random(1))
    hand.apply(Action("fold"))
    hand.apply(Action("fold"))
    result = hand.result()
    assert not result.went_to_showdown
    assert result.shown == {}
    assert result.payoffs == {0: -1, 1: 1, 2: 0}


def test_result_requires_a_finished_hand() -> None:
    hand = RulesHand.start(setup_of({0: 100, 1: 100}, button=1), random.Random(1))
    with pytest.raises(RuntimeError):
        hand.result()


def test_the_same_deck_seed_deals_the_same_cards() -> None:
    setup = setup_of({0: 100, 1: 100, 2: 100}, button=0)
    a = RulesHand.start(setup, random.Random(5))
    b = RulesHand.start(setup, random.Random(5))
    c = RulesHand.start(setup, random.Random(6))
    cards = lambda h: [h.hole_cards(s) for s in (0, 1, 2)]  # noqa: E731
    assert cards(a) == cards(b)
    assert cards(a) != cards(c)


def test_last_hand_cannot_muck_when_everyone_else_mucked() -> None:
    hand = RulesHand.start(setup_of({0: 100, 1: 100, 2: 100}, button=2), random.Random(2))
    while hand.phase == "betting":
        legal = hand.legal()
        assert legal is not None
        hand.apply(Action("check" if "check" in legal.kinds else "call"))
    hand.apply(Action("muck"))
    hand.apply(Action("muck"))
    legal = hand.legal()
    assert legal is not None
    assert legal.kinds == ("show",)  # a pot with nobody to win it would burn chips
    with pytest.raises(IllegalAction):
        hand.apply(Action("muck"))
    hand.apply(Action("show"))
    result = hand.result()
    assert sum(result.payoffs.values()) == 0
    assert max(result.payoffs.values()) > 0
