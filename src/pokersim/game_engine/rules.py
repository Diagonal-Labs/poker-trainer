# pyright: basic
# This is the only module that imports PokerKit, which is only partly typed. The rest of the engine
# sees our own fully typed classes below.
"""Poker rules for one hand of no-limit hold'em cash-game play, wrapping PokerKit.

Everything outside this module uses the types defined here (``Action``, ``LegalOptions``,
``HandSnapshot``, ``HandResult``) and table seat numbers, never PokerKit objects or player indices.

A hand is fully determined by its ``HandSetup``, the shuffling generator and the list of actions.
``RulesHand.replay`` rebuilds a hand from those three, which is how the server restores a hand.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

from pokerkit import Automation, Deck, Mode, NoLimitTexasHoldem

from pokersim.game_engine.positions import position_names

ActionKind = Literal["fold", "check", "call", "bet", "raise", "show", "muck", "runout"]
Phase = Literal["betting", "runout", "showdown", "complete"]
STREETS = ("preflop", "flop", "turn", "river")

_AUTOMATIONS = (
    Automation.ANTE_POSTING,
    Automation.BET_COLLECTION,
    Automation.BLIND_OR_STRADDLE_POSTING,
    Automation.HAND_KILLING,
    Automation.CHIPS_PUSHING,
    Automation.CHIPS_PULLING,
)


def _req(value: int | None) -> int:
    """PokerKit types many numbers as optional. Narrow them where a value must exist."""
    if value is None:
        raise RuntimeError("PokerKit returned no value where one was expected")  # pragma: no cover
    return value


class IllegalAction(ValueError):
    """Raised when an action is not allowed in the current state."""


@dataclass(frozen=True)
class Action:
    """One action. ``amount`` is the total bet-to for a bet or raise, and the count for a runout."""

    kind: ActionKind
    amount: int = 0


@dataclass(frozen=True)
class SeatEntry:
    """A player in the hand: a table seat number and the stack they start the hand with."""

    seat: int
    stack: int


@dataclass(frozen=True)
class HandSetup:
    """Everything needed to start a hand, apart from the shuffle."""

    seats: tuple[SeatEntry, ...]
    button: int
    small_blind: int = 1
    big_blind: int = 2
    straddle: int | None = None  # an under-the-gun straddle, such as 4 at $1/$2

    def validate(self) -> None:
        seats = [e.seat for e in self.seats]
        if len(seats) < 2 or len(seats) > 10:
            raise ValueError("a hand needs 2 to 10 players")
        if len(set(seats)) != len(seats):
            raise ValueError("duplicate seat numbers")
        if self.button not in seats:
            raise ValueError("the button must be one of the seated players")
        if any(e.stack <= 0 for e in self.seats):
            raise ValueError("every stack must be positive")
        if not 0 < self.small_blind <= self.big_blind:
            raise ValueError("blinds must satisfy 0 < small blind <= big blind")
        if self.straddle is not None:
            if len(seats) < 4:
                raise ValueError("a straddle needs at least 4 players (no button straddle in V1)")
            if self.straddle < 2 * self.big_blind:
                raise ValueError("a straddle must be at least twice the big blind")


@dataclass(frozen=True)
class LegalOptions:
    """What the acting seat may do. For a bet or raise, any amount from min to max is allowed."""

    seat: int
    kinds: tuple[ActionKind, ...]
    call_amount: int = 0  # chips needed to call, capped at the stack
    min_raise_to: int = 0
    max_raise_to: int = 0  # the whole stack, as a total bet-to


@dataclass(frozen=True)
class SeatSnapshot:
    seat: int
    position: str
    stack: int
    bet: int  # chips put in on the current street
    in_hand: bool
    all_in: bool


@dataclass(frozen=True)
class HandSnapshot:
    """The public picture of the hand. Hole cards are separate, see ``RulesHand.hole_cards``."""

    phase: Phase
    street: str
    board: tuple[str, ...]
    pot: int  # including bets on the current street
    seats: tuple[SeatSnapshot, ...]
    actor: int | None
    button: int
    small_blind: int
    big_blind: int


@dataclass(frozen=True)
class HandResult:
    payoffs: dict[int, int]  # net chips won or lost, by seat
    final_stacks: dict[int, int]
    board: tuple[str, ...]
    went_to_showdown: bool
    shown: dict[int, tuple[str, str]]  # hole cards revealed at showdown, by seat


class RulesHand:
    """One hand in progress. Build it with ``start`` or ``replay``."""

    def __init__(self, setup: HandSetup, deck: list[str]) -> None:
        setup.validate()
        self.setup = setup
        # PokerKit player order: the seat after the button first, the button last.
        by_seat = sorted(setup.seats, key=lambda e: e.seat)
        pos = next(i for i, e in enumerate(by_seat) if e.seat == setup.button)
        ordered = by_seat[pos + 1 :] + by_seat[: pos + 1]
        self._seat_of = [e.seat for e in ordered]
        self._index_of = {s: i for i, s in enumerate(self._seat_of)}
        self._positions = dict(zip(self._seat_of, position_names(len(ordered)), strict=True))
        blinds = (setup.small_blind, setup.big_blind)
        if setup.straddle is not None:
            blinds = (*blinds, setup.straddle)
        self._start_stacks = {e.seat: e.stack for e in setup.seats}
        self._st = NoLimitTexasHoldem.create_state(
            _AUTOMATIONS,
            True,
            0,
            blinds,
            setup.big_blind,
            tuple(e.stack for e in ordered),
            len(ordered),
            mode=Mode.CASH_GAME,
        )
        self._deck = deck
        self._next_card = 0
        self.history: list[tuple[int, Action]] = []
        self._shown: dict[int, tuple[str, str]] = {}
        self._phase: Phase | None = None  # cached: working it out makes PokerKit rank hands
        self._pump()
        # keep every player's hole cards: PokerKit drops a hand's cards once it is mucked or killed
        self._hole = {
            seat: (repr(self._st.hole_cards[i][0]), repr(self._st.hole_cards[i][1]))
            for i, seat in enumerate(self._seat_of)
        }

    # -- construction --------------------------------------------------------------------------

    @classmethod
    def start(cls, setup: HandSetup, rng: random.Random) -> RulesHand:
        """Start a hand, shuffling a standard deck with ``rng``."""
        deck = [repr(c) for c in Deck.STANDARD]
        rng.shuffle(deck)
        return cls(setup, deck)

    @classmethod
    def replay(cls, setup: HandSetup, rng: random.Random, actions: list[Action]) -> RulesHand:
        """Rebuild a hand from its setup, the same generator state and its action list."""
        hand = cls.start(setup, rng)
        for action in actions:
            hand.apply(action)
        return hand

    # -- dealing -------------------------------------------------------------------------------

    def _take(self, count: int = 1) -> str:
        cards = self._deck[self._next_card : self._next_card + count]
        self._next_card += count
        return "".join(cards)

    def _pump(self) -> None:
        """Deal hole cards, burns and board cards from our own deck until a decision is needed."""
        st = self._st
        self._phase = None  # the state is about to change
        while True:
            if st.can_deal_hole():
                st.deal_hole(self._take())
            elif st.can_burn_card():
                st.burn_card(self._take())
            elif st.can_deal_board():
                st.deal_board(self._take(_req(st.board_dealing_count)))
            else:
                return

    # -- state ---------------------------------------------------------------------------------

    @property
    def phase(self) -> Phase:
        if self._phase is None:
            self._phase = self._work_out_phase()
        return self._phase

    def _work_out_phase(self) -> Phase:
        st = self._st
        if not st.status:
            return "complete"
        if st.actor_index is not None:
            return "betting"
        if st.can_select_runout_count():
            return "runout"
        if st.can_show_or_muck_hole_cards():
            return "showdown"
        raise RuntimeError("hand is stuck: no actor and nothing to do")  # pragma: no cover

    @property
    def actor(self) -> int | None:
        """The seat that must act now, for a bet or a show-or-muck choice. None otherwise."""
        st = self._st
        if self.phase == "betting":
            return self._seat_of[_req(st.actor_index)]
        if self.phase == "showdown":
            return self._seat_of[_req(st.showdown_index)]
        return None

    def position(self, seat: int) -> str:
        return self._positions[seat]

    def hole_cards(self, seat: int) -> tuple[str, str]:
        return self._hole[seat]

    @property
    def board(self) -> tuple[str, ...]:
        return tuple(repr(c) for slot in self._st.board_cards for c in slot)

    def snapshot(self) -> HandSnapshot:
        st = self._st
        seats = []
        for seat in sorted(self._seat_of):
            i = self._index_of[seat]
            in_hand = bool(st.statuses[i])
            seats.append(
                SeatSnapshot(
                    seat=seat,
                    position=self._positions[seat],
                    stack=int(st.stacks[i]),
                    bet=int(st.bets[i]),
                    in_hand=in_hand,
                    all_in=in_hand and st.stacks[i] == 0,
                )
            )
        return HandSnapshot(
            phase=self.phase,
            street=STREETS[min(st.street_index or 0, 3)],
            board=self.board,
            pot=int(st.total_pot_amount),
            seats=tuple(seats),
            actor=self.actor,
            button=self.setup.button,
            small_blind=self.setup.small_blind,
            big_blind=self.setup.big_blind,
        )

    def legal(self) -> LegalOptions | None:
        """Legal options for the current actor, or None when nobody has a choice."""
        st = self._st
        phase = self.phase
        if phase == "betting":
            index = _req(st.actor_index)
            stack = int(st.stacks[index])
            to_call = min(int(st.checking_or_calling_amount or 0), stack)
            kinds: list[ActionKind] = []
            if to_call > 0 and st.can_fold():  # folding when a check is free is never offered
                kinds.append("fold")
            kinds.append("check" if to_call == 0 else "call")
            lo = hi = 0
            top = st.max_completion_betting_or_raising_to_amount  # None when raising is impossible
            if top is not None and st.can_complete_bet_or_raise_to(top):
                hi = top
                lo = min(_req(st.min_completion_betting_or_raising_to_amount), hi)
                facing_bet = max(int(b) for b in st.bets) > 0
                kinds.append("raise" if facing_bet else "bet")
            return LegalOptions(self._seat_of[index], tuple(kinds), to_call, lo, hi)
        if phase == "showdown":
            # A hand cannot muck if it is the only one left contending for some pot: PokerKit
            # would burn that pot. This covers the last hand of a main pot and the last hand of a
            # side pot whose other contenders already mucked.
            me = _req(st.showdown_index)
            unchallenged = any(
                me in pot.player_indices
                and not any(j != me and st.statuses[j] for j in pot.player_indices)
                for pot in st.pots
            )
            # All-in players turn their cards over before the rest of the board is dealt, and
            # PokerKit cannot finish a runout once someone mucks, so mucking needs a full board.
            board_incomplete = len(self.board) < 5
            options: tuple[ActionKind, ...] = (
                ("show",) if unchallenged or board_incomplete else ("show", "muck")
            )
            return LegalOptions(self._seat_of[_req(st.showdown_index)], options)
        if phase == "runout":
            # every remaining player confirms the runout count in turn; V1 always picks one
            return LegalOptions(
                self._seat_of[next(iter(st.runout_count_selector_indices))], ("runout",)
            )
        return None

    # -- acting --------------------------------------------------------------------------------

    def apply(self, action: Action) -> None:
        """Apply an action for the current actor. Raises ``IllegalAction`` if it is not allowed."""
        legal = self.legal()
        if legal is None or action.kind not in legal.kinds:
            raise IllegalAction(f"{action.kind} is not allowed now")
        st = self._st
        seat = legal.seat
        match action.kind:
            case "fold":
                st.fold()
            case "check" | "call":
                st.check_or_call()
            case "bet" | "raise":
                if action.amount < legal.min_raise_to or action.amount > legal.max_raise_to:
                    raise IllegalAction(
                        f"{action.kind} to {action.amount} outside "
                        f"{legal.min_raise_to}-{legal.max_raise_to}"
                    )
                st.complete_bet_or_raise_to(action.amount)
            case "show" | "muck":
                if action.kind == "show":
                    self._shown[seat] = self.hole_cards(seat)
                st.show_or_muck_hole_cards(action.kind == "show")
            case "runout":
                if action.amount != 1:
                    raise IllegalAction("V1 supports a single runout only")
                st.select_runout_count(1)
        self.history.append((seat, action))
        self._pump()

    @property
    def actions(self) -> list[Action]:
        return [a for _, a in self.history]

    # -- result --------------------------------------------------------------------------------

    def result(self) -> HandResult:
        if self.phase != "complete":
            raise RuntimeError("the hand is not finished")
        st = self._st
        payoffs = {self._seat_of[i]: int(p) for i, p in enumerate(st.payoffs)}
        final = {s: self._start_stacks[s] + payoffs[s] for s in self._seat_of}
        return HandResult(
            payoffs=payoffs,
            final_stacks=final,
            board=self.board,
            went_to_showdown=any(a.kind in ("show", "muck") for _, a in self.history),
            shown=dict(self._shown),
        )
