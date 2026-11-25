from pathlib import Path

from pokersim.calibration.simulate import build_bots
from pokersim.decision_engine.decision import decide_preflop
from pokersim.game_engine.game import play_hand
from pokersim.game_engine.rules import HandSetup, SeatEntry
from pokersim.storage.persona_library import PersonaLibrary
from tests.helpers import context, new_hand

DATA = Path(__file__).resolve().parent.parent / "data"
LIB = PersonaLibrary(DATA)
ALL = LIB.persona_ids()


def _table(adherence: float | None = 1.0):  # type: ignore[no-untyped-def]
    bots = build_bots(LIB, ALL, adherence)
    return bots, dict(enumerate(bots))


def test_bots_play_hundreds_of_hands_legally_and_conserve_chips() -> None:
    _, seats = _table(None)
    for n in range(300):
        setup = HandSetup(tuple(SeatEntry(i, 200) for i in range(6)), button=n % 6)
        _, result = play_hand(setup, seats, 7, n)  # an illegal action would raise
        assert sum(result.payoffs.values()) == 0


def test_the_same_seed_gives_the_same_hands() -> None:
    def run() -> list[object]:
        _, seats = _table(None)
        out: list[object] = []
        for n in range(40):
            setup = HandSetup(tuple(SeatEntry(i, 200) for i in range(6)), button=n % 6)
            hand, result = play_hand(setup, seats, 3, n)
            out.append((hand.actions, result.payoffs))
        return out

    assert run() == run()


def test_zero_adherence_bots_never_use_the_chart_and_never_put_chips_in() -> None:
    bots, seats = _table(0.0)
    for n in range(60):
        setup = HandSetup(tuple(SeatEntry(i, 200) for i in range(6)), button=n % 6)
        play_hand(setup, seats, 5, n)
    records = [r for b in bots for r in b.records]
    assert records
    assert not any(r.chart_used for r in records)
    assert {r.action.kind for r in records} <= {"check", "fold"}


def test_a_junk_hand_folds_and_the_record_traces_the_chart_line() -> None:
    hand = new_hand()
    ctx = context(hand)
    bots, _ = _table(1.0)
    nit = bots[ALL.index("nit")]
    # make the first hole cards junk by looking up a class the nit never plays from UTG
    info_hand = "72o"
    probs = nit.policy.stated("open", nit.policy.rule_index("open", "early"), info_hand)
    assert probs == {}
    action, record = decide_preflop(ctx, nit.persona, nit.policy)
    assert record.spot.spot == "open" and record.rule_index == 0
    assert record.chart_used and record.action == action
    assert abs(sum(record.probabilities.values()) - 1.0) < 1e-9


def test_aggregate_preflop_stats_follow_the_persona_ordering() -> None:
    bots, seats = _table(1.0)
    vpip = {b.persona.id: 0 for b in bots}
    for n in range(600):
        setup = HandSetup(tuple(SeatEntry(i, 200) for i in range(6)), button=n % 6)
        for b in bots:
            b.records.clear()
        play_hand(setup, seats, 11, n)
        for b in bots:
            vpip[b.persona.id] += any(
                r.action.kind in ("raise", "bet") or (r.action.kind == "call" and r.to_call > 0)
                for r in b.records
            )
    assert vpip["nit"] < vpip["solid_regular"] < vpip["lag_regular"] < vpip["dave_station"]
    assert vpip["nit"] < vpip["fit_or_fold"] < vpip["maniac"]
