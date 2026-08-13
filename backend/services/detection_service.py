"""
Detection service: orchestrates image save -> ML bridge -> derived fields -> DB persist.
This is where the requested "damage_type"/friendliness lives, layered on top of the
real ML output rather than replacing it.
"""
import os
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.ml_bridge import yolo_runner
from backend.database import crud

UPLOAD_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Human-readable labels for the raw class codes — from Person A's README table.
CLASS_NAMES = {
    "D00": "Longitudinal Crack",
    "D10": "Transverse Crack",
    "D20": "Alligator Crack",
    "D40": "Pothole",
}

# Maps the ML's 3-level severity ("low"/"medium"/"high") to the frontend's
# 4-bucket marker scheme (Critical/High/Medium/Low). Per Person A's note in the
# frontend guide: "high" severity D40 (pothole) detections are treated as
# "Critical" since the model doesn't emit a 4th level natively.
def _severity_level(class_code: str, severity: str) -> str:
    if severity == "high" and class_code == "D40":
        return "Critical"
    return {"high": "High", "medium": "Medium", "low": "Low"}.get(severity, "Low")


def save_upload(file_bytes: bytes, original_filename: str) -> str:
    ext = os.path.splitext(original_filename)[1] or ".jpg"
    filename = f"{uuid.uuid4()}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        f.write(file_bytes)
    return path


def run_and_persist_detection(db: Session, image_path: str, road_id: Optional[str],
                               user_id: Optional[str]) -> dict:
    """
    Calls the YOLO wrapper, enriches each detection with class_name +
    severity_level, saves each as a Detection row, and returns everything the
    /api/detect route needs to build its response.
    """
    raw = yolo_runner.run_detection(image_path)  # {"detections": [...], "count": N, "_inference_time_ms": ..}

    enriched = []
    detection_ids = []
    for det in raw["detections"]:
        class_code = det["class"]
        class_name = CLASS_NAMES.get(class_code, class_code)
        severity_level = _severity_level(class_code, det["severity"])

        record = crud.create_detection(
            db,
            road_id=road_id,
            user_id=user_id,
            image_path=image_path,
            class_code=class_code,
            confidence=det["confidence"],
            bbox=det["bbox"],
            severity=det["severity"],
            class_name=class_name,
            severity_level=severity_level,
        )
        detection_ids.append(record.id)

        enriched.append({
            "class_code": class_code,
            "class_name": class_name,
            "confidence": det["confidence"],
            "bbox": det["bbox"],
            "severity": det["severity"],
            "severity_level": severity_level,
        })

    return {
        "detections": enriched,
        "count": raw["count"],
        "detection_ids": detection_ids,
        "inference_time_ms": raw.get("_inference_time_ms"),
    }
