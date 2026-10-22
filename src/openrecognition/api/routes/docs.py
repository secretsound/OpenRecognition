"""API documentation landing page."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["health"])


@router.get("/api", response_class=HTMLResponse, include_in_schema=False)
def api_docs_portal():
    """Simple index linking to Swagger UI and ReDoc."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>OpenRecognition API</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 40rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }
    a { color: #2563eb; }
    .card { border: 1px solid #ddd; border-radius: 8px; padding: 1rem 1.25rem; margin: 1rem 0; }
    h1 { margin-top: 0; }
  </style>
</head>
<body>
  <h1>OpenRecognition API</h1>
  <p>Interactive OpenAPI documentation for integrators and Home Assistant developers.</p>
  <div class="card">
    <h2><a href="/docs">Swagger UI</a></h2>
    <p>Try endpoints in the browser. Use <strong>Authorize</strong> with your API key.</p>
  </div>
  <div class="card">
    <h2><a href="/redoc">ReDoc</a></h2>
    <p>Readable reference documentation generated from the same OpenAPI schema.</p>
  </div>
  <p><a href="/openapi.json">openapi.json</a> · <a href="/health">health</a> · <a href="/">Console</a></p>
</body>
</html>
"""
