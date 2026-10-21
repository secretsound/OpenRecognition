"""Face / visual heuristic embedding tests."""

from io import BytesIO

import numpy as np
from PIL import Image

from openrecognition.gallery import match
from openrecognition.inference.vision import _image_to_array, heuristic_visual_embedding

def _png_bytes(color=(80, 120, 200)) -> bytes:
    img = Image.new("RGB", (64, 64), color=color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _embed_png(data: bytes, *, seed: int = 43) -> np.ndarray:
    pixels = _image_to_array(data)
    return heuristic_visual_embedding(pixels, seed=seed)


def test_same_image_has_high_similarity():
    data = _png_bytes()
    e1 = _embed_png(data)
    e2 = _embed_png(data)
    assert match.cosine_similarity(e1, e2) > 0.99


def test_different_images_less_similar_than_repeat():
    a = _embed_png(_png_bytes((80, 120, 200)))
    again = _embed_png(_png_bytes((80, 120, 200)))
    b = _embed_png(_png_bytes((200, 60, 40)))
    assert match.cosine_similarity(a, again) > match.cosine_similarity(a, b)


def test_enrolled_face_matches_same_image(client, auth_headers):
    # Unique color avoids matching another test's solid-color face enrollment in the shared DB.
    png = _png_bytes(color=(17, 83, 201))
    r = client.post(
        "/v1/enrollments",
        headers=auth_headers,
        data={"type": "person", "label": "facetest"},
        files=[
            ("files", ("f1.png", png, "image/png")),
            ("files", ("f2.png", png, "image/png")),
            ("files", ("f3.png", png, "image/png")),
        ],
    )
    assert r.status_code == 200

    r2 = client.post(
        "/v1/recognize/image?min_confidence=0.5&include_candidates=true",
        headers=auth_headers,
        files={"file": ("query.png", png, "image/png")},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["entities"]
    assert body["entities"][0]["label"] == "facetest"
    assert body["entities"][0]["confidence"] >= 0.5
