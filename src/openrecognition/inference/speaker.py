"""Speaker embedding extraction."""

import numpy as np

from openrecognition.inference.audio_gate import load_wav_pcm, resample
from openrecognition.inference.session_pool import ModelSessionPool
from openrecognition.gallery import match
from openrecognition.gallery.match import (
    accept_threshold,
    gallery_for_model,
    rank_gallery_matches,
)


EMBED_DIM = 192
HEURISTIC_MODEL_VERSION = "speaker-heuristic-v2"
MODEL_VERSION = HEURISTIC_MODEL_VERSION  # default label; runtime may override on engine

# Fixed projection: similar spectral features → similar embeddings (unlike SHA hashing).
_SPEAKER_PROJ: np.ndarray | None = None


def _speaker_projection(in_dim: int) -> np.ndarray:
    global _SPEAKER_PROJ
    if _SPEAKER_PROJ is None or _SPEAKER_PROJ.shape[1] != in_dim:
        rng = np.random.default_rng(42)
        proj = rng.standard_normal((EMBED_DIM, in_dim), dtype=np.float32)
        proj /= np.linalg.norm(proj, axis=0, keepdims=True) + 1e-9
        _SPEAKER_PROJ = proj
    return _SPEAKER_PROJ


def _extract_features(audio: np.ndarray, sr: int) -> np.ndarray:
    audio = resample(audio, sr, 16000)
    if len(audio) < 1600:
        audio = np.pad(audio, (0, 1600 - len(audio)))
    frame_len = 400
    hops: list[np.ndarray] = []
    for i in range(0, len(audio) - frame_len, frame_len // 2):
        frame = audio[i : i + frame_len]
        spec = np.abs(np.fft.rfft(frame * np.hanning(len(frame))))
        hops.append(spec[:64])
    if not hops:
        hops = [np.zeros(64, dtype=np.float32)]
    stack = np.stack(hops)
    return np.concatenate(
        [
            np.mean(stack, axis=0),
            np.std(stack, axis=0),
            np.percentile(stack, 25, axis=0)[:16],
            np.percentile(stack, 75, axis=0)[:16],
            [np.mean(audio), np.std(audio), float(np.max(np.abs(audio)))],
        ],
        dtype=np.float32,
    )


def heuristic_speaker_embedding(audio: np.ndarray, sr: int) -> np.ndarray:
    feat = _extract_features(audio, sr)
    emb = _speaker_projection(feat.size) @ feat
    norm = np.linalg.norm(emb)
    if norm > 1e-9:
        emb = emb / norm
    return emb.astype(np.float32)


class SpeakerEngine:
    def __init__(self, pool: ModelSessionPool, policy: "InferencePolicy | None" = None):
        from openrecognition.inference.inference_policy import InferencePolicy

        self.pool = pool
        self.policy = policy or InferencePolicy(pool)
        self.model_version = self.current_model_version()
        self.last_fallback_warning: str | None = None

    def current_model_version(self) -> str:
        return self.policy.effective_model_version(
            "speaker_embedding", HEURISTIC_MODEL_VERSION
        )

    def embed(self, audio_bytes: bytes) -> np.ndarray:
        audio, sr = load_wav_pcm(audio_bytes)
        self.model_version = self.current_model_version()
        self.last_fallback_warning = self.policy.fallback_warning("speaker_embedding")
        session = self.policy.get_session("speaker_embedding")
        if session is not None:
            cfg = self.pool.onnx_config("speaker_embedding")
            self.model_version = self.current_model_version()
            preprocessor = cfg.get("preprocessor", "wespeaker_fbank")
            embed_dim = int(cfg["embed_dim"]) if cfg.get("embed_dim") else EMBED_DIM
            if preprocessor == "wespeaker_fbank":
                from openrecognition.inference.speaker_fbank import embed_wespeaker_onnx

                return embed_wespeaker_onnx(
                    session,
                    audio,
                    sr,
                    num_mel_bins=int(cfg.get("num_mel_bins", 80)),
                    max_seconds=float(cfg.get("max_seconds", 15.0)),
                    embed_dim=embed_dim,
                )
            from openrecognition.inference.onnx_embedding import embed_audio_waveform

            return embed_audio_waveform(
                session,
                audio,
                sr,
                sample_rate=int(cfg.get("sample_rate", 16000)),
                min_samples=int(cfg.get("min_samples", 4800)),
                embed_dim=embed_dim,
            )
        return heuristic_speaker_embedding(audio, sr)

    def match_gallery(
        self,
        vector: np.ndarray,
        gallery: list[dict],
        min_confidence: float,
        return_unknown: bool,
    ) -> list[dict]:
        best = None
        best_accepted_sim = -1.0
        best_any_sim = -1.0
        best_thresh = min_confidence
        gallery = gallery_for_model(gallery, self.current_model_version())
        for item in gallery:
            if item.get("type") not in ("person", "sound"):
                continue
            if item["vector"].size != vector.size:
                continue
            sim = match.cosine_similarity(vector, item["vector"])
            if sim > best_any_sim:
                best_any_sim = sim
            thresh = accept_threshold(item, min_confidence)
            if sim >= thresh and sim > best_accepted_sim:
                best_accepted_sim = sim
                best = item
                best_thresh = thresh
        results = []
        if best:
            results.append(
                {
                    "entity_id": best["id"],
                    "label": best["label"],
                    "type": best["type"],
                    "recognition_type": "speaker",
                    "confidence": best_accepted_sim,
                    "modality": "audio",
                    "threshold_used": best_thresh,
                }
            )
        elif return_unknown and best_any_sim >= min_confidence * 0.5:
            results.append(
                {
                    "entity_id": None,
                    "label": "unknown",
                    "type": "person",
                    "recognition_type": "speaker",
                    "confidence": best_any_sim,
                    "modality": "audio",
                    "threshold_used": None,
                }
            )
        return results

    def match_candidates(
        self,
        vector: np.ndarray,
        gallery: list[dict],
        min_confidence: float,
        *,
        top_k: int = 8,
    ) -> list[dict]:
        return rank_gallery_matches(
            vector,
            gallery_for_model(gallery, self.current_model_version()),
            {"person", "sound"},
            min_confidence,
            "speaker",
            "audio",
            top_k=top_k,
        )
