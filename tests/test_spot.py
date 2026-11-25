from pokersim.decision_engine.spot import find_spot
from tests.helpers import context, new_hand, play


def test_first_to_act_is_an_open_from_early_position() -> None:
    info = find_spot(context(new_hand()))
    assert (info.spot, info.position_group, info.raises, info.limpers) == ("open", "early", 0, 0)


def test_a_limp_makes_the_next_spot_vs_limp() -> None:
    info = find_spot(context(play(new_hand(), "call")))
    assert (info.spot, info.position_group, info.limpers) == ("vs_limp", "middle", 1)


def test_big_blind_facing_limpers_is_vs_limp_with_a_free_check() -> None:
    hand = play(new_hand(), "call", "call", "call", "call", "call")  # to the BB option
    ctx = context(hand)
    assert ctx.seat == 1 and "check" in ctx.legal.kinds
    info = find_spot(ctx)
    assert (info.spot, info.position_group, info.limpers) == ("vs_limp", "bb", 5)


def test_each_raise_moves_to_the_next_spot() -> None:
    hand = new_hand()
    spots = []
    for _ in range(4):
        spots.append(find_spot(context(hand)).spot)
        play(hand, "raise")
    spots.append(find_spot(context(hand)).spot)
    assert spots == ["open", "vs_raise", "vs_3bet", "vs_4bet", "vs_4bet"]


def test_calls_after_a_raise_do_not_count_as_limpers() -> None:
    hand = play(new_hand(), "raise", "call", "call")
    info = find_spot(context(hand))
    assert (info.spot, info.limpers, info.raises) == ("vs_raise", 0, 1)


def test_the_small_blind_and_button_get_their_own_groups() -> None:
    hand = play(new_hand(), "fold", "fold", "fold")  # to the button
    assert find_spot(context(hand)).position_group == "button"
    hand = play(hand, "fold")
    assert find_spot(context(hand)).position_group == "sb"
