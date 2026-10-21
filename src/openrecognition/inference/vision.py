"""Face and visual re-ID (pets, objects)."""

from typing import Any

import numpy as np
from PIL import Image

from openrecognition.inference.session_pool import ModelSessionPool
from openrecognition.gallery import match
from openrecognition.gallery.match import (
    accept_threshold,
    gallery_for_model,
    rank_gallery_matches,
)

VISUAL_DIM = 512
FACE_MODEL_VERSION = "face-heuristic-v2"
VISUAL_MODEL_VERSION = "visual-reid-heuristic-v2"

_PROJ_CACHE: dict[tuple[int, int], np.ndarray] = {}


def _image_to_array(data: bytes, *, max_side: int = 1024) -> np.ndarray:
    import io

    img = Image.open(io.BytesIO(data)).convert("RGB")
    if max_side and max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.BILINEAR)
    return np.array(img, dtype=np.float32) / 255.0


def _visual_projection(in_dim: int, seed: int) -> np.ndarray:
    key = (in_dim, seed)
    proj = _PROJ_CACHE.get(key)
    if proj is None:
        rng = np.random.default_rng(seed)
        proj = rng.standard_normal((VISUAL_DIM, in_dim), dtype=np.float32)
        proj /= np.linalg.norm(proj, axis=0, keepdims=True) + 1e-9
        _PROJ_CACHE[key] = proj
    return proj


def _extract_visual_features(pixels: np.ndarray) -> np.ndarray:
    h, w, _ = pixels.shape
    parts: list[np.ndarray] = []
    for c in range(3):
        channel = pixels[:, :, c].reshape(-1)
        parts.append(np.histogram(channel, bins=32, range=(0, 1))[0].astype(np.float32))
    grid = 4
    for gi in range(grid):
        for gj in range(grid):
            y0, y1 = gi * h // grid, (gi + 1) * h // grid
            x0, x1 = gj * w // grid, (gj + 1) * w // grid
            patch = pixels[y0:y1, x0:x1]
            if patch.size:
                parts.append(patch.mean(axis=(0, 1)).astype(np.float32))
            else:
                parts.append(np.zeros(3, dtype=np.float32))
    parts.append(pixels.mean(axis=(0, 1)).astype(np.float32))
    parts.append(pixels.std(axis=(0, 1)).astype(np.float32))
    return np.concatenate(parts, dtype=np.float32)


def heuristic_visual_embedding(pixels: np.ndarray, *, seed: int = 42) -> np.ndarray:
    feat = _extract_visual_features(pixels)
    emb = _visual_projection(feat.size, seed) @ feat
    norm = np.linalg.norm(emb)
    if norm > 1e-9:
        emb = emb / norm
    return emb.astype(np.float32)


def _crop_pixels(pixels: np.ndarray, bbox: list[float], *, margin: float = 0.05) -> np.ndarray:
    h, w = pixels.shape[:2]
    x1, y1, x2, y2 = bbox
    bw, bh = x2 - x1, y2 - y1
    x1 = max(0, int(x1 - bw * margin))
    y1 = max(0, int(y1 - bh * margin))
    x2 = min(w, int(x2 + bw * margin))
    y2 = min(h, int(y2 + bh * margin))
    if x2 <= x1 or y2 <= y1:
        return pixels
    return pixels[y1:y2, x1:x2]


def _largest_bbox(bboxes: list[list[float]]) -> list[float] | None:
    if not bboxes:
        return None
    best = bboxes[0]
    best_area = 0.0
    for bb in bboxes:
        area = (bb[2] - bb[0]) * (bb[3] - bb[1])
        if area > best_area:
            best_area = area
            best = bb
    return best


def detect_animal_bbox(pixels: np.ndarray, pool: ModelSessionPool | None = None, policy=None) -> list[list[float]]:
    """YOLO pet crops when ONNX is available; else center-crop heuristic."""
    if pool is not None and policy is not None:
        session = policy.get_session("animal_detector")
        if session is not None:
            from openrecognition.inference.yolo_detect import detect_animal_bboxes

            cfg = pool.onnx_config("animal_detector")
            boxes = detect_animal_bboxes(
                session,
                pixels,
                pets_only=True,
                input_size=int(cfg.get("input_size", 640)),
                conf_thres=float(cfg.get("conf_thres", 0.25)),
            )
            if boxes:
                return boxes
    h, w = pixels.shape[:2]
    margin = 0.15
    return [[w * margin, h * margin, w * (1 - margin), h * (1 - margin)]]


class VisionEngine:
    def __init__(self, pool: ModelSessionPool, policy: "InferencePolicy | None" = None):
        from openrecognition.inference.inference_policy import InferencePolicy

        self.pool = pool
        self.policy = policy or InferencePolicy(pool)
        self.face_model_version = self.current_face_model_version()
        self.visual_model_version = self.current_visual_model_version()
        self.last_face_fallback_warning: str | None = None
        self.last_visual_fallback_warning: str | None = None

    def current_face_model_version(self) -> str:
        return self.policy.effective_model_version("face_embedding", FACE_MODEL_VERSION)

    def current_visual_model_version(self) -> str:
        return self.policy.effective_model_version("visual_reid", VISUAL_MODEL_VERSION)

    def _face_crop_pixels(self, pixels: np.ndarray) -> np.ndarray:
        det_session = self.policy.get_session("face_detector")
        if det_session is not None:
            from openrecognition.inference.scrfd import detect_faces_scrfd

            cfg = self.pool.onnx_config("face_detector")
            size = int(cfg.get("input_size", 640))
            conf = float(cfg.get("conf_thres", 0.5))
            boxes = detect_faces_scrfd(
                det_session,
                pixels,
                input_size=(size, size),
                conf_thres=conf,
            )
            best = _largest_bbox(boxes)
            if best is not None:
                return _crop_pixels(pixels, best, margin=0.1)
        return pixels

    def embed_face(self, image_bytes: bytes) -> np.ndarray:
        pixels = _image_to_array(image_bytes)
        self.face_model_version = self.current_face_model_version()
        self.last_face_fallback_warning = self.policy.fallback_warning("face_embedding")
        session = self.policy.get_session("face_embedding")
        if session is not None:
            from openrecognition.inference.onnx_embedding import embed_image_nchw

            cfg = self.pool.onnx_config("face_embedding")
            self.face_model_version = self.current_face_model_version()
            crop = self._face_crop_pixels(pixels)
            return embed_image_nchw(
                session,
                crop,
                size=int(cfg.get("input_size", 112)),
                embed_dim=int(cfg["embed_dim"]) if cfg.get("embed_dim") else VISUAL_DIM,
                input_norm=str(cfg.get("input_norm", "insightface")),
            )
        return heuristic_visual_embedding(pixels, seed=43)

    def embed_visual(self, image_bytes: bytes, crop_bbox: list[float] | None = None) -> np.ndarray:
        pixels = _image_to_array(image_bytes)
        if crop_bbox:
            pixels = _crop_pixels(pixels, crop_bbox)
            if pixels.size == 0:
                pixels = _image_to_array(image_bytes)
        self.visual_model_version = self.current_visual_model_version()
        self.last_visual_fallback_warning = self.policy.fallback_warning("visual_reid")
        session = self.policy.get_session("visual_reid")
        if session is not None:
            cfg = self.pool.onnx_config("visual_reid")
            self.visual_model_version = self.current_visual_model_version()
            backend = str(cfg.get("backend", "nchw"))
            size = int(cfg.get("input_size", 224))
            dim = int(cfg["embed_dim"]) if cfg.get("embed_dim") else VISUAL_DIM
            norm = str(cfg.get("input_norm", "imagenet"))
            if backend == "classifier":
                from openrecognition.inference.onnx_embedding import embed_image_classifier

                return embed_image_classifier(
                    session, pixels, size=size, embed_dim=dim, input_norm=norm
                )
            from openrecognition.inference.onnx_embedding import embed_image_nchw

            return embed_image_nchw(
                session, pixels, size=size, embed_dim=dim, input_norm=norm
            )
        return heuristic_visual_embedding(pixels, seed=44)

    def match_gallery(
        self,
        vector: np.ndarray,
        gallery: list[dict],
        etypes: set[str],
        min_confidence: float,
        return_unknown: bool,
        recognition_type: str,
    ) -> list[dict]:
        best = None
        best_sim = -1.0
        best_thresh = min_confidence
        for item in gallery:
            if item.get("type") not in etypes:
                continue
            if item["vector"].size != vector.size:
                continue
            sim = match.cosine_similarity(vector, item["vector"])
            thresh = accept_threshold(item, min_confidence)
            if sim >= thresh and sim > best_sim:
                best_sim = sim
                best = item
                best_thresh = thresh
        results = []
        if best:
            results.append(
                {
                    "entity_id": best["id"],
                    "label": best["label"],
                    "type": best["type"],
                    "recognition_type": recognition_type,
                    "confidence": best_sim,
                    "modality": "image",
                    "threshold_used": best_thresh,
                }
            )
        elif return_unknown and best_sim >= min_confidence * 0.5:
            unknown_type = "pet" if "pet" in etypes else "person"
            results.append(
                {
                    "entity_id": None,
                    "label": "unknown",
                    "type": unknown_type,
                    "recognition_type": recognition_type,
                    "confidence": best_sim,
                    "modality": "image",
                }
            )
        return results

    def recognize_image(
        self,
        image_bytes: bytes,
        gallery: list[dict],
        include_faces: bool = True,
        include_pets: bool = True,
        include_objects: bool = True,
        min_confidence: float = 0.75,
        return_unknown: bool = True,
        *,
        include_candidates: bool = False,
    ) -> tuple[list[dict], dict | None]:
        entities: list[dict] = []
        pipelines: list[str] = []
        candidates: list[dict] = []
        notes: list[str] = []

        if include_faces:
            pipelines.append("face")
            vec = self.embed_face(image_bytes)
            face_gallery = gallery_for_model(gallery, self.current_face_model_version())
            entities.extend(
                self.match_gallery(
                    vec,
                    face_gallery,
                    {"person"},
                    min_confidence,
                    return_unknown,
                    "face",
                )
            )
            if include_candidates:
                candidates.extend(
                    rank_gallery_matches(
                        vec,
                        face_gallery,
                        {"person"},
                        min_confidence,
                        "face",
                        "image",
                    )
                )

        pixels = _image_to_array(image_bytes)
        if include_pets or include_objects:
            visual_gallery = gallery_for_model(
                gallery, self.current_visual_model_version()
            )
            for bbox in detect_animal_bbox(pixels, self.pool, self.policy):
                vec = self.embed_visual(image_bytes, bbox)
                if include_pets:
                    pipelines.append("pet")
                    entities.extend(
                        self.match_gallery(
                            vec,
                            visual_gallery,
                            {"pet"},
                            min_confidence,
                            return_unknown,
                            "pet_identity",
                        )
                    )
                    if include_candidates:
                        candidates.extend(
                            rank_gallery_matches(
                                vec,
                                visual_gallery,
                                {"pet"},
                                min_confidence,
                                "pet_identity",
                                "image",
                            )
                        )
                if include_objects:
                    pipelines.append("object")
                    entities.extend(
                        self.match_gallery(
                            vec,
                            visual_gallery,
                            {"object"},
                            min_confidence,
                            return_unknown,
                            "object_identity",
                        )
                    )
                    if include_candidates:
                        candidates.extend(
                            rank_gallery_matches(
                                vec,
                                visual_gallery,
                                {"object"},
                                min_confidence,
                                "object_identity",
                                "image",
                            )
                        )

        diagnostics = None
        if include_candidates:
            if not gallery:
                notes.append("Gallery is empty — enroll identities first.")
            elif not candidates:
                notes.append(
                    "No gallery embeddings matched the embedding size for the pipelines that ran."
                )
            else:
                candidates.sort(key=lambda x: -x["confidence"])
                seen: set[str] = set()
                deduped: list[dict] = []
                for c in candidates:
                    key = f"{c['entity_id']}:{c['recognition_type']}"
                    if key in seen:
                        continue
                    seen.add(key)
                    deduped.append(c)
                candidates = deduped[:12]
            diagnostics = {
                "pipelines": pipelines,
                "candidates": candidates,
                "notes": notes,
            }
        return entities, diagnostics
