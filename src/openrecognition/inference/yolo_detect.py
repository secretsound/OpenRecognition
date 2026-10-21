"""YOLO ONNX object detection (Ultralytics export)."""

from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image

from openrecognition.inference.onnx_helpers import run_session

# COCO class ids useful for pets / common objects in home scenes.
PET_CLASS_IDS = frozenset({14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24})
OBJECT_CLASS_IDS = frozenset(
    {
        39,
        40,
        41,
        42,
        43,
        44,
        45,
        46,
        47,
        48,
        49,
        50,
        51,
        52,
        53,
        54,
        55,
        56,
        57,
        58,
        59,
        60,
        61,
        62,
        63,
        64,
        65,
        66,
        67,
        68,
        69,
        70,
        71,
        72,
        73,
        74,
        75,
        76,
        77,
        78,
        79,
    }
)


def _nms_xyxy(boxes: np.ndarray, scores: np.ndarray, iou_thres: float) -> list[int]:
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        xx1 = np.maximum(boxes[i, 0], boxes[rest, 0])
        yy1 = np.maximum(boxes[i, 1], boxes[rest, 1])
        xx2 = np.minimum(boxes[i, 2], boxes[rest, 2])
        yy2 = np.minimum(boxes[i, 3], boxes[rest, 3])
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
        area_rest = (boxes[rest, 2] - boxes[rest, 0]) * (boxes[rest, 3] - boxes[rest, 1])
        iou = inter / (area_i + area_rest - inter + 1e-9)
        order = rest[np.where(iou <= iou_thres)[0]]
    return keep


def _xywh_to_xyxy(cx: np.ndarray, cy: np.ndarray, w: np.ndarray, h: np.ndarray) -> np.ndarray:
    return np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=-1)


def detect_yolo(
    session: Any,
    pixels: np.ndarray,
    *,
    input_size: int = 640,
    conf_thres: float = 0.25,
    iou_thres: float = 0.45,
    class_filter: frozenset[int] | None = None,
    max_det: int = 20,
) -> list[tuple[list[float], float, int]]:
    """Run YOLO on RGB float pixels [0,1]. Returns (bbox xyxy, score, class_id)."""
    h, w = pixels.shape[:2]
    rgb = (np.clip(pixels, 0, 1) * 255).astype(np.uint8)
    scale = min(input_size / h, input_size / w)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = np.array(
        Image.fromarray(rgb).resize((new_w, new_h), Image.Resampling.BILINEAR),
        dtype=np.uint8,
    )
    canvas = np.full((input_size, input_size, 3), 114, dtype=np.uint8)
    canvas[:new_h, :new_w] = resized
    blob = canvas.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32) / 255.0

    inp_name = session.get_inputs()[0].name
    pred = run_session(session, {inp_name: blob})[0][0]  # (84, anchors)
    if pred.shape[0] < pred.shape[1]:
        pred = pred.T  # (anchors, 84)

    boxes_xywh = pred[:, :4]
    scores_all = pred[:, 4:]
    class_ids = scores_all.argmax(axis=1)
    conf = scores_all[np.arange(scores_all.shape[0]), class_ids]

    mask = conf >= conf_thres
    if class_filter is not None:
        mask &= np.isin(class_ids, list(class_filter))
    if not np.any(mask):
        return []

    boxes_xywh = boxes_xywh[mask]
    conf = conf[mask]
    class_ids = class_ids[mask]

    boxes_xywh[:, 0] /= scale
    boxes_xywh[:, 1] /= scale
    boxes_xywh[:, 2] /= scale
    boxes_xywh[:, 3] /= scale

    xyxy = _xywh_to_xyxy(boxes_xywh[:, 0], boxes_xywh[:, 1], boxes_xywh[:, 2], boxes_xywh[:, 3])
    xyxy[:, 0] = np.clip(xyxy[:, 0], 0, w)
    xyxy[:, 1] = np.clip(xyxy[:, 1], 0, h)
    xyxy[:, 2] = np.clip(xyxy[:, 2], 0, w)
    xyxy[:, 3] = np.clip(xyxy[:, 3], 0, h)

    keep = _nms_xyxy(xyxy, conf, iou_thres)[:max_det]
    out: list[tuple[list[float], float, int]] = []
    for i in keep:
        row = xyxy[i]
        out.append(
            (
                [float(row[0]), float(row[1]), float(row[2]), float(row[3])],
                float(conf[i]),
                int(class_ids[i]),
            )
        )
    return out


def detect_animal_bboxes(
    session: Any,
    pixels: np.ndarray,
    *,
    pets_only: bool = True,
    input_size: int = 640,
    conf_thres: float = 0.25,
) -> list[list[float]]:
    class_filter = PET_CLASS_IDS if pets_only else PET_CLASS_IDS | OBJECT_CLASS_IDS
    hits = detect_yolo(
        session,
        pixels,
        class_filter=class_filter,
        input_size=input_size,
        conf_thres=conf_thres,
    )
    return [bbox for bbox, _, _ in hits]
