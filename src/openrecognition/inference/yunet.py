"""YuNet face detection (OpenCV Zoo ONNX)."""

from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image

from openrecognition.inference.onnx_helpers import run_session
from openrecognition.inference.scrfd import _nms

_STRIDES = (8, 16, 32)


def decode_yunet_level(
    cls: np.ndarray,
    obj: np.ndarray,
    bbox: np.ndarray,
    *,
    stride: int,
    cols: int,
    conf_thres: float,
) -> list[tuple[float, float, float, float, float]]:
    """One feature stride → boxes as x1, y1, x2, y2, score in network pixels."""
    cls_v = np.clip(np.asarray(cls, dtype=np.float32).reshape(-1), 0.0, 1.0)
    obj_v = np.clip(np.asarray(obj, dtype=np.float32).reshape(-1), 0.0, 1.0)
    box = np.asarray(bbox, dtype=np.float32).reshape(-1, 4)
    score = np.sqrt(cls_v * obj_v)
    found: list[tuple[float, float, float, float, float]] = []
    for idx in np.where(score >= conf_thres)[0]:
        i = int(idx)
        row, col = divmod(i, cols)
        cx = (col + float(box[i, 0])) * stride
        cy = (row + float(box[i, 1])) * stride
        w = float(np.exp(box[i, 2])) * stride
        h = float(np.exp(box[i, 3])) * stride
        found.append((cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0, float(score[i])))
    return found


def _letterbox_bgr(rgb: np.ndarray, input_size: tuple[int, int]) -> tuple[np.ndarray, float]:
    width, height = input_size
    im_h, im_w = rgb.shape[:2]
    im_ratio = float(im_h) / max(im_w, 1)
    model_ratio = height / width
    if im_ratio > model_ratio:
        new_h = height
        new_w = max(1, int(new_h / im_ratio))
    else:
        new_w = width
        new_h = max(1, int(new_w * im_ratio))
    det_scale = float(new_h) / max(im_h, 1)
    resized = np.array(
        Image.fromarray(rgb).resize((new_w, new_h), Image.Resampling.BILINEAR),
        dtype=np.uint8,
    )
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[:new_h, :new_w] = resized
    bgr = canvas[:, :, ::-1]
    blob = np.transpose(bgr.astype(np.float32), (2, 0, 1))[np.newaxis, ...]
    return blob, det_scale


def detect_faces_yunet(
    session: Any,
    pixels: np.ndarray,
    *,
    input_size: tuple[int, int] = (640, 640),
    conf_thres: float = 0.6,
    iou_thres: float = 0.3,
) -> list[list[float]]:
    """Detect face boxes from float RGB pixels in [0, 1]."""
    rgb = (np.clip(pixels, 0, 1) * 255).astype(np.uint8)
    blob, det_scale = _letterbox_bgr(rgb, input_size)
    outputs = run_session(session, {session.get_inputs()[0].name: blob})
    by_name = {out.name: np.asarray(value) for out, value in zip(session.get_outputs(), outputs)}
    width, height = input_size
    raw: list[tuple[float, float, float, float, float]] = []
    for stride in _STRIDES:
        raw.extend(
            decode_yunet_level(
                by_name[f"cls_{stride}"],
                by_name[f"obj_{stride}"],
                by_name[f"bbox_{stride}"],
                stride=stride,
                cols=width // stride,
                conf_thres=conf_thres,
            )
        )
    if not raw:
        return []
    det = np.asarray(raw, dtype=np.float32)
    det[:, :4] /= det_scale
    order = det[:, 4].argsort()[::-1]
    det = det[order]
    keep = _nms(det, iou_thres)
    return [[float(v) for v in det[i, :4]] for i in keep]
