"""
Tests for POST /api/detect and GET /api/detections.

YOLO inference is monkey-patched so tests run without model weights or GPU.
"""
import io
import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import auth

# Fake detection response that mirrors ml/detection/infer.py output exactly
MOCK_DETECTION_RESULT = {
    "detections": [
        {
            "class": "D40",
            "confidence": 0.81,
            "bbox": [10.0, 20.0, 100.0, 150.0],
            "severity": "high",
        },
        {
            "class": "D00",
            "confidence": 0.63,
            "bbox": [200.0, 300.0, 280.0, 340.0],
            "severity": "medium",
        },
    ],
    "count": 2,
    "_inference_time_ms": 42.5,
}


@pytest.fixture
def mock_yolo():
    """Patch the YOLO runner so no model file is needed."""
    with patch(
        "backend.ml_bridge.yolo_runner.run_detection",
        return_value=MOCK_DETECTION_RESULT,
    ) as m:
        yield m


def _fake_image() -> bytes:
    """1×1 white JPEG in memory — enough to pass file-type checks."""
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
        b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
        b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1e"
        b"C\t\t\x0c\x18\r\x0c\x18!\x1c\x1c!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        b"!!!!!!!!!!!!!!!!!!!!!\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
        b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5"
        b"\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01}\x01"
        b"\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07\"q\x142\x81\x91\xa1\x08"
        b"#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&'()*456789:CDE"
        b"FGHIJSTUVWXYZ cdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93"
        b"\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3"
        b"\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3"
        b"\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1"
        b"\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x08\x01\x01\x00\x00?\x00"
        b"\xfb\xd2\x8a(\x03\xff\xd9"
    )


def test_detect_returns_detections(client, admin_token, mock_yolo):
    image = _fake_image()
    resp = client.post(
        "/api/detect",
        files={"file": ("test.jpg", image, "image/jpeg")},
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["count"] == 2
    assert len(data["detections"]) == 2
    assert "detection_ids" in data
    assert len(data["detection_ids"]) == 2
    assert "image_url" in data


def test_detect_enriches_class_name(client, admin_token, mock_yolo):
    image = _fake_image()
    resp = client.post(
        "/api/detect",
        files={"file": ("test.jpg", image, "image/jpeg")},
        headers=auth(admin_token),
    )
    detections = resp.json()["detections"]
    d40 = next(d for d in detections if d["class_code"] == "D40")
    assert d40["class_name"] == "Pothole"
    assert d40["severity_level"] == "Critical"   # high severity D40 → Critical

    d00 = next(d for d in detections if d["class_code"] == "D00")
    assert d00["class_name"] == "Longitudinal Crack"
    assert d00["severity_level"] == "Medium"


def test_detect_requires_auth(client, mock_yolo):
    image = _fake_image()
    resp = client.post(
        "/api/detect",
        files={"file": ("test.jpg", image, "image/jpeg")},
    )
    assert resp.status_code == 401


def test_detect_rejects_non_image(client, admin_token):
    resp = client.post(
        "/api/detect",
        files={"file": ("doc.pdf", b"%PDF", "application/pdf")},
        headers=auth(admin_token),
    )
    assert resp.status_code == 400


def test_list_detections(client, admin_token, mock_yolo):
    # Run a detection first so there's something to list
    image = _fake_image()
    client.post(
        "/api/detect",
        files={"file": ("test.jpg", image, "image/jpeg")},
        headers=auth(admin_token),
    )
    resp = client.get("/api/detections", headers=auth(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
