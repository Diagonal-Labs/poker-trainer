from pokersim.decision_engine.sizing import OPEN_MULTIPLES, preflop_raise_to
from pokersim.decision_engine.spot import find_spot
from pokersim.game_engine.rules import HandSetup, SeatEntry
from tests.helpers import context, new_hand, play, six_handed


def _size(hand, seed: int = 1) -> int:  # type: ignore[no-untyped-def]
    ctx = context(hand, seed)
    return preflop_raise_to(find_spot(ctx), ctx)


def test_open_raises_are_three_to_five_big_blinds() -> None:
    sizes = {_size(new_hand(), seed) for seed in range(40)}
    assert sizes == {2 * m for m in OPEN_MULTIPLES}


def test_isolation_adds_two_and_a_half_big_blinds_per_limper() -> None:
    hand = play(new_hand(), "call", "call")  # two limpers, HJ to act
    sizes = {_size(hand, seed) for seed in range(40)}
    assert sizes == {2 * m + 5 * 2 for m in OPEN_MULTIPLES}


def test_three_bet_is_3x_in_position_and_4x_out_of_position() -> None:
    hand = new_hand()
    play(hand, "raise")  # UTG raises to 4 (the minimum)
    play(hand, "fold", "fold")  # HJ and CO fold; the button acts
    assert context(hand).snapshot.seats[5].position == "BTN"
    assert _size(hand) == 12
    hand2 = new_hand()
    play(hand2, "raise", "fold", "fold", "fold")  # the SB acts, out of position
    assert _size(hand2) == 16


def test_a_raise_over_half_the_stack_becomes_a_shove() -> None:
    setup = HandSetup(tuple(SeatEntry(i, 10 if i == 2 else 200) for i in range(6)), button=5)
    ctx = context(new_hand(setup))
    assert ctx.seat == 2
    assert preflop_raise_to(find_spot(ctx), ctx) == 10


def test_sizes_stay_within_the_legal_range_everywhere() -> None:
    for seed in range(30):
        hand = new_hand(six_handed(60), seed)
        for _ in range(4):
            ctx = context(hand, seed)
            size = preflop_raise_to(find_spot(ctx), ctx)
            assert ctx.legal.min_raise_to <= size <= ctx.legal.max_raise_to
            play(hand, "raise")
