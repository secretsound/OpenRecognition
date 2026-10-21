import io

from PIL import Image

from tests.helpers import wav_bytes


def _png_bytes() -> bytes:
    img = Image.new("RGB", (128, 128), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_recognize_image(client, auth_headers):
    client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "pet", "label": "Pepper", "species_hint": "cat"},
        files=[("files", ("p.png", _png_bytes(), "image/png"))],
    )
    r = client.post(
        "/v1/recognize/image",
        headers=auth_headers,
        files={"file": ("p.png", _png_bytes(), "image/png")},
    )
    assert r.status_code == 200
    assert "entities" in r.json()


def test_gallery_export_import(client, auth_headers):
    r = client.post("/v1/gallery/export", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["enrollment_count"] >= 0
