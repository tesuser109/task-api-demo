from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.claude_client import ClaudeUnavailableError


class NotFoundError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class SummaryRejectedError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status_code)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return error_response(404, "not_found", exc.message)

    @app.exception_handler(SummaryRejectedError)
    async def summary_rejected(_: Request, exc: SummaryRejectedError) -> JSONResponse:
        return error_response(502, "summary_rejected", exc.message)

    @app.exception_handler(ClaudeUnavailableError)
    async def claude_unavailable(_: Request, exc: ClaudeUnavailableError) -> JSONResponse:
        return error_response(503, "claude_unavailable", str(exc))

    @app.exception_handler(RequestValidationError)
    async def invalid_input(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0]
        field = ".".join(str(part) for part in first["loc"][1:])
        return error_response(422, "invalid_input", f"{field}: {first['msg']}")
