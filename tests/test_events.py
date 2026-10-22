def test_record_publishes_event(client):
    from openrecognition.api.routes.events import subscribe, unsubscribe

    q = subscribe()
    try:
        client.app.state.app_state.recognition_logs.record(
            event="recognition.match",
            label="Ada",
            modality="audio",
        )
        item = q.get_nowait()
        assert item["type"] == "recognition.log"
        assert item["log"]["label"] == "Ada"
        assert item["log"]["event"] == "recognition.match"
    finally:
        unsubscribe(q)


def test_event_stream_requires_auth(client):
    r = client.get("/v1/events/stream")
    assert r.status_code == 401
