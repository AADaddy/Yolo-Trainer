from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.router import api_router
from backend.config import API_PREFIX, APP_TITLE, APP_VERSION
from backend.database import init_db
from backend.services.trainer import resume_training_queue


def create_app() -> FastAPI:
    app = FastAPI(title=APP_TITLE, version=APP_VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()
        resume_training_queue()

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(api_router, prefix=API_PREFIX)
    return app


app = create_app()
