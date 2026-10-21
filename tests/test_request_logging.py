"""HTTP request logging middleware."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from openrecognition.api.request_logging import RequestLoggingMiddleware


def test_request_logging_adds_timing_header():
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/v1/example")
    def example():
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/v1/example")
    assert response.status_code == 200
    assert "X-Response-Time-Ms" in response.headers
    assert float(response.headers["X-Response-Time-Ms"]) >= 0
