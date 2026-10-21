"""SCRFD face detection (ONNX)."""

from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image

from openrecognition.inference.onnx_helpers import run_session


def distance2bbox(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    x1 = points[:, 0] - distance[:, 0]
    y1 = points[:, 1] - distance[:, 1]
    x2 = points[:, 0] + distance[:, 2]
    y2 = points[:, 1] + distance[:, 3]
    return np.stack([x1, y1, x2, y2], axis=-1)


def _nms(dets: np.ndarray, iou_thres: float) -> list[int]:
    x1, y1, x2, y2, scores = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3], dets[:, 4]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[np.where(ovr <= iou_thres)[0] + 1]
    return keep


def _prepare_blob(
    rgb: np.ndarray,
    input_size: tuple[int, int],
    *,
    mean: float = 127.5,
    std: float = 128.0,
) -> tuple[np.ndarray, float]:
    width, height = input_size
    im_h, im_w = rgb.shape[:2]
    im_ratio = float(im_h) / im_w
    model_ratio = height / width
    if im_ratio > model_ratio:
        new_h = height
        new_w = int(new_h / im_ratio)
    else:
        new_w = width
        new_h = int(new_w * im_ratio)

    det_scale = float(new_h) / im_h
    resized = np.array(
        Image.fromarray(rgb).resize((new_w, new_h), Image.Resampling.BILINEAR),
        dtype=np.uint8,
    )
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[:new_h, :new_w] = resized

    blob = canvas.astype(np.float32)
    blob = (blob - mean) / std
    blob = blob.transpose(2, 0, 1)[np.newaxis, ...]
    return blob, det_scale


class ScrfdDetector:
    def __init__(
        self,
        session: Any,
        *,
        input_size: tuple[int, int] = (640, 640),
        conf_thres: float = 0.5,
        iou_thres: float = 0.4,
    ):
        self.session = session
        self.input_size = input_size
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres
        self.fmc = 3
        self._feat_stride_fpn = (8, 16, 32)
        self._num_anchors = 2
        self._center_cache: dict[tuple[int, int, int], np.ndarray] = {}
        self._input_name = session.get_inputs()[0].name

    def _forward(self, blob: np.ndarray) -> tuple[list[np.ndarray], list[np.ndarray]]:
        outputs = run_session(self.session, {self._input_name: blob})
        input_height = blob.shape[2]
        input_width = blob.shape[3]
        scores_list: list[np.ndarray] = []
        bboxes_list: list[np.ndarray] = []
        fmc = self.fmc
        for idx, stride in enumerate(self._feat_stride_fpn):
            scores = outputs[idx]
            bbox_preds = outputs[idx + fmc] * stride
            height = input_height // stride
            width = input_width // stride
            key = (height, width, stride)
            anchor_centers = self._center_cache.get(key)
            if anchor_centers is None:
                anchor_centers = np.stack(np.mgrid[:height, :width][::-1], axis=-1).astype(
                    np.float32
                )
                anchor_centers = (anchor_centers * stride).reshape((-1, 2))
                if self._num_anchors > 1:
                    anchor_centers = np.stack([anchor_centers] * self._num_anchors, axis=1).reshape(
                        (-1, 2)
                    )
                if len(self._center_cache) < 100:
                    self._center_cache[key] = anchor_centers

            pos_inds = np.where(scores >= self.conf_thres)[0]
            bboxes = distance2bbox(anchor_centers, bbox_preds)
            scores_list.append(scores[pos_inds])
            bboxes_list.append(bboxes[pos_inds])
        return scores_list, bboxes_list

    def detect(
        self,
        rgb: np.ndarray,
        *,
        max_num: int = 0,
    ) -> list[tuple[list[float], float]]:
        blob, det_scale = _prepare_blob(rgb, self.input_size)
        scores_list, bboxes_list = self._forward(blob)
        if not scores_list:
            return []
        scores = np.vstack(scores_list)
        bboxes = np.vstack(bboxes_list) / det_scale
        order = scores.ravel().argsort()[::-1]
        pre_det = np.hstack((bboxes, scores)).astype(np.float32, copy=False)[order]
        keep = _nms(pre_det, self.iou_thres)
        det = pre_det[keep]
        if 0 < max_num < det.shape[0]:
            areas = (det[:, 2] - det[:, 0]) * (det[:, 3] - det[:, 1])
            det = det[np.argsort(areas)[::-1][:max_num]]
        return [
            ([float(row[0]), float(row[1]), float(row[2]), float(row[3])], float(row[4]))
            for row in det
        ]


def detect_faces_scrfd(
    session: Any,
    pixels: np.ndarray,
    *,
    input_size: tuple[int, int] = (640, 640),
    conf_thres: float = 0.5,
) -> list[list[float]]:
    """Detect face boxes from float RGB pixels in [0,1]."""
    rgb = (np.clip(pixels, 0, 1) * 255).astype(np.uint8)
    det = ScrfdDetector(session, input_size=input_size, conf_thres=conf_thres)
    return [bbox for bbox, _ in det.detect(rgb)]
