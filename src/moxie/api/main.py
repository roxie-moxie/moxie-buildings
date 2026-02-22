from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from moxie.api.routers.admin import router as admin_router
from moxie.api.routers.auth import router as auth_router
from moxie.api.routers.units import router as units_router
from moxie.api.settings import get_settings


def create_app() -> FastAPI:
    """FastAPI application factory with CORS middleware and all routers mounted."""
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
        """Smoke test endpoint -- returns status ok."""
        return {"status": "ok"}

    # Mount all routers
    application.include_router(auth_router)   # /auth/*
    application.include_router(admin_router)  # /admin/*
    application.include_router(units_router)  # /units

    return application


# Module-level app instance for uvicorn
app = create_app()
