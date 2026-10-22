"""Audio VAD and gate classification."""

import io
import shutil
import subprocess
import time
import wave
from typing import Any

import numpy as np

from openrecognition.inference.session_pool import ModelSessionPool
from openrecognition.models.schemas import GateResponse


class AudioDecodeError(ValueError):
    """Audio bytes could not be decoded to mono PCM."""


def _detect_container(data: bytes) -> str | None:
    if len(data) < 4:
        return None
    if data[:4] == b"RIFF":
        return "WAV"
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "MP3"
    if data[:4] == b"fLaC":
        return "FLAC"
    if data[:4] == b"OggS":
        return "OGG"
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "WebM"
    if len(data) >= 8 and data[4:8] == b"ftyp":
        return "MP4"
    return None


def _load_with_soundfile(data: bytes) -> tuple[np.ndarray, int] | None:
    try:
        import soundfile as sf

        audio, sr = sf.read(io.BytesIO(data), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        return audio.astype(np.float32), int(sr)
    except Exception:
        return None


def _load_wav_with_wave(data: bytes) -> tuple[np.ndarray, int] | None:
    try:
        with wave.open(io.BytesIO(data), "rb") as wf:
            nch = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            sr = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
    except (wave.Error, EOFError, OSError):
        return None
    if sampwidth == 2:
        pcm = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 1:
        pcm = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sampwidth == 4:
        pcm = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        return None
    if nch > 1:
        pcm = pcm.reshape(-1, nch).mean(axis=1)
    return pcm.astype(np.float32), int(sr)


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _load_with_ffmpeg(data: bytes) -> tuple[np.ndarray, int] | None:
    if not _ffmpeg_available():
        return None
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                "pipe:0",
                "-f",
                "s16le",
                "-acodec",
                "pcm_s16le",
                "-ac",
                "1",
                "-ar",
                "16000",
                "pipe:1",
            ],
            input=data,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    pcm = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    return pcm, 16000


def _load_raw_pcm16(data: bytes) -> tuple[np.ndarray, int] | None:
    if len(data) < 2 or len(data) % 2 != 0:
        return None
    samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
    return samples, 16000


def load_wav_pcm(data: bytes) -> tuple[np.ndarray, int]:
    """Decode audio bytes to mono float32 samples and sample rate."""
    if not data:
        raise AudioDecodeError("Empty audio payload")

    for loader in (_load_with_soundfile, _load_wav_with_wave, _load_with_ffmpeg):
        result = loader(data)
        if result is not None:
            return result

    container = _detect_container(data)
    if container:
        if container in ("MP3", "WebM", "MP4") and not _ffmpeg_available():
            raise AudioDecodeError(
                f"Cannot decode {container} audio: install ffmpeg on the server "
                "(e.g. apt install ffmpeg) or upload WAV/FLAC/OGG."
            )
        raise AudioDecodeError(
            f"Could not decode {container} audio. Try WAV, FLAC, or OGG, or re-encode the file."
        )

    result = _load_raw_pcm16(data)
    if result is not None:
        return result

    raise AudioDecodeError(
        "Unrecognized audio format. Upload WAV, FLAC, OGG, or 16-bit mono PCM at 16 kHz."
    )


def resample(audio: np.ndarray, sr: int, target: int = 16000) -> np.ndarray:
    if sr == target or len(audio) == 0:
        return audio
    duration = len(audio) / sr
    new_len = int(duration * target)
    if new_len < 1:
        return audio
    x_old = np.linspace(0, 1, len(audio))
    x_new = np.linspace(0, 1, new_len)
    return np.interp(x_new, x_old, audio).astype(np.float32)


def heuristic_gate(audio: np.ndarray, sr: int) -> GateResponse:
    start = time.perf_counter()
    audio = resample(audio, sr)
    if len(audio) < sr * 0.1:
        return GateResponse(
            gate="reject",
            reason="too_short",
            scores={"speech": 0.0, "music": 0.0, "noise": 1.0},
            latency_ms=(time.perf_counter() - start) * 1000,
        )
    rms = float(np.sqrt(np.mean(audio**2)))
    zcr = float(np.mean(np.abs(np.diff(np.sign(audio)))) / 2)
    spec = np.abs(np.fft.rfft(audio[: min(len(audio), sr)]))
    spec_energy = float(np.mean(spec))
    speech_score = min(1.0, rms * 8 + zcr * 2)
    music_score = min(1.0, spec_energy * 0.01) if zcr < 0.08 else 0.1
    noise_score = max(0.0, 1.0 - speech_score - music_score * 0.5)
    total = speech_score + music_score + noise_score + 1e-9
    scores = {
        "speech": speech_score / total,
        "music": music_score / total,
        "noise": noise_score / total,
    }
    if scores["speech"] >= 0.35 and rms >= 0.01:
        gate, reason = "accept", None
    elif scores["music"] > 0.5:
        gate, reason = "reject", "music"
    elif rms < 0.005:
        gate, reason = "reject", "silence"
    else:
        gate, reason = "reject", "background_noise"
    return GateResponse(
        gate=gate,
        reason=reason,
        scores=scores,
        latency_ms=(time.perf_counter() - start) * 1000,
    )


class AudioGateEngine:
    def __init__(self, pool: ModelSessionPool, policy: "InferencePolicy | None" = None):
        from openrecognition.inference.inference_policy import InferencePolicy

        self.pool = pool
        self.policy = policy or InferencePolicy(pool)
        ver = pool.model_version("silero_vad")
        self.model_version = ver or "heuristic-gate-v1"
        self.last_fallback_warning: str | None = None
        self.last_classifier_fallback_warning: str | None = None

    def run(self, audio_bytes: bytes) -> GateResponse:
        audio, sr = load_wav_pcm(audio_bytes)
        self.last_fallback_warning = self.policy.fallback_warning("silero_vad")
        self.last_classifier_fallback_warning = self.policy.fallback_warning(
            "audio_gate_classifier"
        )

        vad_session = self.policy.get_session("silero_vad")
        clf_session = self.policy.get_session("audio_gate_classifier")

        if vad_session is not None:
            from openrecognition.inference.silero_vad import gate_with_silero

            self.model_version = self.pool.model_version("silero_vad") or "silero-vad-onnx"
            threshold = float(self.pool.onnx_config("silero_vad").get("speech_threshold", 0.28))
            result = gate_with_silero(
                vad_session, audio, sr, speech_threshold=threshold
            )
            if clf_session is not None:
                from openrecognition.inference.gate_classifier import refine_gate_with_classifier

                ver = self.pool.model_version("audio_gate_classifier")
                if ver:
                    self.model_version = f"{self.model_version}+{ver}"
                result = refine_gate_with_classifier(clf_session, audio, sr, result)
            return result

        if clf_session is not None:
            from openrecognition.inference.gate_classifier import gate_with_yamnet

            self.model_version = (
                self.pool.model_version("audio_gate_classifier") or "yamnet-gate-v1"
            )
            return gate_with_yamnet(clf_session, audio, sr)

        return heuristic_gate(audio, sr)
