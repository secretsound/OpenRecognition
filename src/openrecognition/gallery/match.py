"""Embedding similarity and matching."""

import numpy as np


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float32).flatten()
    b = b.astype(np.float32).flatten()
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def robust_centroid(vectors: list[np.ndarray]) -> np.ndarray:
    if not vectors:
        raise ValueError("No vectors")
    stack = np.stack([v.astype(np.float32).flatten() for v in vectors])
    centroid = np.mean(stack, axis=0)
    if len(stack) > 2:
        dists = [cosine_similarity(centroid, v) for v in stack]
        median = np.median(dists)
        kept = [v for v, d in zip(stack, dists) if d >= median - 0.15]
        if kept:
            centroid = np.mean(np.stack(kept), axis=0)
    norm = np.linalg.norm(centroid)
    if norm > 1e-9:
        centroid = centroid / norm
    return centroid.astype(np.float32)


def vector_to_bytes(v: np.ndarray) -> bytes:
    return v.astype(np.float32).tobytes()


def bytes_to_vector(data: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(data, dtype=np.float32).copy()


def separation_score(a: np.ndarray, b: np.ndarray) -> float:
    """Higher = more separable (1 - similarity)."""
    return 1.0 - cosine_similarity(a, b)


def accept_threshold(item: dict, min_confidence: float) -> float:
    """Similarity required to accept a match.

    The request ``min_confidence`` is a floor. A stricter per-enrollment
    threshold raises the bar for that identity only.
    """
    raw = item.get("threshold")
    enrollment = float(raw) if raw is not None else 0.0
    return max(min_confidence, enrollment)


def wyoming_threshold(item: dict, min_confidence: float) -> float:
    """Similarity required to include this identity on the Wyoming path.

    A per-enrollment Wyoming setting replaces the default so a noisy
    microphone can use a lower bar without changing everyone else.
    """
    raw = item.get("wyoming_min_confidence")
    if raw is not None:
        return float(raw)
    return accept_threshold(item, min_confidence)


def gallery_for_model(gallery: list[dict], model_version: str | None) -> list[dict]:
    """Keep gallery rows for this embedding model.

    Rows with no ``model_version`` are left in place so callers that build a
    gallery by hand still match. Once any row is versioned, other versions are
    dropped so a 512-d face centroid cannot score against a 512-d pet centroid.
    """
    if not model_version or not gallery:
        return gallery
    if not any(item.get("model_version") for item in gallery):
        return gallery
    return [item for item in gallery if item.get("model_version") == model_version]


def entity_threshold(item: dict) -> float | None:
    t = item.get("threshold")
    return float(t) if t is not None else None


def rank_gallery_matches(
    vector: np.ndarray,
    gallery: list[dict],
    etypes: set[str],
    min_confidence: float,
    recognition_type: str,
    modality: str,
    *,
    top_k: int = 8,
    threshold_fn=None,
) -> list[dict]:
    """Top gallery hits by similarity, whether or not they pass threshold."""
    thresh_of = threshold_fn or accept_threshold
    ranked: list[dict] = []
    for item in gallery:
        if item.get("type") not in etypes:
            continue
        if item["vector"].size != vector.size:
            continue
        sim = cosine_similarity(vector, item["vector"])
        thresh = thresh_of(item, min_confidence)
        ranked.append(
            {
                "entity_id": item["id"],
                "label": item["label"],
                "type": item["type"],
                "recognition_type": recognition_type,
                "confidence": sim,
                "modality": modality,
                "threshold_used": thresh,
                "enrollment_threshold": entity_threshold(item),
                "accepted": sim >= thresh,
            }
        )
    ranked.sort(key=lambda x: -x["confidence"])
    return ranked[:top_k]
