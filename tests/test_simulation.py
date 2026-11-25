from pathlib import Path

from pokersim.calibration.simulate import pct, report, simulate, simulate_range
from pokersim.storage.persona_library import PersonaLibrary

DATA = Path(__file__).resolve().parent.parent / "data"
LIB = PersonaLibrary(DATA)
IDS = LIB.persona_ids()


def test_every_seat_is_dealt_every_hand() -> None:
    result = simulate_range(DATA, IDS, 0, 60, 1, 1.0)
    assert result.hands == 60
    assert all(c.hands == 60 for c in result.by_persona.values())
    assert sum(c.hands for k, c in result.by_position.items()) == 60 * len(IDS)


def test_results_do_not_depend_on_the_number_of_workers() -> None:
    one = simulate(DATA, IDS, 80, seed=2, chart_adherence=1.0, workers=1)
    two = simulate(DATA, IDS, 80, seed=2, chart_adherence=1.0, workers=2)
    assert one.by_persona == two.by_persona
    assert one.first_spot == two.first_spot


def test_pfr_never_exceeds_vpip_and_personas_are_ordered() -> None:
    result = simulate(DATA, IDS, 900, seed=4, chart_adherence=1.0, workers=1)
    for c in result.by_persona.values():
        assert c.pfr <= c.vpip <= c.hands
    vpip = {p: pct(c.vpip, c.hands) for p, c in result.by_persona.items()}
    assert vpip["nit"] < vpip["solid_regular"] < vpip["lag_regular"] < vpip["maniac"]
    assert vpip["nit"] < vpip["fit_or_fold"] < vpip["dave_station"]


def test_report_lists_each_persona_with_its_targets() -> None:
    text = report(simulate(DATA, IDS, 30, seed=1, chart_adherence=1.0, workers=1), LIB)
    assert text.count("\n") == len(IDS)
    assert "dave_station" in text and "50-70" in text
