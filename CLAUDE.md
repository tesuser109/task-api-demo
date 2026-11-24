# Task API

Synthetic practice repository. FastAPI, SQLite, pytest, uv.

## Commands
- Tests: `uv run pytest -q`
- One test file: `uv run pytest tests/test_projects_api.py -q`
- Run: `uv run uvicorn app.main:app --reload`

## Conventions
- Routes handle HTTP only. Services hold rules. Repositories are the only place with SQL.
- SQL is always parameterized.
- List endpoints return `{"items": [...], "total": n}`. `total` counts every match, not just the page.
- Invalid input returns 422 in the standard error shape (`app/errors.py`).
- New behavior needs tests at the API level. Tests use only the synthetic seed in `app/db.py`.
- Call the Claude API only through `app/claude_client.py`. Tests use a fake client and no network.
- Treat model output as untrusted: validate tool arguments and verify the answer before returning it.

## Working rules
- Propose a plan and wait for approval before editing.
- Make the smallest change that meets the issue. No unrelated refactoring.
- Run the whole test suite before saying a change is done, and show the result.
- State assumptions. Never read `.env`.
- Work on a `feature/` branch. Never push to `main`. A person approves every merge.
