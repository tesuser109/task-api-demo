import logging
import os

from fastapi import FastAPI

from app.db import connect
from app.errors import install_error_handlers
from app.routes import projects, tasks


def create_app(db_path: str | None = None) -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    app = FastAPI(title="Task API")
    app.state.conn = connect(db_path or os.getenv("TASK_DB", "tasks.db"))
    install_error_handlers(app)
    app.include_router(tasks.router)
    app.include_router(projects.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
