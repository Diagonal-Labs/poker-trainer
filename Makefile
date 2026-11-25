.PHONY: install dev test lint format typecheck check charts ranking simulate docker

install:  ## install the package and dev tools in editable mode
	pip install -e ".[dev]"

dev:  ## run the API with auto-reload on http://localhost:8000
	uvicorn pokersim.request_handler.app:app --reload --port 8000

test:  ## run the tests
	pytest

lint:  ## style and bug checks
	ruff check .
	ruff format --check .

format:  ## apply the formatter and safe lint fixes
	ruff check --fix .
	ruff format .

typecheck:  ## static types (strict for src/pokersim)
	pyright

check: lint typecheck test  ## everything CI runs

charts:  ## regenerate the starter charts (data/charts) from data/hand_ranking.json
	python tools/generate_charts.py

ranking:  ## recompute data/hand_ranking.json (about 30 seconds)
	python tools/rank_hands.py data/hand_ranking.json 100000

simulate:  ## 100k-hand preflop simulation: VPIP and PFR against each persona's targets (about 4 minutes)
	python tools/simulate_preflop.py --hands 100000 --by-position

docker:  ## build and run the app in Docker
	docker compose up --build
