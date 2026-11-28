"""Plays a hand forward for the web table: rebuild it, run the bots, describe what the player sees.

Stateless: the request carries the seed, the setup and every action so far. Bots do not decide again
for actions already taken (the replay applies them), so a hand always comes back the same.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from pokersim.decision_engine.bot_factory import make_bot
from pokersim.decision_engine.bot_seat import BotSeat
from pokersim.decision_engine.equity import EquityModel
from pokersim.decision_engine.presets import Tuning
from pokersim.game_engine.game import next_button, replay_hand, run_until_human_turn, start_hand
from pokersim.game_engine.rules import Action, HandSetup, IllegalAction, RulesHand, SeatEntry
from pokersim.game_engine.seats import HumanSeat, Seat
from pokersim.request_handler.models import (
    ActionIn,
    EventOut,
    HandRequest,
    HandResponse,
    LegalOut,
    NextHandOut,
    ResultOut,
    SeatOut,
)
from pokersim.storage.persona_library import PersonaLibrary

REBUY = 200  # chips a busted seat is topped up to for the next hand
HUMAN_NAME = "You"


class _World:
    """Everything loaded from data/ once: the tables the bots share."""

    def __init__(self, data_dir: Path) -> None:
        self.library = PersonaLibrary(data_dir)
        self.ranking = self.library.hand_ranking()
        self.presets = self.library.presets()
        scales = self.library.bias_scales()
        self.tuning = Tuning.from_data(self.presets, scales)
        self.looseness_scale = scales["looseness"]["classesPerUnit"]
        self.model = EquityModel(self.ranking)  # its cache is pure, so sharing it is safe

    def bot(self, persona_id: str) -> BotSeat:
        persona = self.library.persona(persona_id)
        chart = self.library.chart(persona.preflop.chart)
        return make_bot(
            persona,
            chart,
            self.ranking,
            self.presets,
            self.looseness_scale,
            self.tuning,
            self.model,
        )


@lru_cache(maxsize=4)
def _world(data_dir: Path) -> _World:
    return _World(data_dir)


def personas(data_dir: Path) -> list[dict[str, object]]:
    library = _world(data_dir).library
    out: list[dict[str, object]] = []
    for pid in library.persona_ids():
        p = library.persona(pid)
        out.append({"id": p.id, "name": p.name, "description": p.description})
    return out


def _reason(bot: BotSeat, street: str, action: Action) -> str | None:
    if street == "preflop" and bot.records:
        r = bot.records.pop(0)
        odds = " ".join(f"{a} {p:.0%}" for a, p in r.probabilities.items() if p > 0)
        if not r.chart_used:
            return f"{r.hand} {r.spot.spot}: forgot the chart, so {action.kind}"
        return f"{r.hand} {r.spot.spot}, chart rule {r.rule_index}: {odds}"
    if street != "preflop" and bot.postflop_records:
        q = bot.postflop_records.pop(0)
        top = sorted(q.probabilities.items(), key=lambda kv: -kv[1])[:3]
        odds = " ".join(f"{a} {p:.0%}" for a, p in top)
        flags = f" [{','.join(q.perception.flags)}]" if q.perception.flags else ""
        return f"sees {q.perception.category}, equity {q.perception.equity:.2f}{flags}: {odds}"
    return None


def _setup(req: HandRequest) -> HandSetup:
    setup = HandSetup(tuple(SeatEntry(s.seat, s.stack) for s in req.seats), button=req.button)
    setup.validate()
    return setup


def play(req: HandRequest, data_dir: Path) -> HandResponse:
    """Replay the hand from the request, run bots to the human's turn, and describe the result."""
    world = _world(data_dir)
    setup = _setup(req)
    hero = next(s.seat for s in req.seats if s.personaId is None)
    bots: dict[int, BotSeat] = {
        s.seat: world.bot(s.personaId) for s in req.seats if s.personaId is not None
    }
    seats: Mapping[int, Seat] = {**bots, hero: HumanSeat()}
    actions = [Action(a.kind, a.amount) for a in req.actions]
    try:
        hand = (
            replay_hand(setup, req.seed, req.handNumber, actions)
            if actions
            else start_hand(setup, req.seed, req.handNumber)
        )
    except IllegalAction as exc:
        raise ValueError(str(exc)) from exc
    known = len(hand.history)
    step = run_until_human_turn(hand, seats, req.seed, req.handNumber)
    return _describe(req, hand, bots, hero, known, step.waiting_for, step.complete)


def _describe(
    req: HandRequest,
    hand: RulesHand,
    bots: dict[int, BotSeat],
    hero: int,
    known: int,
    waiting_for: int | None,
    complete: bool,
) -> HandResponse:
    names = {s.seat: HUMAN_NAME for s in req.seats if s.personaId is None}
    for s in req.seats:
        if s.personaId is not None:
            names[s.seat] = bots[s.seat].persona.name
    snap = hand.snapshot()
    result = hand.result() if complete else None
    shown = result.shown if result else {}
    events: list[EventOut] = []
    for i, ((seat, act), street) in enumerate(zip(hand.history, hand.history_streets, strict=True)):
        reason = None
        if i >= known and seat in bots and act.kind in ("fold", "check", "call", "bet", "raise"):
            reason = _reason(bots[seat], street, act)
        events.append(
            EventOut(
                index=i, seat=seat, street=street, kind=act.kind, amount=act.amount, reason=reason
            )
        )
    persona_of = {s.seat: s.personaId for s in req.seats}
    out_seats: list[SeatOut] = []
    for s in snap.seats:
        cards: list[str] | None = None
        if s.seat == hero:
            cards = list(hand.hole_cards(hero))
        elif s.seat in shown:
            cards = list(shown[s.seat])
        out_seats.append(
            SeatOut(
                seat=s.seat,
                name=names[s.seat],
                personaId=persona_of[s.seat],
                position=s.position,
                stack=s.stack,
                bet=s.bet,
                inHand=s.in_hand,
                allIn=s.all_in,
                isButton=s.seat == snap.button,
                cards=cards,
            )
        )
    legal = hand.legal() if waiting_for == hero else None
    legal_out = (
        LegalOut(
            kinds=list(legal.kinds),
            callAmount=legal.call_amount,
            minRaiseTo=legal.min_raise_to,
            maxRaiseTo=legal.max_raise_to,
        )
        if legal
        else None
    )
    result_out = next_out = None
    if result is not None:
        result_out = ResultOut(
            payoffs=result.payoffs,
            finalStacks=result.final_stacks,
            wentToShowdown=result.went_to_showdown,
        )
        stacks = {
            seat: (stack if stack > 0 else REBUY) for seat, stack in result.final_stacks.items()
        }
        next_out = NextHandOut(
            handNumber=req.handNumber + 1,
            button=next_button(list(stacks), req.button),
            stacks=stacks,
        )
    return HandResponse(
        actions=[ActionIn(kind=a.kind, amount=a.amount) for a in hand.actions],
        events=events,
        street=snap.street,
        board=list(snap.board),
        pot=snap.pot,
        seats=out_seats,
        hero=hero,
        waitingFor=waiting_for,
        legal=legal_out,
        complete=complete,
        result=result_out,
        next=next_out,
    )
