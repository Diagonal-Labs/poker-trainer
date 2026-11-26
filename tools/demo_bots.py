"""Narrated hands played by the six starter personas, with each preflop and postflop decision.

python tools/demo_bots.py [hands] [seed]
"""

from __future__ import annotations

import sys
from pathlib import Path

from pokersim.calibration.simulate import build_bots
from pokersim.game_engine.game import play_hand
from pokersim.game_engine.rules import HandSetup, SeatEntry
from pokersim.storage.persona_library import PersonaLibrary

DATA = Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    hands = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    library = PersonaLibrary(DATA)
    bots = build_bots(library, library.persona_ids(), None)
    seats = dict(enumerate(bots))
    for n in range(hands):
        setup = HandSetup(tuple(SeatEntry(i, 200) for i in range(len(bots))), button=n % len(bots))
        for bot in bots:
            bot.records.clear()
            bot.postflop_records.clear()
        _, result = play_hand(setup, seats, seed, n)
        print(f"\n=== hand {n}, button seat {setup.button} ===")
        rows = [(i, r) for i, b in enumerate(bots) for r in b.records]
        for i, r in sorted(rows, key=lambda row: row[0]):
            bot = bots[i]
            if not r.chart_used:
                why = "forgot the chart -> " + r.action.kind
            else:
                mix = " ".join(f"{a} {p:.0%}" for a, p in r.probabilities.items() if p > 0)
                why = f"chart rule {r.rule_index}: {mix} -> {r.chosen}"
                if r.action.kind in ("raise", "bet"):
                    why += f" to {r.action.amount}"
            s = r.spot
            print(f"  {bot.persona.name:<24} {s.position_group:<6} {r.hand:<4} {s.spot:<8} {why}")
        for bot in bots:
            for q in bot.postflop_records:
                seen = q.perception
                top = sorted(q.probabilities.items(), key=lambda kv: -kv[1])[:3]
                odds = " ".join(f"{a} {p:.0%}" for a, p in top)
                flags = ",".join(seen.flags) or "-"
                print(
                    f"  {bot.persona.name:<24} {q.street:<5} {' '.join(q.state.hole)} on "
                    f"{' '.join(q.state.board)}: sees {seen.category} eq {seen.equity:.2f} "
                    f"[{flags}] pot {q.state.pot} to call {q.state.to_call}: {odds} -> {q.chosen}"
                )
        print(f"  board {' '.join(result.board) or '-'}  net {result.payoffs}")


if __name__ == "__main__":
    main()
