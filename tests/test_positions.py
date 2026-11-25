import pytest

from pokersim.game_engine.positions import chart_group, position_names


def test_known_tables() -> None:
    assert position_names(2) == ("BB", "BTN")
    assert position_names(3) == ("SB", "BB", "BTN")
    assert position_names(6) == ("SB", "BB", "UTG", "HJ", "CO", "BTN")
    assert position_names(9) == ("SB", "BB", "UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN")
    assert position_names(10)[2:5] == ("UTG", "UTG+1", "UTG+2")


@pytest.mark.parametrize("n", range(2, 11))
def test_names_are_unique_and_end_with_button(n: int) -> None:
    names = position_names(n)
    assert len(names) == n
    assert len(set(names)) == n
    assert names[-1] == "BTN"


@pytest.mark.parametrize("n", range(2, 11))
def test_every_position_maps_to_a_chart_group(n: int) -> None:
    groups = {chart_group(p) for p in position_names(n)}
    assert groups <= {"early", "middle", "cutoff", "button", "sb", "bb"}


def test_bad_player_counts() -> None:
    for n in (0, 1, 11):
        with pytest.raises(ValueError):
            position_names(n)
