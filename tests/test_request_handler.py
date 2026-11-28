"""API smoke test."""

from fastapi.testclient import TestClient

from pokersim import __version__
from pokersim.request_handler.app import create_app


def test_health() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


PERSONAS = ["dave_station", "fit_or_fold", "lag_regular", "maniac", "nit", "solid_regular"]


def _seats(stacks: dict[int, int] | None = None) -> list[dict[str, object]]:
    stacks = stacks or {i: 200 for i in range(6)}
    return [
        {"seat": i, "personaId": None if i == 0 else PERSONAS[i - 1], "stack": stacks[i]}
        for i in range(6)
    ]


def _play_hand(client: TestClient, number: int, button: int, stacks: dict[int, int]):  # type: ignore[no-untyped-def]
    body: dict[str, object] = {
        "seed": 5,
        "handNumber": number,
        "button": button,
        "seats": _seats(stacks),
        "actions": [],
    }
    for _ in range(60):
        response = client.post("/api/hand", json=body)
        assert response.status_code == 200, response.text
        view = response.json()
        body["actions"] = view["actions"]
        if view["complete"]:
            return view
        legal = view["legal"]
        assert view["waitingFor"] == view["hero"] and legal
        kinds = legal["kinds"]
        if "show" in kinds:
            act = {"kind": "show", "amount": 0}
        elif "call" in kinds:
            act = {"kind": "call", "amount": 0}
        else:
            act = {"kind": "check", "amount": 0}
        body["actions"] = [*view["actions"], act]
    raise AssertionError("hand did not finish")


def test_playing_many_hands_through_the_api_conserves_chips() -> None:
    client = TestClient(create_app())
    stacks = {i: 200 for i in range(6)}
    button = 5
    for n in range(12):
        view = _play_hand(client, n, button, stacks)
        assert sum(view["result"]["payoffs"].values()) == 0
        nxt = view["next"]
        assert nxt["handNumber"] == n + 1
        stacks = {int(k): v for k, v in nxt["stacks"].items()}
        button = nxt["button"]


def test_the_same_request_gives_the_same_table() -> None:
    client = TestClient(create_app())
    body = {"seed": 9, "handNumber": 2, "button": 3, "seats": _seats(), "actions": []}
    assert client.post("/api/hand", json=body).json() == client.post("/api/hand", json=body).json()


def test_the_player_sees_only_their_own_cards_and_bot_reasons_on_new_actions() -> None:
    client = TestClient(create_app())
    body = {"seed": 4, "handNumber": 0, "button": 2, "seats": _seats(), "actions": []}
    view = client.post("/api/hand", json=body).json()
    assert [bool(s["cards"]) for s in view["seats"]] == [True, False, False, False, False, False]
    bot_events = [e for e in view["events"] if e["seat"] != view["hero"]]
    assert bot_events and all(e["reason"] for e in bot_events)


def test_an_illegal_action_is_rejected() -> None:
    client = TestClient(create_app())
    body = {"seed": 4, "handNumber": 0, "button": 2, "seats": _seats(), "actions": []}
    view = client.post("/api/hand", json=body).json()
    body["actions"] = [*view["actions"], {"kind": "raise", "amount": 99999}]
    assert client.post("/api/hand", json=body).status_code == 422


def test_exactly_one_human_seat_is_required() -> None:
    client = TestClient(create_app())
    seats = _seats()
    seats[1]["personaId"] = None
    body = {"seed": 1, "handNumber": 0, "button": 2, "seats": seats, "actions": []}
    assert client.post("/api/hand", json=body).status_code == 422


def test_personas_endpoint_lists_the_starters() -> None:
    names = {p["id"] for p in TestClient(create_app()).get("/api/personas").json()}
    assert names == set(PERSONAS)


def test_the_web_page_is_served() -> None:
    page = TestClient(create_app()).get("/")
    assert page.status_code == 200
    assert "Poker trainer" in page.text
