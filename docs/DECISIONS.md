# Decisions log

Short entries, newest first. The design doc holds the full reasoning for the early ones.

## Slice 1

- **Package and layout.** One Python package, `pokersim`, in the `src` layout. Engine, schemas, storage, api and
  calibration are subpackages with inward-pointing imports, enforced by `tests/test_architecture.py`.
- **Tooling.** ruff for lint and format, pyright (strict on `src/pokersim`), pytest with hypothesis available.
  CI runs all of them on Python 3.11 and 3.13.
- **Charts are generated, not hand-written.** `tools/generate_charts.py` builds the six starter charts from
  `data/hand_ranking.json` and per-persona profiles, fitted to VPIP and PFR targets. A test fails if the
  committed charts differ from the generator's output. The implied stats depend on an assumed spot mix
  (`data/spot_mix.json`) that slice 3 replaces with simulation measurements.
- **Chart module.** `engine/chart.py` holds the range-string parser, validator and implied-stat report as pure
  functions. Reading files is done by callers, not the engine.
- **Chart rename.** `l2_tight_passive` became `l2_nit`, because the nit's targets mean it raises almost every
  hand it plays.

## Earlier (see the design doc)

- PokerKit 0.7.x pinned, wrapped behind `engine.rules`. eval7 for all equity.
- Stateless server: table state is rebuilt each request by replaying the current hand from its seed and action
  list. No table-state cache in V1.
- SQLite for sessions and hand history, JSON files for personas and charts.

## Open

- License. Undecided, since the project may be commercialized. Add one before the repo goes public.
