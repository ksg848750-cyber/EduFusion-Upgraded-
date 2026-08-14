from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app import main as main_module
from app.main import app


@pytest.fixture(autouse=True)
def _no_db(monkeypatch):
    """Keep tests hermetic: never open a real DB pool or hit the network.
    Patches the bindings actually invoked by the lifespan hook in app.main.
    """
    async def noop():
        return None

    monkeypatch.setattr(main_module, "init_pool", noop)
    monkeypatch.setattr(main_module, "close_pool", noop)


@pytest.fixture
def client(monkeypatch) -> TestClient:
    """TestClient whose DB pool is left uninitialized (no network), so the
    user store returns None unless the service is mocked.
    """

    def fake_claims() -> dict[str, Any]:
        return {
            "sub": "test-auth-uid-123",
            "email": "learner@example.com",
            "user_metadata": {"name": "Test Learner"},
            "exp": 9999999999,
        }

    app.dependency_overrides[get_current_user] = fake_claims
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def authed_client(client) -> TestClient:
    return client


@pytest.fixture
def raw_client() -> TestClient:
    """Client with no dependency override -> exercises the real auth path."""
    with TestClient(app) as c:
        yield c
