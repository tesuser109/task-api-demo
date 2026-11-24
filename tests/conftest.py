import pytest
from fastapi.testclient import TestClient

from app.db import seed
from app.main import create_app


@pytest.fixture
def app(tmp_path):
    app = create_app(str(tmp_path / "test.db"))
    seed(app.state.conn)
    yield app
    app.state.conn.close()


@pytest.fixture
def client(app):
    return TestClient(app)
