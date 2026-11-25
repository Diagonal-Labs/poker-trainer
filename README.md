# pokersim

A simulator and trainer for low-stakes live poker ($1/$2 card rooms and home games). You practice against
bots built from player-type personas (a calling station, a nit, a maniac and so on) that are realistic and
flawed on purpose, not solver-perfect.

The full design is in the
[technical design doc](https://docs.google.com/document/d/1DB4krwIPZAsGksaVoPLSTvSjJjRjS6PnvEzObejL_Pc/edit).
Decisions made while building are logged in [docs/DECISIONS.md](docs/DECISIONS.md).

## Status

Early build, in slices. See the build order in the design doc.

| Slice | What | State |
|---|---|---|
| 1 | Scaffold, tooling, preflop chart module and starter charts | done |
| 2 | Game engine: PokerKit wrapper, replayable hands | next |
| 3 | Preflop bots and simulation check of VPIP and PFR | |
| 4 | Postflop decision engine | |
| 5 | Request handler and storage | |
| 6 | Frontend table | |
| 7 | Full personas, stats, tells, review | |

## Quick start

Needs Python 3.11 or newer.

```bash
python -m venv .venv && source .venv/bin/activate
make install        # package plus dev tools
make check          # lint, types and tests, the same as CI
make dev            # API on http://localhost:8000 (try /health)
```

Other commands: `make charts` regenerates the starter charts, `make ranking` recomputes the hand ranking,
`make docker` runs the app in Docker. `grep '##' Makefile` lists every command.

## Layout

```
src/pokersim/
  engine/        poker rules, table play and bot decisions (pure, no I/O)
  schemas/       pydantic models shared everywhere
  storage/       session store, persona library, hand history
  api/           FastAPI routes only
  calibration/   simulation runner and stats harness
data/            charts, hand ranking, spot mix, later personas and presets (files, not code)
tools/           scripts that generate data files
tests/           pytest, including architecture rules
frontend/        the web app (later)
```
