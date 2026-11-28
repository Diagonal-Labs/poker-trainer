"""FastAPI application factory: the JSON API and the static web table."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from pokersim import __version__
from pokersim.request_handler import hand_service
from pokersim.request_handler.models import HandRequest, HandResponse


def _project_root() -> Path:
    """The folder holding data/ and frontend/: POKERSIM_ROOT, else the working directory, else the
    source checkout. The Docker image runs from /app with both folders copied in."""
    configured = os.environ.get("POKERSIM_ROOT")
    if configured:
        return Path(configured)
    if (Path.cwd() / "data").is_dir():
        return Path.cwd()
    return Path(__file__).resolve().parents[3]


ROOT = _project_root()
DATA = ROOT / "data"
FRONTEND = ROOT / "frontend"


def create_app(data_dir: Path = DATA, frontend_dir: Path = FRONTEND) -> FastAPI:
    app = FastAPI(title="pokersim", version=__version__)

    @app.get("/health")
    def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok", "version": __version__}

    @app.get("/api/personas")
    def personas() -> list[dict[str, object]]:  # pyright: ignore[reportUnusedFunction]
        return hand_service.personas(data_dir)

    @app.post("/api/hand")
    def hand(request: HandRequest) -> HandResponse:  # pyright: ignore[reportUnusedFunction]
        """Replay the hand from the request, run bots to the human's turn, return the table."""
        try:
            return hand_service.play(request, data_dir)
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/")
    def index() -> FileResponse:  # pyright: ignore[reportUnusedFunction]
        page = frontend_dir / "index.html"
        if not page.exists():
            raise HTTPException(status_code=404, detail="frontend/index.html is missing")
        return FileResponse(page)

    return app


app = create_app()
