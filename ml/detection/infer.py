import torch
from ultralytics import YOLO
import json
import sys
import os


MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "runs",
    "rdd2022",
    "yolov8m_rdd-3",
    "weights",
    "best.pt"
)


CLASS_NAMES = {
    0: "D00",
    1: "D10",
    2: "D20",
    3: "D40"
}


# Simple severity mapping based on confidence
def estimate_severity(confidence):
    if confidence >= 0.75:
        return "high"
    elif confidence >= 0.5:
        return "medium"
    else:
        return "low"


def load_yolo_model():
    """
    Load the trusted YOLO checkpoint with weights_only=False.

    The best.pt file is a trusted Ultralytics checkpoint.
    PyTorch's newer safe-loading behavior can reject the
    DetectionModel class contained in older YOLO checkpoints.
    """

    original_torch_load = torch.load

    def trusted_torch_load(*args, **kwargs):
        kwargs["weights_only"] = False
        return original_torch_load(*args, **kwargs)

    torch.load = trusted_torch_load

    try:
        model = YOLO(MODEL_PATH)
        return model
    finally:
        # Restore normal torch.load after the checkpoint is loaded
        torch.load = original_torch_load


def detect_defects(image_path):
    # Check model exists
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"YOLO model not found at: {MODEL_PATH}"
        )

    # Check image exists
    if not os.path.exists(image_path):
        raise FileNotFoundError(
            f"Image not found at: {image_path}"
        )

    # Load YOLO model
    model = load_yolo_model()

    # Run prediction
    results = model.predict(
        source=image_path,
        verbose=False
    )

    detections = []

    for result in results:
        boxes = result.boxes

        for box in boxes:
            cls_id = int(box.cls[0])
            confidence = float(box.conf[0])

            xyxy = box.xyxy[0].tolist()

            detections.append({
                "class": CLASS_NAMES.get(
                    cls_id,
                    "unknown"
                ),
                "confidence": round(
                    confidence,
                    4
                ),
                "bbox": [
                    round(coord, 2)
                    for coord in xyxy
                ],
                "severity": estimate_severity(
                    confidence
                )
            })

    output = {
        "detections": detections,
        "count": len(detections)
    }

    return output


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print(
            "Usage: python infer.py --image path/to/image.jpg"
        )
        sys.exit(1)

    # Simple argument parsing for --image
    if "--image" in sys.argv:

        idx = sys.argv.index("--image")

        if idx + 1 >= len(sys.argv):
            print("Error: --image requires a file path")
            sys.exit(1)

        image_path = sys.argv[idx + 1]

    else:
        image_path = sys.argv[1]

    try:
        result = detect_defects(image_path)

        print(
            json.dumps(
                result,
                indent=2
            )
        )

    except Exception as e:
        print(
            json.dumps(
                {
                    "error": str(e)
                },
                indent=2
            )
        )
        sys.exit(1)