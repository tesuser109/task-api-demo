"""The only place this app talks to the Claude API.

CLAUDE_MODE=live (default) calls the API, record also saves the responses,
replay reads saved responses and makes no network calls.
"""

import json
import os
from pathlib import Path
from typing import Any, Protocol

import anthropic
from anthropic.types.beta import BetaMessage

MODEL = "claude-opus-5-5"


class ClaudeUnavailableError(Exception):
    pass


class ClaudeClient(Protocol):
    def create(
        self, *, system: str, messages: list[dict], tools: list[dict], output_schema: dict[str, Any]
    ) -> BetaMessage: ...


class LiveClient:
    def create(self, *, system, messages, tools, output_schema) -> BetaMessage:
        try:
            client = anthropic.Anthropic(timeout=45.0, max_retries=1)
            return client.beta.messages.create(
                model=MODEL,
                max_tokens=16000,
                system=system,
                messages=messages,
                tools=tools,
                output_config={
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": output_schema},
                },
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as exc:
            raise ClaudeUnavailableError("Claude rejected the credentials") from exc
        except anthropic.RateLimitError as exc:
            raise ClaudeUnavailableError("Claude rate limit reached") from exc
        except anthropic.APIStatusError as exc:
            raise ClaudeUnavailableError(f"Claude returned HTTP {exc.status_code}") from exc
        except anthropic.APIConnectionError as exc:
            raise ClaudeUnavailableError("Claude could not be reached") from exc
        except (anthropic.AnthropicError, TypeError) as exc:
            # The SDK reports missing credentials this way.
            raise ClaudeUnavailableError("Claude client is not configured") from exc


class RecordClient:
    def __init__(self, path: Path) -> None:
        self._live, self._path, self._saved = LiveClient(), path, []

    def create(self, **request) -> BetaMessage:
        response = self._live.create(**request)
        self._saved.append(response.model_dump(mode="json"))
        self._path.write_text(json.dumps(self._saved, indent=2) + "\n", encoding="utf-8")
        return response


class ReplayClient:
    def __init__(self, path: Path) -> None:
        self._responses = iter(json.loads(path.read_text(encoding="utf-8")))

    def create(self, **request) -> BetaMessage:
        try:
            return BetaMessage.model_validate(next(self._responses))
        except StopIteration as exc:
            raise ClaudeUnavailableError("The recording has no more responses") from exc


def get_claude_client() -> ClaudeClient:
    mode = os.getenv("CLAUDE_MODE", "live")
    path = Path(os.getenv("CLAUDE_RECORDING", "recordings/summary.json"))
    if mode == "replay":
        return ReplayClient(path)
    if mode == "record":
        return RecordClient(path)
    return LiveClient()
