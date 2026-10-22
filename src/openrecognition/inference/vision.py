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

    def _detect_face_boxes(self, pixels: np.ndarray) -> list[list[float]]:
        det_session = self.policy.get_session("face_detector")
        if det_session is None:
            return []
        from openrecognition.inference.scrfd import detect_faces_scrfd

        cfg = self.pool.onnx_config("face_detector")
        return detect_faces_scrfd(
            det_session,
            pixels,
            input_size=(int(cfg.get("input_size", 640)), int(cfg.get("input_size", 640))),
            conf_thres=float(cfg.get("conf_thres", 0.5)),
        )

    def inspect_image(self, image_bytes: bytes) -> dict[str, Any]:
        pixels = _image_to_array(image_bytes)
        gray = pixels.mean(axis=2)
        gy, gx = np.gradient(gray)
        sharpness = float(np.mean(np.sqrt(gx * gx + gy * gy)))
        boxes = self._detect_face_boxes(pixels)
        best = _largest_bbox(boxes)
        h, w = pixels.shape[:2]
        frac = 0.0
        if best is not None:
            frac = ((best[2] - best[0]) * (best[3] - best[1])) / max(1.0, float(w * h))
        return {
            "brightness": float(pixels.mean()),
            "sharpness": sharpness,
            "face_count": len(boxes),
            "face_frac": frac,
            "detector": self.policy.get_session("face_detector") is not None,
        }

    def _face_crop_pixels(self, pixels: np.ndarray) -> np.ndarray:
        best = _largest_bbox(self._detect_face_boxes(pixels))
        if best is not None:
            return _crop_pixels(pixels, best, margin=0.1)
        return pixels

    def _embed_face_session(self, pixels: np.ndarray, session, cfg: dict) -> np.ndarray:
        from openrecognition.inference.onnx_embedding import embed_image_nchw

        crop = self._face_crop_pixels(pixels)
        return embed_image_nchw(
            session,
            crop,
            size=int(cfg.get("input_size", 112)),
            embed_dim=int(cfg["embed_dim"]) if cfg.get("embed_dim") else VISUAL_DIM,
            input_norm=str(cfg.get("input_norm", "insightface")),
        )

    def embed_face(self, image_bytes: bytes) -> np.ndarray:
        pixels = _image_to_array(image_bytes)
        self.face_model_version = self.current_face_model_version()
        self.last_face_fallback_warning = self.policy.fallback_warning("face_embedding")
        session = self.policy.get_session("face_embedding")
        if session is not None:
            return self._embed_face_session(pixels, session, self.pool.onnx_config("face_embedding"))
        return heuristic_visual_embedding(pixels, seed=43)

    def embed_face_configured(self, image_bytes: bytes, *, session, cfg: dict) -> np.ndarray:
        return self._embed_face_session(_image_to_array(image_bytes), session, cfg)

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
            return self._embed_visual_session(pixels, session, self.pool.onnx_config("visual_reid"))
        return heuristic_visual_embedding(pixels, seed=44)

    def _embed_visual_session(self, pixels: np.ndarray, session, cfg: dict) -> np.ndarray:
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

    def embed_visual_configured(
        self,
        image_bytes: bytes,
        crop_bbox: list[float] | None = None,
        *,
        session,
        cfg: dict,
    ) -> np.ndarray:
        pixels = _image_to_array(image_bytes)
        if crop_bbox:
            cropped = _crop_pixels(pixels, crop_bbox)
            if cropped.size:
                pixels = cropped
        return self._embed_visual_session(pixels, session, cfg)

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

    def _version_groups(self, gallery: list[dict], etypes: set[str], active: str) -> dict[str, list[dict]]:
        groups: dict[str, list[dict]] = {}
        for item in gallery:
            if item.get("type") not in etypes:
                continue
            version = str(item.get("model_version") or active)
            groups.setdefault(version, []).append(item)
        return groups

    def _best_match(self, found: list[dict]) -> dict | None:
        accepted = [item for item in found if item.get("entity_id")]
        if accepted:
            return max(accepted, key=lambda item: item["confidence"])
        unknowns = [item for item in found if not item.get("entity_id")]
        if unknowns:
            return max(unknowns, key=lambda item: item["confidence"])
        return None

    def _match_face_versions(
        self,
        image_bytes: bytes,
        gallery: list[dict],
        min_confidence: float,
        return_unknown: bool,
        include_candidates: bool,
        alternates: dict,
        entities: list[dict],
        candidates: list[dict],
    ) -> None:
        active = self.current_face_model_version()
        groups = self._version_groups(gallery, {"person"}, active)
        if not groups:
            self.embed_face(image_bytes)
            return
        found: list[dict] = []
        for version, rows in groups.items():
            if version == active:
                vector = self.embed_face(image_bytes)
            else:
                embedder = alternates.get(version)
                if embedder is None:
                    continue
                vector = embedder(image_bytes)
            found.extend(
                self.match_gallery(
                    vector,
                    rows,
                    {"person"},
                    min_confidence,
                    return_unknown,
                    "face",
                )
            )
            if include_candidates:
                candidates.extend(
                    rank_gallery_matches(
                        vector,
                        rows,
                        {"person"},
                        min_confidence,
                        "face",
                        "image",
                    )
                )
        winner = self._best_match(found)
        if winner:
            entities.append(winner)

    def _match_visual_versions(
        self,
        image_bytes: bytes,
        boxes: list,
        gallery: list[dict],
        include_pets: bool,
        include_objects: bool,
        min_confidence: float,
        return_unknown: bool,
        include_candidates: bool,
        alternates: dict,
        entities: list[dict],
        candidates: list[dict],
        pipelines: list[str],
    ) -> None:
        active = self.current_visual_model_version()
        etypes = set()
        if include_pets:
            etypes.add("pet")
        if include_objects:
            etypes.add("object")
        groups = self._version_groups(gallery, etypes, active)
        if not groups or not boxes:
            return
        usable = {
            version: rows
            for version, rows in groups.items()
            if version == active or version in alternates
        }
        if not usable:
            return
        for bbox in boxes:
            by_type: dict[str, list[dict]] = {"pet": [], "object": []}
            for version, rows in usable.items():
                if version == active:
                    vector = self.embed_visual(image_bytes, bbox)
                else:
                    vector = alternates[version](image_bytes, bbox)
                if include_pets:
                    pipelines.append("pet")
                    by_type["pet"].extend(
                        self.match_gallery(
                            vector,
                            rows,
                            {"pet"},
                            min_confidence,
                            return_unknown,
                            "pet_identity",
                        )
                    )
                    if include_candidates:
                        candidates.extend(
                            rank_gallery_matches(
                                vector,
                                rows,
                                {"pet"},
                                min_confidence,
                                "pet_identity",
                                "image",
                            )
                        )
                if include_objects:
                    pipelines.append("object")
                    by_type["object"].extend(
                        self.match_gallery(
                            vector,
                            rows,
                            {"object"},
                            min_confidence,
                            return_unknown,
                            "object_identity",
                        )
                    )
                    if include_candidates:
                        candidates.extend(
                            rank_gallery_matches(
                                vector,
                                rows,
                                {"object"},
                                min_confidence,
                                "object_identity",
                                "image",
                            )
                        )
            for kind in ("pet", "object"):
                winner = self._best_match(by_type[kind])
                if winner:
                    entities.append(winner)

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
        face_alternates: dict | None = None,
        visual_alternates: dict | None = None,
    ) -> tuple[list[dict], dict | None]:
        entities: list[dict] = []
        pipelines: list[str] = []
        candidates: list[dict] = []
        notes: list[str] = []

        if include_faces:
            pipelines.append("face")
            self._match_face_versions(
                image_bytes,
                gallery,
                min_confidence,
                return_unknown,
                include_candidates,
                face_alternates or {},
                entities,
                candidates,
            )

        pixels = _image_to_array(image_bytes)
        if include_pets or include_objects:
            boxes = detect_animal_bbox(pixels, self.pool, self.policy)
            self._match_visual_versions(
                image_bytes,
                boxes,
                gallery,
                include_pets,
                include_objects,
                min_confidence,
                return_unknown,
                include_candidates,
                visual_alternates or {},
                entities,
                candidates,
                pipelines,
            )

        accepted = {item["recognition_type"] for item in entities if item.get("entity_id")}
        entities[:] = [
            item
            for item in entities
            if item.get("entity_id") or item["recognition_type"] not in accepted
        ]

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
