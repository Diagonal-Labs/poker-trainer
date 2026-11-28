"""Simulate preflop play and compare VPIP and PFR with each persona's targets.

    python tools/simulate_preflop.py --hands 100000
    python tools/simulate_preflop.py --hands 20000 --adherence preset
    python tools/simulate_preflop.py --hands 20000 --table solo:nit
    python tools/simulate_preflop.py --hands 100000 --spot-mix-out measured_spot_mix.json

Adherence "chart" (default) makes every bot follow its chart on every decision, which is what the
chart-fitted targets assume. "preset" uses each persona's own chartAdherence, with the stand-in
for the missing perception pipeline (check or fold) on the other decisions.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from pokersim.calibration.simulate import pct, postflop_report, report, simulate
from pokersim.storage.persona_library import PersonaLibrary

DATA = Path(__file__).resolve().parent.parent / "data"
POSITIONS = ("early", "middle", "cutoff", "button", "sb", "bb")
SPOTS = ("open", "vs_limp", "vs_raise", "vs_3bet", "vs_4bet")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--hands", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--adherence", choices=["chart", "preset"], default="chart")
    ap.add_argument("--table", default="mixed", help="mixed (all starter personas) or solo:<id>")
    ap.add_argument("--seats", type=int, default=6, help="players at the table, 2 to 10")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--by-position", action="store_true")
    ap.add_argument("--spot-mix-out", type=Path, help="write the measured spot mix as JSON")
    args = ap.parse_args()

    library = PersonaLibrary(DATA)
    if args.table.startswith("solo:"):
        ids = [args.table.split(":", 1)[1]] * args.seats
    else:
        everyone = library.persona_ids()
        ids = [everyone[i % len(everyone)] for i in range(args.seats)]
    start = time.time()
    result = simulate(
        DATA, ids, args.hands, args.seed, 1.0 if args.adherence == "chart" else None, args.workers
    )
    secs = time.time() - start
    print(
        f"{result.hands} hands, {len(ids)} seats, {secs:.0f}s ({result.hands / secs:.0f} hands/s)\n"
    )
    print(report(result, library))
    print("\nPostflop (the full decision pipeline)")
    print(postflop_report(result, library))
    if args.by_position:
        print("\nVPIP / PFR by position group")
        for persona in result.by_persona:
            cells = []
            for pos in POSITIONS:
                c = result.by_position.get((persona, pos))
                cells.append(
                    f"{pos} {pct(c.vpip, c.hands):.0f}/{pct(c.pfr, c.hands):.0f}" if c else ""
                )
            print(f"  {persona:<16}" + "  ".join(cells))
    print("\nMeasured spot mix of each bot's first decision (percent)")
    mix: dict[str, dict[str, float]] = {}
    for pos in POSITIONS:
        total = sum(result.first_spot.get((pos, s), 0) for s in SPOTS)
        mix[pos] = {
            s: round(result.first_spot.get((pos, s), 0) / total, 3) if total else 0 for s in SPOTS
        }
        print(f"  {pos:<8}" + "".join(f"{s} {100 * mix[pos][s]:5.1f}  " for s in SPOTS))
    if args.spot_mix_out:
        args.spot_mix_out.write_text(json.dumps({"mix": mix}, indent=1) + "\n")


if __name__ == "__main__":
    main()
