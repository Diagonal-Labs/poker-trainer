# Working in this repo

Design doc (source of truth for behavior):
https://docs.google.com/document/d/1DB4krwIPZAsGksaVoPLSTvSjJjRjS6PnvEzObejL_Pc/edit
When code and doc disagree, flag it and update one of them. Log real decisions in docs/DECISIONS.md.

## Commands

- `make check`: ruff, pyright (strict on src/pokersim) and pytest. Run before every commit. CI runs the same.
- `make charts`: regenerate data/charts. Never hand-edit generated charts. A test fails if they drift.
- `make dev`: run the API locally.

## Rules (from the design doc)

- Both engines are functional cores: no file, network or database access. Only the request handler touches storage.
- Dependencies point inward: request_handler and calibration -> decision_engine, game_engine, schemas, storage.
  storage -> schemas. decision_engine -> game_engine, schemas, eval7. game_engine -> schemas, PokerKit.
  Only `game_engine/rules.py` imports PokerKit; game_engine never imports decision_engine. `tests/test_architecture.py`
  enforces this.
- Pass the random generator in explicitly. No global `random.*` calls in either engine, or seeded replay breaks.
- Pydantic at the edges (API, files, stores). Plain dataclasses inside the decision loop.
- Bot behavior comes from persona and chart files in `data/`, never from code branches on persona names.
- Use eval7 for all equity. PokerKit's evaluator is for showdown only.

## Process

Build in slices. Each slice: tests first or alongside, `make check` green, a short write-up with a demo
(printed hands, simulation stats, a screenshot), then wait for sign-off before the next slice.
Work on a branch and open a PR. Do not push to main directly after the initial commit.
