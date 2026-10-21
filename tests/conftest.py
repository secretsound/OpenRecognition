import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Test config before app import
tmpdir = tempfile.mkdtemp()
os.environ["OPENRECOGNITION_DATA_DIR"] = tmpdir
os.environ["OPENRECOGNITION_AUTH_REQUIRED"] = "true"
os.environ["OPENRECOGNITION_MODEL_PACKS_DIR"] = str(
    Path(__file__).resolve().parent / "fixtures" / "model-packs"
)
# Fixture pack has manifests but no .onnx files (deterministic heuristics in CI).
os.environ["OPENRECOGNITION_PACK"] = "edge"
# Keep CI/tests on heuristics even if dev machine has ONNX files under model-packs/edge.
os.environ["OPENRECOGNITION_INFERENCE_BACKEND"] = "heuristic"


@pytest.fixture(scope="module")
def client():
    from openrecognition.api.app import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(scope="module")
def admin_key(client):
    state = client.app.state.app_state
    if not state.sessions.has_users():
        state.sessions.create_user("admin", "test-admin-password", "admin")
    created = state.api_keys.create_key(
        "test-admin",
        ["admin", "read", "enroll", "recognize"],
    )
    return created["key"]


@pytest.fixture
def auth_headers(admin_key):
    return {"Authorization": f"Bearer {admin_key}"}


@pytest.fixture(autouse=True)
def _heuristic_inference_for_tests(client):
    """Isolate tests from persisted runtime settings and admin API backend changes."""
    state = client.app.state.app_state
    state.inference_policy.set_backend("heuristic")
    state.settings.inference_backend = "heuristic"
    yield


