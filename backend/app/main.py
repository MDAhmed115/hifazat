# backend/app/main.py
"""Hifazat FastAPI Application Entrypoint combining P4, P5, and P6 modules."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine
from .routers import (
    audit_routes,
    auth_routes,
    cases,
    consent,
    decision_routes,
    mock_services,
)


def create_app() -> FastAPI:
    # Auto-create tables in SQLite development environment
    if settings.DATABASE_URL.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)

    app = FastAPI(
        title=f"{settings.APP_NAME} API ({settings.APP_LABEL})",
        version=settings.APP_VERSION,
        description="Unified Multi-Role Anti-Scam SaaS Platform protecting Pakistani citizens from fraudulent SMS, fake relief payments, and financial scams.",
    )

    # CORS configuration for Vite frontend and local testing
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount all routers
    app.include_router(auth_routes.router)
    app.include_router(cases.router)
    app.include_router(consent.router)
    app.include_router(decision_routes.router)
    app.include_router(audit_routes.router)
    app.include_router(mock_services.router)

    @app.get("/", tags=["meta"])
    def root():
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "docs": "/docs",
            "redoc": "/redoc",
            "message": "Hifazat Unified Backend API is active.",
        }

    @app.get("/health", tags=["meta"])
    @app.get("/api/health", tags=["meta"])
    def health():
        return {
            "status": "ok",
            "ok": True,
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        }

    return app


app = create_app()
