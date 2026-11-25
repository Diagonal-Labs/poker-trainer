"""Narrated demo of the game engine: positions, a straddle, side pots and replay parity.

Run with ``python tools/demo_hand.py``.
"""

from __future__ import annotations

from pokersim.game_engine.game import play_hand, replay_hand, start_hand
from pokersim.game_engine.rules import Action, HandSetup, RulesHand, SeatEntry
from pokersim.game_engine.seats import RandomSeat


class Narrator:
    """Wraps a seat and prints what it does, with the street and position."""

    def __init__(self, inner: RandomSeat, log: list[str]) -> None:
        self.inner, self.log = inner, log

    def act(self, ctx):  # type: ignore[no-untyped-def]
        action = self.inner.act(ctx)
        pos = next(s.position for s in ctx.snapshot.seats if s.seat == ctx.seat)
        cards = " ".join(ctx.hole_cards)
        amount = f" to {action.amount}" if action and action.kind in ("bet", "raise") else ""
        self.log.append(
            f"  {ctx.snapshot.street:<8} seat {ctx.seat} ({pos:<5}) [{cards}] "
            f"{action.kind if action else '?'}{amount}   pot {ctx.snapshot.pot}"
        )
        return action


def show(title: str, setup: HandSetup, seed: int) -> tuple[RulesHand, list[str]]:
    print(f"\n=== {title} ===")
    hand0 = start_hand(setup, seed, 1)
    print("  positions:", ", ".join(f"{s.seat}:{s.position}" for s in hand0.snapshot().seats))
    log: list[str] = []
    seats = {e.seat: Narrator(RandomSeat(), log) for e in setup.seats}
    hand, result = play_hand(setup, seats, seed, 1)
    print("\n".join(log))
    print(f"  board: {' '.join(result.board) or '(none)'}")
    print(f"  net: {result.payoffs}   final stacks: {result.final_stacks}")
    assert sum(result.payoffs.values()) == 0
    return hand, log


def main() -> None:
    six = tuple(SeatEntry(i, 200) for i in range(6))
    show("Six-handed, $1/$2, button on seat 5", HandSetup(six, button=5), seed=3)

    show(
        "Six-handed with a $6 straddle under the gun",
        HandSetup(six, button=5, straddle=6),
        seed=8,
    )

    uneven = tuple(SeatEntry(i, s) for i, s in enumerate([30, 120, 60, 200]))
    hand, _ = show("Four-handed, uneven stacks, side pots", HandSetup(uneven, button=3), seed=21)

    heads_up = (SeatEntry(0, 100), SeatEntry(1, 100))
    show("Heads-up (button posts the small blind)", HandSetup(heads_up, button=1), seed=5)

    setup = HandSetup(uneven, button=3)
    actions: list[Action] = hand.actions
    rebuilt = replay_hand(setup, 21, 1, actions)
    same = rebuilt.result() == hand.result()
    print(
        f"\nReplay parity: rebuilt the side-pot hand from seed + {len(actions)} actions -> {same}"
    )
    assert same


if __name__ == "__main__":
    main()
