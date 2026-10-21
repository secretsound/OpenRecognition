def test_swagger_ui(client):
    r = client.get("/docs")
    assert r.status_code == 200
    assert "swagger" in r.text.lower()


def test_redoc(client):
    r = client.get("/redoc")
    assert r.status_code == 200
    assert "redoc" in r.text.lower()


def test_openapi_json(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert schema["info"]["title"] == "OpenRecognition"
    assert "BearerAuth" in schema["components"]["securitySchemes"]
    assert "/v1/recognize/audio" in schema["paths"]


def test_docs_portal(client):
    r = client.get("/api")
    assert r.status_code == 200
    assert "Swagger UI" in r.text


def test_health_lists_documentation(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert "documentation" in r.json()
    assert r.json()["documentation"]["swagger_ui"] == "/docs"
