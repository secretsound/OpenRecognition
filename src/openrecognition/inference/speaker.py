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


def rate_shift(audio: np.ndarray, ratio: float) -> np.ndarray:
    """Play the same samples faster/slower so pitch and pace move together.

    About ±6% (~one semitone) covers the small day-to-day shifts people make
    when talking to a voice assistant, without inventing a different speaker.
    """
    if ratio <= 0 or abs(ratio - 1.0) < 1e-6 or audio.size == 0:
        return audio.astype(np.float32)
    new_len = max(1, int(round(audio.size / ratio)))
    x_old = np.linspace(0.0, 1.0, num=audio.size, dtype=np.float32)
    x_new = np.linspace(0.0, 1.0, num=new_len, dtype=np.float32)
    return np.interp(x_new, x_old, audio.astype(np.float32)).astype(np.float32)


_STYLE_RATIOS = (0.94, 1.06)


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

    def _embed_pcm_session(self, audio: np.ndarray, sr: int, session, cfg: dict) -> np.ndarray:
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

    def _embed_pcm(self, audio: np.ndarray, sr: int) -> np.ndarray:
        session = self.policy.get_session("speaker_embedding")
        if session is not None:
            return self._embed_pcm_session(audio, sr, session, self.pool.onnx_config("speaker_embedding"))
        return heuristic_speaker_embedding(audio, sr)

    def _finish_vectors(self, vecs: list[np.ndarray]) -> np.ndarray:
        stacked = np.stack(vecs)
        out = stacked.mean(axis=0)
        norm = float(np.linalg.norm(out))
        if norm > 1e-9:
            out = out / norm
        return out.astype(np.float32)

    def embed(self, audio_bytes: bytes, *, stabilize: bool = False) -> np.ndarray:
        audio, sr = load_wav_pcm(audio_bytes)
        self.model_version = self.current_model_version()
        self.last_fallback_warning = self.policy.fallback_warning("speaker_embedding")
        if not stabilize:
            return self._embed_pcm(audio, sr)
        vecs = [self._embed_pcm(audio, sr)]
        for ratio in _STYLE_RATIOS:
            vecs.append(self._embed_pcm(rate_shift(audio, ratio), sr))
        return self._finish_vectors(vecs)

    def embed_configured(self, audio_bytes: bytes, *, session, cfg: dict) -> np.ndarray:
        """Embed with a retained model file instead of the active one."""
        audio, sr = load_wav_pcm(audio_bytes)
        return self._embed_pcm_session(audio, sr, session, cfg)

    def _pick_best(self, vector: np.ndarray, rows: list[dict], min_confidence: float, threshold_fn):
        best = None
        best_accepted_sim = -1.0
        best_any_sim = -1.0
        best_thresh = min_confidence
        scored = 0
        thresh_of = threshold_fn or accept_threshold
        for item in rows:
            if item.get("type") not in ("person", "sound"):
                continue
            if item["vector"].size != vector.size:
                continue
            scored += 1
            sim = match.cosine_similarity(vector, item["vector"])
            if sim > best_any_sim:
                best_any_sim = sim
            thresh = thresh_of(item, min_confidence)
            if sim >= thresh and sim > best_accepted_sim:
                best_accepted_sim = sim
                best = item
                best_thresh = thresh
        hit = None
        if best:
            hit = {
                "entity_id": best["id"],
                "label": best["label"],
                "type": best["type"],
                "recognition_type": "speaker",
                "confidence": best_accepted_sim,
                "modality": "audio",
                "threshold_used": best_thresh,
            }
        return hit, best_any_sim, scored

    def match_gallery(
        self,
        vector: np.ndarray,
        gallery: list[dict],
        min_confidence: float,
        return_unknown: bool,
        threshold_fn=None,
    ) -> list[dict]:
        gallery = gallery_for_model(gallery, self.current_model_version())
        hit, best_any_sim, _scored = self._pick_best(vector, gallery, min_confidence, threshold_fn)
        if hit:
            return [hit]
        if return_unknown and best_any_sim >= min_confidence * 0.5:
            return [
                {
                    "entity_id": None,
                    "label": "unknown",
                    "type": "person",
                    "recognition_type": "speaker",
                    "confidence": best_any_sim,
                    "modality": "audio",
                    "threshold_used": None,
                }
            ]
        return []

    def match_retained(
        self,
        audio_bytes: bytes,
        gallery: list[dict],
        min_confidence: float,
        return_unknown: bool,
        *,
        alternates: dict | None = None,
        threshold_fn=None,
        top_k: int = 8,
    ) -> dict:
        """Score a clip with every model that still has saved enrollments.

        The active model is what new samples use. Older files stay in the
        match until those enrollments are saved again with the new model.
        """
        alternates = alternates or {}
        active = self.current_model_version()
        groups: dict[str, list[dict]] = {}
        for item in gallery:
            if item.get("type") not in ("person", "sound"):
                continue
            version = str(item.get("model_version") or active)
            groups.setdefault(version, []).append(item)

        best_hit = None
        best_version = active
        best_vector = None
        best_any_sim = -1.0
        comparable = 0
        ranked: list[dict] = []
        for version, rows in groups.items():
            if version == active:
                vector = self.embed(audio_bytes)
            else:
                embedder = alternates.get(version)
                if embedder is None:
                    continue
                vector = embedder(audio_bytes)
            hit, any_sim, scored = self._pick_best(vector, rows, min_confidence, threshold_fn)
            comparable += scored
            if any_sim > best_any_sim:
                best_any_sim = any_sim
            ranked.extend(
                rank_gallery_matches(
                    vector,
                    rows,
                    {"person", "sound"},
                    min_confidence,
                    "speaker",
                    "audio",
                    top_k=top_k,
                    threshold_fn=threshold_fn,
                )
            )
            if hit and (best_hit is None or hit["confidence"] > best_hit["confidence"]):
                best_hit = hit
                best_version = version
                best_vector = vector

        ranked.sort(key=lambda item: -item["confidence"])
        seen: set[str] = set()
        deduped: list[dict] = []
        for item in ranked:
            key = f"{item.get('entity_id')}:{item.get('recognition_type')}"
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= top_k:
                break

        matches: list[dict] = []
        if best_hit:
            matches.append(best_hit)
        elif return_unknown and best_any_sim >= min_confidence * 0.5:
            matches.append(
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
            best_version = active
            best_vector = None
        return {
            "matches": matches,
            "candidates": deduped,
            "vector": best_vector,
            "model_version": best_version if best_hit else None,
            "comparable": comparable,
        }

    def match_candidates(
        self,
        vector: np.ndarray,
        gallery: list[dict],
        min_confidence: float,
        *,
        top_k: int = 8,
        threshold_fn=None,
    ) -> list[dict]:
        return rank_gallery_matches(
            vector,
            gallery_for_model(gallery, self.current_model_version()),
            {"person", "sound"},
            min_confidence,
            "speaker",
            "audio",
            top_k=top_k,
            threshold_fn=threshold_fn,
        )
