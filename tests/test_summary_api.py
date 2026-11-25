import json
from pathlib import Path

import anthropic
import pytest
from anthropic.types.beta import BetaMessage

from app.claude_client import ClaudeUnavailableError, get_claude_client
from app.models import TaskStatus
from app.services.task_service import TaskService

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "docs" / "summary"
VALID_ARGS = {"status": "open", "limit": 100}
LOGIN = {"id": 1, "title": "Fix login redirect loop", "reason": "High priority"}
INBOX = {"id": 3, "title": "Crash when opening an empty inbox", "reason": "High priority"}
SUMMARY = {"headline": "Four open tasks.", "total_open": 4, "top_tasks": [LOGIN, INBOX]}


def reply(stop_reason, *content):
    return BetaMessage.model_validate(
        {
            "id": "msg_fake",
            "type": "message",
            "role": "assistant",
            "model": "fake",
            "content": list(content),
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }
    )


def tool_use(args=VALID_ARGS, name="list_tasks", block_id="toolu_1"):
    return {"type": "tool_use", "id": block_id, "name": name, "input": args}


def call(args=VALID_ARGS, name="list_tasks"):
    return reply("tool_use", tool_use(args, name))


def text(value, stop_reason="end_turn"):
    return reply(stop_reason, {"type": "text", "text": value})


def answer(**changes):
    return text(json.dumps(SUMMARY | changes))


class FakeClaude:
    """Returns scripted replies. Exceptions are raised, callables run before the next reply."""

    def __init__(self):
        self.script, self.requests = [], []

    def create(self, **request):
        self.requests.append(request | {"messages": list(request["messages"])})
        step = self.script.pop(0)
        while callable(step):
            step()
            step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    def tool_results(self, request_index=1):
        return self.requests[request_index]["messages"][-1]["content"]


@pytest.fixture(autouse=True)
def block_live_client(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Tests must not create a live Claude client")

    monkeypatch.setattr(anthropic, "Anthropic", fail)


@pytest.fixture
def claude(app):
    claude = FakeClaude()
    app.dependency_overrides[get_claude_client] = lambda: claude
    return claude


@pytest.fixture
def summarize(client, claude):
    def run(*script):
        claude.script = list(script)
        return client.post("/tasks/summary")

    return run


@pytest.fixture
def service_calls(monkeypatch):
    calls, original = [], TaskService.list_tasks

    def spy(self, **kwargs):
        calls.append(kwargs)
        return original(self, **kwargs)

    monkeypatch.setattr(TaskService, "list_tasks", spy)
    return calls


@pytest.fixture
def close_task(app):
    def close(task_id):
        app.state.conn.execute("UPDATE tasks SET status = 'closed' WHERE id = ?", [task_id])
        app.state.conn.commit()

    return close


def load_schema(name):
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def assert_rejected(response, message):
    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "summary_rejected"
    assert message in error["message"]


# 1. The endpoint


def test_summary_returns_open_tasks(summarize):
    response = summarize(call(), answer())
    assert response.status_code == 200
    assert response.json() == SUMMARY


def test_summary_without_open_tasks(summarize, close_task):
    for task_id in [1, 3, 5, 8]:
        close_task(task_id)
    response = summarize(call(), answer(total_open=0, top_tasks=[]))
    assert response.status_code == 200
    assert response.json()["total_open"] == 0


# 2. The tool


def test_claude_gets_exactly_one_tool(summarize, claude):
    summarize(call(), answer())
    tools = [load_schema("tool-schema.json")]
    assert [request["tools"] for request in claude.requests] == [tools, tools]


def test_tool_runs_through_task_service(summarize, claude, service_calls):
    tool_call = call()
    summarize(tool_call, answer())
    assert service_calls == [{"limit": 100, "offset": 0, "status": TaskStatus.OPEN}]
    sent = claude.requests[1]["messages"]
    assert sent[-2] == {"role": "assistant", "content": tool_call.content}
    [result] = claude.tool_results()
    assert result["tool_use_id"] == "toolu_1"
    assert "is_error" not in result
    page = json.loads(result["content"])
    assert [task["id"] for task in page["items"]] == [1, 3, 5, 8]
    assert page["total"] == 4


@pytest.mark.parametrize("limit", [1, 100])
def test_tool_limit_bounds_are_allowed(summarize, service_calls, limit):
    response = summarize(call({"status": "open", "limit": limit}), answer(top_tasks=[LOGIN]))
    assert response.status_code == 200
    assert service_calls[0]["limit"] == limit


@pytest.mark.parametrize(
    ("args", "name"),
    [
        ({"status": "closed", "limit": 10}, "list_tasks"),
        ({"status": "in_progress", "limit": 10}, "list_tasks"),
        ({"status": "OPEN", "limit": 10}, "list_tasks"),
        ({"status": None, "limit": 10}, "list_tasks"),
        ({"status": "open", "limit": 0}, "list_tasks"),
        ({"status": "open", "limit": 101}, "list_tasks"),
        ({"status": "open", "limit": "10"}, "list_tasks"),
        ({"status": "open", "limit": 1.5}, "list_tasks"),
        ({"status": "open", "limit": True}, "list_tasks"),
        ({"status": "open"}, "list_tasks"),
        ({"limit": 10}, "list_tasks"),
        ({"status": "open", "limit": 10, "offset": 1}, "list_tasks"),
        (VALID_ARGS, "delete_tasks"),
    ],
)
def test_invalid_tool_call_runs_nothing(summarize, claude, service_calls, args, name):
    response = summarize(call(args, name), answer())
    assert_rejected(response, "without a tool result")
    [result] = claude.tool_results()
    assert result["tool_use_id"] == "toolu_1"
    assert result["is_error"] is True
    assert service_calls == []


def test_claude_can_recover_from_an_invalid_call(summarize, service_calls):
    response = summarize(call({"status": "closed", "limit": 10}), call(), answer())
    assert response.status_code == 200
    assert len(service_calls) == 1


def test_parallel_calls_each_get_a_result(summarize, claude, service_calls):
    blocks = [tool_use(), tool_use({"status": "closed", "limit": 5}, block_id="toolu_2")]
    response = summarize(reply("tool_use", *blocks), answer())
    assert response.status_code == 200
    first, second = claude.tool_results()
    assert (first["tool_use_id"], second["tool_use_id"]) == ("toolu_1", "toolu_2")
    assert "is_error" not in first
    assert second["is_error"] is True
    assert len(service_calls) == 1


# 3. Structured output


def test_every_request_uses_the_output_schema(summarize, claude):
    summarize(call(), answer())
    schema = load_schema("output-schema.json")
    assert [request["output_schema"] for request in claude.requests] == [schema, schema]


@pytest.mark.parametrize(
    "value",
    [
        "",
        "Four open tasks.",
        json.dumps({"headline": "Four open tasks.", "total_open": 4}),
        json.dumps(SUMMARY | {"total_open": "4"}),
        json.dumps(SUMMARY | {"extra": 1}),
        json.dumps(SUMMARY | {"top_tasks": [{"id": 1, "title": LOGIN["title"]}]}),
    ],
)
def test_malformed_answer_is_rejected(summarize, value):
    assert_rejected(summarize(call(), text(value)), "output schema")


# 4. Verification


@pytest.mark.parametrize("total", [3, 5, 9])
def test_wrong_total_is_rejected(summarize, total):
    assert_rejected(summarize(call(), answer(total_open=total)), "total_open")


@pytest.mark.parametrize(
    "task",
    [
        LOGIN | {"id": 999},
        LOGIN | {"id": 3},
        LOGIN | {"title": "Fix login"},
        {"id": 2, "title": "Update password help text", "reason": "Closed"},
    ],
)
@pytest.mark.parametrize("before", [[], [INBOX]])
def test_wrong_top_task_is_rejected(summarize, task, before):
    assert_rejected(summarize(call(), answer(top_tasks=[*before, task])), "does not match")


def test_total_counts_every_match_not_just_the_page(summarize):
    response = summarize(call({"status": "open", "limit": 1}), answer(top_tasks=[LOGIN]))
    assert response.status_code == 200
    assert response.json()["total_open"] == 4


def test_open_task_outside_the_tool_result_is_rejected(summarize):
    response = summarize(call({"status": "open", "limit": 1}), answer(top_tasks=[INBOX]))
    assert_rejected(response, "does not match")


def test_task_missing_from_the_latest_result_is_rejected(summarize, close_task):
    final = answer(total_open=3, top_tasks=[LOGIN])
    response = summarize(call(), lambda: close_task(1), call(), final)
    assert_rejected(response, "does not match")


def test_latest_result_is_used_after_a_task_closes(summarize, close_task):
    final = answer(total_open=3, top_tasks=[INBOX])
    response = summarize(call(), lambda: close_task(1), call(), final)
    assert response.status_code == 200


def test_invalid_call_does_not_discard_the_earlier_result(summarize):
    response = summarize(call(), call({"status": "closed", "limit": 10}), answer())
    assert response.status_code == 200


def test_duplicate_top_task_is_rejected(summarize):
    assert_rejected(summarize(call(), answer(top_tasks=[LOGIN, LOGIN])), "more than once")


def test_answer_without_a_tool_call_is_rejected(summarize):
    assert_rejected(summarize(answer()), "without a tool result")


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_incomplete_answer_is_rejected(summarize, stop_reason):
    response = summarize(call(), text(json.dumps(SUMMARY), stop_reason))
    assert_rejected(response, stop_reason)


# 5. Claude failures and the request cap


@pytest.mark.parametrize("before", [[], [call()]])
def test_claude_failure_returns_503(summarize, before):
    response = summarize(*before, ClaudeUnavailableError("Claude could not be reached"))
    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "claude_unavailable",
        "message": "Claude could not be reached",
    }


def test_fourth_request_can_answer(summarize, claude):
    assert summarize(call(), call(), call(), answer()).status_code == 200
    assert len(claude.requests) == 4


def test_there_is_no_fifth_request(summarize, claude):
    assert_rejected(summarize(*[call()] * 4, answer()), "4 requests")
    assert len(claude.requests) == 4


# 6. Existing endpoints


def test_get_summary_path_is_still_an_invalid_task_id(client):
    response = client.get("/tasks/summary")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
