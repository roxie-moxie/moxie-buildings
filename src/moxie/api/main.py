from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from moxie.api.settings import get_settings


def create_app() -> FastAPI:
    """FastAPI application factory with CORS middleware."""
    settings = get_settings()

    application = FastAPI(
        title="Moxie Buildings API",
        description="Authenticated API for Chicago rental market data",
        version="1.0.0",
    )

    # Parse comma-separated CORS origins from settings
    cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health", tags=["meta"])
    def health_check():
        """Smoke test endpoint — returns status ok."""
        return {"status": "ok"}

    return application


# Module-level app instance for uvicorn
app = create_app()
