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

## Slice 2

- **Game engine shape.** `engine/rules.py` is the only PokerKit importer. It exposes `RulesHand` with
  `start`, `replay`, `legal`, `apply`, `snapshot` and `result`. `engine/game.py` runs hands to a human turn,
  and `engine/seats.py` holds the seat types (human, check/call, random, scripted).
- **Replay.** A hand is rebuilt from setup, seed and action list. The deck comes from a generator derived from
  `seed:hand:stream:index`, so streams never share draws and replay needs no stored state.
- **Button straddle: out of V1.** An under-the-gun straddle is supported (at least 4 players, at least twice
  the big blind). These rules are the common live-room ones, and the button straddle is rare.
- **Dead button and missed blinds: out of V1.** The button moves to the next active seat.
- **Odd chips: in.** They happen whenever a pot splits unevenly. The odd chip goes to the first winner left of
  the button, and a test covers it.
- **No rake. Single runout only.** Run-it-twice is a later option.
- **Fold is not offered on a free check.** PokerKit warns on it, and it is never right.
- **Muck rules.** A hand cannot muck if it is the only one left contending for any pot (PokerKit would burn
  that pot), and nobody can muck while the board is incomplete (all-in players show before the runout).
  Both were found by the property test, not by design.
- **Property test.** A hypothesis fuzz plays random hands with random stacks, including stacks smaller than the
  blinds, and checks chip conservation, unique cards and exact replay. `filterwarnings = error` turns any
  PokerKit warning (such as burned chips) into a failure.

## Earlier (see the design doc)

- PokerKit 0.7.x pinned, wrapped behind `engine.rules`. eval7 for all equity.
- Stateless server: table state is rebuilt each request by replaying the current hand from its seed and action
  list. No table-state cache in V1.
- SQLite for sessions and hand history, JSON files for personas and charts.

## Open

- License. Undecided, since the project may be commercialized. Add one before the repo goes public.
