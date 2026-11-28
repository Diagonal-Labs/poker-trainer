"""Request and response shapes for the hand endpoint (Pydantic, since they are the API edge)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SeatIn(_Model):
    seat: int = Field(ge=0, le=9)
    personaId: str | None = None  # None marks the human seat
    stack: int = Field(gt=0)


class ActionIn(_Model):
    kind: Literal["fold", "check", "call", "bet", "raise", "show", "muck", "runout"]
    amount: int = 0


class HandRequest(_Model):
    """A whole hand, stateless: the seed, the setup and every action so far."""

    seed: int
    handNumber: int = Field(ge=0)
    button: int
    seats: list[SeatIn] = Field(min_length=2, max_length=10)
    actions: list[ActionIn] = []

    @model_validator(mode="after")
    def _one_human(self) -> HandRequest:
        if sum(1 for s in self.seats if s.personaId is None) != 1:
            raise ValueError("exactly one seat must be the human (personaId null)")
        return self


class SeatOut(_Model):
    seat: int
    name: str
    personaId: str | None
    position: str
    stack: int
    bet: int
    inHand: bool
    allIn: bool
    isButton: bool
    cards: list[str] | None  # the human's cards always; others only once shown at showdown


class LegalOut(_Model):
    kinds: list[str]
    callAmount: int
    minRaiseTo: int
    maxRaiseTo: int


class EventOut(_Model):
    index: int
    seat: int
    street: str
    kind: str
    amount: int
    reason: str | None = None  # why a bot acted; only for actions made in this request


class ResultOut(_Model):
    payoffs: dict[int, int]
    finalStacks: dict[int, int]
    wentToShowdown: bool


class NextHandOut(_Model):
    handNumber: int
    button: int
    stacks: dict[int, int]


class HandResponse(_Model):
    actions: list[ActionIn]  # the full list, to send back with the next action
    events: list[EventOut]
    street: str
    board: list[str]
    pot: int
    seats: list[SeatOut]
    hero: int
    waitingFor: int | None
    legal: LegalOut | None
    complete: bool
    result: ResultOut | None = None
    next: NextHandOut | None = None
