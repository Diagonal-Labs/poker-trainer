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
- **Chart module.** `decision_engine/preflop.py` (was `engine/chart.py`) holds the range-string parser, validator and implied-stat report as pure
  functions. Reading files is done by callers, not the engine.
- **Chart rename.** `l2_tight_passive` became `l2_nit`, because the nit's targets mean it raises almost every
  hand it plays.

## Slice 2

- **Game engine shape.** `game_engine/rules.py` is the only PokerKit importer. It exposes `RulesHand` with
  `start`, `replay`, `legal`, `apply`, `snapshot` and `result`. `game_engine/game.py` runs hands to a human turn,
  and `game_engine/seats.py` holds the seat types (human, check/call, random, scripted).
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

## Folder names follow the design doc

- **Two engine packages.** `engine/` became `game_engine/` (rules, game, seats, positions) and
  `decision_engine/` (preflop so far). The doc's `engine.rules` is now `game_engine.rules`, and so on.
- **Dependency direction.** `decision_engine` may import `game_engine` for the table and action types;
  `game_engine` never imports `decision_engine`. The hand loop only sees the `Seat` interface, so it is
  testable with scripted seats and needs no bots. A test enforces both rules.
- **BotSeat moves.** The doc put BotSeat in `engine.seats`. It will live in `decision_engine/bot_seat.py`,
  because it calls the Decision engine and the dependency runs that way. HumanSeat and the test seats stay in
  `game_engine/seats.py`.
- **`api` is `request_handler`.** The doc calls it the Request handler. The doc's "API design" section still
  describes its HTTP surface.
- **`chart.py` is `preflop.py`.** The doc's pipeline step is `preflop`, and charts are its data.
- **Slice 1 entries below** use the old names, kept as written at the time.

## Slice 3

- **Persona schema covers the preflop part only.** `schemas/persona.py` has the doc's field names
  (`preflop.chart`, `chartAdherence`, `mixFidelity`, `biases.looseness`, `targetStats`). Unknown fields are
  rejected, so the other doc fields (perception, habits, selector, other biases) are added with the slices that
  use them. `preflop.chart` is required for now; the doc's "a persona with only a skillLevel is valid" needs
  level default charts, which come with presets.
- **Starter personas.** Six files in `data/personas/`, one per starter chart, with the doc's target ranges.
  `looseness` is 0 on all of them because the charts are already fitted to each persona's targets. The doc lists
  looseness values for the nit, Dave, the maniac and the LAG. Those would be applied on top of the chart and
  move the stats away from the targets, so the doc and the files differ here. To decide with the doc.
- **Looseness** shifts every rule by `round(looseness * classesPerUnit)` hand classes down (or up) the hand
  ranking. `data/bias_scales.json` starts at 20 classes per unit, a guess for calibration.
- **Chart adherence stand-in.** The doc sends a bot that "forgets" its chart to the full perception pipeline,
  which does not exist yet. Until slice 4, such a decision is check-if-free, otherwise fold. The simulation
  reports the chart-only numbers (adherence 1) and, separately, the persona presets.
- **Postflop placeholder.** Bots check when they can and fold to any bet, and always show at showdown.
- **Spot detection** reads the action log: raises so far (0 open or vs_limp, 1 vs_raise, 2 vs_3bet, 3+ vs_4bet),
  and calls before the first raise are limpers. `DecisionContext` now carries that log.
- **Preflop sizes** (`decision_engine/sizing.py`): opens of 3, 4 or 5 big blinds, isolation raises add 2.5 big
  blinds per limper, 3-bets are 3x in position and 4x out, 4-bets about 2.3x, 5-bets all-in, and any raise that
  commits over half the stack is a shove. The doc's level-based sizing styles come later.
- **Only the `pos` chart condition is read.** `raiserPos`, `callers`/`limpers` and `depth` are in the format but
  no starter chart uses them yet.
- **Simulation.** `calibration/simulate.py` plays bot-only hands with stacks reset to 100 big blinds and the
  button moving every hand. The result does not depend on the number of worker processes. VPIP counts a call of a
  bet or a raise, not a big-blind check. Results are in `docs/preflop_simulation.md`.
- **Performance fix.** `RulesHand.phase` is cached: working it out made PokerKit rank hands several times per
  decision, and caching more than doubled simulation speed.

## Slice 4

Decided on my own, as asked. Review these.

- **Pipeline implemented:** decision state, perception, baseline EV, biases, selector (two steps), in
  `decision_engine/` with one module per stage. **Habits and tells are deferred** (the doc's later stages).
- **Perception dials:** only `handStrength`, `boardTexture`, `money` and `multiway` exist. A dial of 0 reads like 1.
  Levels 1 and 2 use category tables, misreads and flags; Level 3 uses real equity against range buckets.
- **Equity:** eval7 only, in `decision_engine/eval7_adapter.py`, the single importer (a test enforces it). The
  sampler is seeded by the inputs, so the cache is pure and the engine stays deterministic.
- **Opponent ranges** are guessed from the action log: raises narrow to 30/12/6/4 percent of hands, calls to
  35/20/12, a postflop bet keeps 80 percent of the range (floor 30), a call 90 percent.
- **Baseline EV** follows the doc's formulas. Extra stand-ins in `data/presets.json`: `callBonus` (0.2, implied
  odds), `raiseFoldFactor`, `maxFoldPerOpponent`, `raiseCalledPenalty`, which stop raises looking free.
- **Size menu:** bets 33/66/100/150 percent of the pot, raises min/3x/3.5x, all-in only when the stack is at most
  2.5 pots (`shoveMaxPotMultiple`); sizes near the stack collapse into the all-in.
- **Biases:** looseness, aggression, stickiness, riskAversion and sizing style are implemented. `looseness` stays
  0 on the starter personas because their charts already encode it. Bias scales are guesses.
- **Chart adherence fallback** is still check-if-free, otherwise fold. Routing it into this pipeline is the
  next change; it is why fit-or-fold VPIP is below target.
- **Postflop targets** (af, wtsd, cbet, foldToBet) in the persona files are my estimates, not data.
- **Game engine:** `RulesHand` now records the street of every action and each seat's chips invested, and
  `DecisionContext` carries `history_streets`.
- **Simulation:** `docs/postflop_simulation.md`. Several stats are still outside the estimated targets.

## Slice 5

- **Build order changed.** The playable table moved ahead of storage so the product can be tested early (UAT in
  slices, not only code). Storage and hand history are now slice 7, tells and polish slice 8.
- **One endpoint, stateless.** `POST /api/hand` takes the seed, hand number, button, seats and every action so
  far; the server replays the hand, runs bots until the human must act, and returns the table, the legal
  options and the full action list to send back. Bots do not decide again for replayed actions.
- **Hidden information.** The response carries the human's cards, and other cards only once shown at showdown.
- **Bot reasons** (`reason` on events) come from the decision records and exist only for actions made during
  that request. The page keeps them, so a page reload after the action keeps them. They are for UAT.
- **Session lives in the browser** (seed, stacks, button, personas, hand number, in localStorage). `next` in the
  response gives the next hand's button and stacks; a busted seat is topped up to 200.
- **One human seat (seat 0), six handed**, 200 chip stacks. No straddle, no rake, and bots never rebuy to a
  target stack, so stacks drift apart over a session.
- **Bots play at their own chart adherence**, so the chart-adherence stand-in (check or fold) is visible in play
  ("forgot the chart"). It is the first thing to fix after UAT.
- **No animation or delays.** Bots act instantly; everything shows when it is your turn.
- **Static page** `frontend/index.html` (vanilla JS), served by the API at `/`. No build step, so it can be
  replaced by the real frontend later.
- **Bot factory.** `decision_engine/bot_factory.py` builds a bot from plain data so the request handler does not
  import calibration; calibration uses it too.
- **Project root** for `data/` and `frontend/` comes from `POKERSIM_ROOT`, else the working directory, else the
  source checkout (the Docker image runs from /app).

## Earlier (see the design doc)

- PokerKit 0.7.x pinned, wrapped behind `game_engine.rules`. eval7 for all equity.
- Stateless server: table state is rebuilt each request by replaying the current hand from its seed and action
  list. No table-state cache in V1.
- SQLite for sessions and hand history, JSON files for personas and charts.

## Open

- License. Undecided, since the project may be commercialized. Add one before the repo goes public.
