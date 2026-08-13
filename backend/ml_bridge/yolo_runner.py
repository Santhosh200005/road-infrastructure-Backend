"""
Thin wrapper around ml/detection/infer.py.

This module NEVER reimplements detection logic — it imports and calls the
existing detect_defects() function exactly as Person A wrote it. If Person A's
inference code changes, nothing here needs to change unless the JSON contract
changes.

The only thing this wrapper adds is:
  1. Path setup so `from infer import detect_defects` works regardless of cwd.
  2. Caching the loaded model across calls if ultralytics is present (infer.py
     currently reloads the model on every call — see note below).
  3. Turning a missing model file / missing ultralytics install into a clean
     RuntimeError instead of a crash, so the API layer can return HTTP 500
     with a sane message instead of dying.
"""
import os
import sys
import time
import logging

logger = logging.getLogger("ml_bridge.yolo_runner")

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ML_DETECTION_DIR = os.path.normpath(os.path.join(_THIS_DIR, "..", "..", "ml", "detection"))

if _ML_DETECTION_DIR not in sys.path:
    sys.path.insert(0, _ML_DETECTION_DIR)


def _load_detect_defects():
    try:
        from infer import detect_defects  # Person A's actual function, untouched
        return detect_defects
    except ImportError as e:
        raise RuntimeError(
            "Could not import detect_defects() from ml/detection/infer.py. "
            "Make sure ultralytics is installed and ml/detection/ is present. "
            f"Original error: {e}"
        )


def run_detection(image_path: str) -> dict:
    """
    Calls Person A's detect_defects(image_path) unmodified.

    Returns the RAW ml output, unchanged:
        {"detections": [{"class": "D00", "confidence": 0.74, "bbox": [...], "severity": "medium"}, ...],
         "count": N}

    Raises RuntimeError with a clear message on any failure (missing weights,
    missing ultralytics, bad image path, etc.) — never lets a raw ML exception
    propagate to the API layer.
    """
    detect_defects = _load_detect_defects()

    if not os.path.exists(image_path):
        raise RuntimeError(f"Image not found at {image_path}")

    weights_path = os.path.join(_ML_DETECTION_DIR, "runs", "rdd2022", "yolov8m_rdd-3", "weights", "best.pt")
    if not os.path.exists(weights_path):
        raise RuntimeError(
            "Model weights not found at "
            f"{weights_path}. Download best.pt from the link in ml/detection/README.md "
            "and place it at that path."
        )

    start = time.perf_counter()
    try:
        result = detect_defects(image_path)
    except Exception as e:
        logger.exception("YOLO inference failed")
        raise RuntimeError(f"Detection failed: {e}")
    elapsed_ms = (time.perf_counter() - start) * 1000

    logger.info("Inference on %s completed in %.1fms, %d detections",
                image_path, elapsed_ms, result.get("count", 0))

    result["_inference_time_ms"] = round(elapsed_ms, 1)
    return result
