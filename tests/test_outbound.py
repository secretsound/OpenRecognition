import pytest

from openrecognition.inference.sound_events import classify_sound_events
from openrecognition.outbound import UnsafeUrlError, validate_outbound_url
from tests.helpers import wav_bytes


def test_blocks_metadata_and_loopback():
    with pytest.raises(UnsafeUrlError):
        validate_outbound_url("http://169.254.169.254/latest/meta-data")
    with pytest.raises(UnsafeUrlError):
        validate_outbound_url("http://127.0.0.1/secret")
    with pytest.raises(UnsafeUrlError):
        validate_outbound_url("file:///etc/passwd")


def test_allows_lan_and_loopback_when_opted_in():
    assert validate_outbound_url("http://192.168.1.20:8123/api/webhook").startswith("http://192.168")
    assert validate_outbound_url("http://127.0.0.1:9999/hook", allow_loopback=True).startswith(
        "http://127.0.0.1"
    )


def test_image_url_and_webhook_reject_metadata(client, auth_headers):
    image = client.post(
        "/v1/recognize/image/url",
        headers=auth_headers,
        json={"url": "http://169.254.169.254/latest/meta-data"},
    )
    assert image.status_code == 400
    assert image.json()["code"] == "UNSAFE_URL"

    loopback = client.post(
        "/v1/recognize/image/url",
        headers=auth_headers,
        json={"url": "http://127.0.0.1/photo.jpg"},
    )
    assert loopback.status_code == 400

    hook = client.post(
        "/v1/webhooks/subscriptions",
        headers=auth_headers,
        json={
            "url": "http://169.254.169.254/latest/meta-data",
            "events": ["recognition.match"],
            "debounce_seconds": 5,
            "filters": {},
        },
    )
    assert hook.status_code == 400
    assert hook.json()["code"] == "UNSAFE_URL"


def test_loud_clip_is_not_labeled_bark():
    entities = classify_sound_events(wav_bytes(duration=0.5, freq=100))
    assert all(entity.label != "bark" for entity in entities)
