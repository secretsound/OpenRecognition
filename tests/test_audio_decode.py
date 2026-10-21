import pytest

from openrecognition.inference.audio_gate import AudioDecodeError, load_wav_pcm
from tests.helpers import wav_bytes


def test_load_wav_pcm_accepts_wav():
    audio, sr = load_wav_pcm(wav_bytes())
    assert sr == 16000
    assert len(audio) > 0


def test_load_wav_pcm_rejects_webm_without_ffmpeg():
    webm_stub = b"\x1a\x45\xdf\xa3" + b"\x00" * 100
    with pytest.raises(AudioDecodeError) as exc:
        load_wav_pcm(webm_stub)
    assert "WebM" in str(exc.value) or "ffmpeg" in str(exc.value).lower()
