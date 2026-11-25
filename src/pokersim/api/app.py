"""FastAPI application factory."""

from fastapi import FastAPI

from pokersim import __version__


def create_app() -> FastAPI:
    """Build the app. Routes for sessions and hands are added in a later slice."""
    app = FastAPI(title="pokersim", version=__version__)

    @app.get("/health")
    def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
