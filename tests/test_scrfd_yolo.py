"""Unit tests for SCRFD / YOLO helpers (optional local ONNX files)."""

from pathlib import Path

import numpy as np
import pytest

from openrecognition.inference.scrfd import detect_faces_scrfd
from openrecognition.inference.yolo_detect import detect_yolo

TMP_DET = Path("/tmp/det_500m.onnx")
TMP_YOLO = Path("/tmp/yolo11n.onnx")


@pytest.mark.skipif(not TMP_DET.exists(), reason="det_500m.onnx not in /tmp")
def test_scrfd_blank_image_no_crash():
    import onnxruntime as ort

    session = ort.InferenceSession(str(TMP_DET), providers=["CPUExecutionProvider"])
    pixels = np.zeros((240, 320, 3), dtype=np.float32)
    assert detect_faces_scrfd(session, pixels) == []


@pytest.mark.skipif(not TMP_YOLO.exists(), reason="yolo11n.onnx not in /tmp")
def test_yolo_blank_image_no_crash():
    import onnxruntime as ort

    session = ort.InferenceSession(str(TMP_YOLO), providers=["CPUExecutionProvider"])
    pixels = np.zeros((240, 320, 3), dtype=np.float32)
    hits = detect_yolo(session, pixels, class_filter=frozenset({15, 16}))
    assert isinstance(hits, list)
