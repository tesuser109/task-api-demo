import pytest


def test_status_filter_includes_open_tasks(client):
    body = client.get("/tasks", params={"status": "open"}).json()
    ids = {task["id"] for task in body["items"]}
    assert {1, 3, 5, 8} <= ids


def test_status_filter_excludes_closed_tasks(client):
    """Reported in docs/bug-report.md."""
    body = client.get("/tasks", params={"status": "open"}).json()
    closed = [task["id"] for task in body["items"] if task["status"] == "closed"]
    assert closed == []


@pytest.mark.parametrize(
    ("status", "expected"),
    [("open", [1, 3, 5, 8]), ("in_progress", [4, 7]), ("closed", [2, 6, 9])],
)
def test_status_filter_returns_only_matching_tasks(client, status, expected):
    body = client.get("/tasks", params={"status": status}).json()
    assert [task["id"] for task in body["items"]] == expected
    assert body["total"] == len(expected)


def test_absent_status_returns_every_task(client):
    assert client.get("/tasks").json()["total"] == 9


def test_status_filter_paginates_matches(client):
    body = client.get("/tasks", params={"status": "open", "limit": 2, "offset": 2}).json()
    assert [task["id"] for task in body["items"]] == [5, 8]
    assert body["total"] == 4


@pytest.mark.parametrize("status", ["done", "OPEN", ""])
def test_invalid_status_is_rejected(client, status):
    response = client.get("/tasks", params={"status": status})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
