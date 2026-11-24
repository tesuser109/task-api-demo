import json
from pathlib import Path

import anthropic
import pytest
from anthropic.types.beta import BetaMessage

from app.claude_client import ClaudeUnavailableError, get_claude_client
from app.models import TaskStatus
from app.services.task_service import TaskService

DOCS = Path(__file__).resolve().parents[1] / "docs" / "summary"
OPEN_ARGS = {"status": "open", "limit": 100}
ANSWER = {
    "headline": "Four open tasks, two of them high priority.",
    "total_open": 4,
    "top_tasks": [
        {"id": 1, "title": "Fix login redirect loop", "reason": "High priority"},
        {"id": 3, "title": "Crash when opening an empty inbox", "reason": "High priority"},
    ],
}


def message(stop_reason, *content):
    return BetaMessage.model_validate(
        {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "fake",
            "content": list(content),
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }
    )


def tool_block(args, name="list_tasks", block_id="toolu_1"):
    return {"type": "tool_use", "id": block_id, "name": name, "input": args}


def tool_call(args=OPEN_ARGS, name="list_tasks"):
    return message("tool_use", tool_block(args, name))


def answer(**changes):
    return raw_answer(json.dumps(ANSWER | changes))


def raw_answer(text, stop_reason="end_turn"):
    return message(stop_reason, {"type": "text", "text": text})


class FakeClient:
    def __init__(self):
        self.responses, self.requests = [], []

    def create(self, **request):
        self.requests.append(request | {"messages": list(request["messages"])})
        response = self.responses[len(self.requests) - 1]
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Tests must not create a real Claude client")

    monkeypatch.setattr(anthropic, "Anthropic", fail)


@pytest.fixture
def fake(app):
    fake = FakeClient()
    app.dependency_overrides[get_claude_client] = lambda: fake
    return fake


@pytest.fixture
def list_calls(monkeypatch):
    calls, original = [], TaskService.list_tasks

    def spy(self, **kwargs):
        calls.append(kwargs)
        return original(self, **kwargs)

    monkeypatch.setattr(TaskService, "list_tasks", spy)
    return calls


def summarize(client, fake, *responses):
    fake.responses = list(responses)
    return client.post("/tasks/summary")


def tool_results(fake, request_index=1):
    return fake.requests[request_index]["messages"][-1]["content"]


def assert_rejected(response):
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "summary_rejected"


# Criterion 1


def test_summary_returns_verified_open_tasks(client, fake):
    response = summarize(client, fake, tool_call(), answer())
    assert response.status_code == 200
    assert response.json() == ANSWER


def test_summary_with_no_open_tasks(app, client, fake):
    app.state.conn.execute("UPDATE tasks SET status = 'closed'")
    app.state.conn.commit()
    response = summarize(client, fake, tool_call(), answer(total_open=0, top_tasks=[]))
    assert response.status_code == 200
    assert response.json()["total_open"] == 0
    assert response.json()["top_tasks"] == []


# Criterion 2


def test_claude_gets_only_list_tasks(client, fake):
    summarize(client, fake, tool_call(), answer())
    schema = json.loads((DOCS / "tool-schema.json").read_text(encoding="utf-8"))
    assert [request["tools"] for request in fake.requests] == [[schema], [schema]]


def test_tool_runs_through_task_service(client, fake, list_calls):
    summarize(client, fake, tool_call(), answer())
    assert list_calls == [{"limit": 100, "offset": 0, "status": TaskStatus.OPEN}]
    [result] = tool_results(fake)
    assert result["tool_use_id"] == "toolu_1"
    assert "is_error" not in result
    page = json.loads(result["content"])
    assert [task["id"] for task in page["items"]] == [1, 3, 5, 8]
    assert page["total"] == 4


def test_assistant_turn_is_sent_back_unchanged(client, fake):
    call = tool_call()
    summarize(client, fake, call, answer())
    assert fake.requests[1]["messages"][1] == {"role": "assistant", "content": call.content}


def test_parallel_tool_calls_return_one_result_each(client, fake, list_calls):
    call = message(
        "tool_use",
        tool_block(OPEN_ARGS, block_id="toolu_1"),
        tool_block({"status": "closed", "limit": 5}, block_id="toolu_2"),
    )
    assert summarize(client, fake, call, answer()).status_code == 200
    first, second = tool_results(fake)
    assert (first["tool_use_id"], second["tool_use_id"]) == ("toolu_1", "toolu_2")
    assert "is_error" not in first
    assert second["is_error"] is True
    assert len(list_calls) == 1


@pytest.mark.parametrize("limit", [1, 100])
def test_limit_bounds_are_accepted(client, fake, list_calls, limit):
    call = tool_call({"status": "open", "limit": limit})
    response = summarize(client, fake, call, answer(top_tasks=[]))
    assert response.status_code == 200
    assert list_calls[0]["limit"] == limit


@pytest.mark.parametrize(
    ("args", "name"),
    [
        ({"status": "closed", "limit": 10}, "list_tasks"),
        ({"status": "in_progress", "limit": 10}, "list_tasks"),
        ({"status": "open", "limit": 0}, "list_tasks"),
        ({"status": "open", "limit": 101}, "list_tasks"),
        ({"status": "open", "limit": "10"}, "list_tasks"),
        ({"status": "open", "limit": True}, "list_tasks"),
        ({"status": "open"}, "list_tasks"),
        ({"limit": 10}, "list_tasks"),
        ({"status": "open", "limit": 10, "offset": 5}, "list_tasks"),
        (OPEN_ARGS, "delete_tasks"),
    ],
)
def test_invalid_tool_call_runs_nothing(client, fake, list_calls, args, name):
    assert_rejected(summarize(client, fake, tool_call(args, name), answer()))
    [result] = tool_results(fake)
    assert result["tool_use_id"] == "toolu_1"
    assert result["is_error"] is True
    assert list_calls == []


def test_claude_can_correct_invalid_arguments(client, fake, list_calls):
    bad_call = tool_call({"status": "closed", "limit": 10})
    response = summarize(client, fake, bad_call, tool_call(), answer())
    assert response.status_code == 200
    assert len(list_calls) == 1


# Criterion 3


def test_every_request_sends_output_schema(client, fake):
    summarize(client, fake, tool_call(), answer())
    schema = json.loads((DOCS / "output-schema.json").read_text(encoding="utf-8"))
    assert [request["output_schema"] for request in fake.requests] == [schema, schema]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Four open tasks.",
        json.dumps({"headline": "Four", "total_open": 4}),
        json.dumps(ANSWER | {"note": "extra"}),
        json.dumps(ANSWER | {"total_open": "4"}),
        json.dumps(ANSWER | {"top_tasks": [{"id": 1, "title": "Fix login redirect loop"}]}),
    ],
)
def test_malformed_answer_is_rejected(client, fake, text):
    assert_rejected(summarize(client, fake, tool_call(), raw_answer(text)))


# Criterion 4


@pytest.mark.parametrize(
    "changes",
    [
        {"total_open": 5},
        {"top_tasks": [{"id": 999, "title": "Fix login redirect loop", "reason": "x"}]},
        {"top_tasks": [{"id": 2, "title": "Update password help text", "reason": "x"}]},
        {"top_tasks": [{"id": 1, "title": "Fix login", "reason": "x"}]},
        {"top_tasks": [*ANSWER["top_tasks"], {"id": 5, "title": "Wrong", "reason": "x"}]},
    ],
)
def test_mismatched_answer_is_rejected(client, fake, changes):
    assert_rejected(summarize(client, fake, tool_call(), answer(**changes)))


def test_total_is_checked_against_all_matches(client, fake):
    call = tool_call({"status": "open", "limit": 1})
    response = summarize(client, fake, call, answer(top_tasks=ANSWER["top_tasks"][:1]))
    assert response.status_code == 200
    assert response.json()["total_open"] == 4


def test_task_outside_tool_result_is_rejected(client, fake):
    call = tool_call({"status": "open", "limit": 1})
    task = {"id": 8, "title": "Tidy settings screen spacing", "reason": "Open"}
    assert_rejected(summarize(client, fake, call, answer(top_tasks=[task])))


def test_answer_without_tool_call_is_rejected(client, fake):
    assert_rejected(summarize(client, fake, answer()))


def test_answer_after_only_failed_tool_calls_is_rejected(client, fake):
    bad_call = tool_call({"status": "closed", "limit": 10})
    assert_rejected(summarize(client, fake, bad_call, bad_call, answer()))


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_refusal_or_truncation_is_rejected(client, fake, stop_reason):
    stopped = raw_answer(json.dumps(ANSWER), stop_reason)
    assert_rejected(summarize(client, fake, tool_call(), stopped))


# Criterion 5


@pytest.mark.parametrize("before", [[], [tool_call()]])
def test_claude_failure_returns_503(client, fake, before):
    response = summarize(client, fake, *before, ClaudeUnavailableError("Claude is down"))
    assert response.status_code == 503
    assert response.json()["error"] == {"code": "claude_unavailable", "message": "Claude is down"}


def test_summary_stops_after_four_requests(client, fake):
    assert_rejected(summarize(client, fake, *[tool_call()] * 5))
    assert len(fake.requests) == 4


def test_answer_on_fourth_request_is_accepted(client, fake):
    response = summarize(client, fake, *[tool_call()] * 3, answer())
    assert response.status_code == 200
    assert len(fake.requests) == 4


# Criterion 6


def test_get_tasks_summary_path_is_still_invalid(client):
    response = client.get("/tasks/summary")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
