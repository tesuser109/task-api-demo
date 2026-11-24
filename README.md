# Task API

A small synthetic task API for training. All data is invented.

    uv sync
    uv run python -m scripts.seed
    uv run uvicorn app.main:app --reload
    uv run pytest

API docs: http://127.0.0.1:8000/docs
