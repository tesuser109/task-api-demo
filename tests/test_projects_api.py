import pytest


def test_list_projects_returns_all_by_default(client):
    body = client.get("/projects").json()
    assert body["total"] == 3


@pytest.mark.parametrize(("archived", "expected"), [("true", {3}), ("false", {1, 2})])
def test_list_projects_filters_by_archived(client, archived, expected):
    body = client.get("/projects", params={"archived": archived}).json()
    assert {project["id"] for project in body["items"]} == expected
    assert body["total"] == len(expected)
