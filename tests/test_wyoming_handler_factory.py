"""Wyoming handler factory must pass reader/writer to AsyncEventHandler."""

from openrecognition.integrator.wyoming.handler import SpeakerProxyHandler


def test_speaker_proxy_handler_accepts_reader_writer_kwargs():
    class FakeReader:
        pass

    class FakeWriter:
        pass

    handler = SpeakerProxyHandler(
        "info",
        "state",
        "tcp://127.0.0.1:10300",
        reader=FakeReader(),
        writer=FakeWriter(),
    )
    assert handler.reader is not None
    assert handler.writer is not None
