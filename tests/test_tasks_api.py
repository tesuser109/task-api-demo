def test_list_tasks_returns_all_by_default(client):
    body = client.get("/tasks").json()
    assert [task["id"] for task in body["items"]] == list(range(1, 10))
    assert body["total"] == 9


def test_list_tasks_paginates_without_changing_total(client):
    body = client.get("/tasks", params={"limit": 2, "offset": 2}).json()
    assert [task["id"] for task in body["items"]] == [3, 4]
    assert body["total"] == 9


def test_list_tasks_rejects_invalid_limit(client):
    response = client.get("/tasks", params={"limit": 0})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"


def test_get_task(client):
    assert client.get("/tasks/1").json()["title"] == "Fix login redirect loop"


def test_get_missing_task_returns_not_found(client):
    response = client.get("/tasks/999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_create_task_defaults_to_open(client):
    response = client.post("/tasks", json={"project_id": 1, "title": "Check footer links"})
    assert response.status_code == 201
    assert response.json()["status"] == "open"


def test_create_task_rejects_unknown_project(client):
    response = client.post("/tasks", json={"project_id": 99, "title": "Nope"})
    assert response.status_code == 404
