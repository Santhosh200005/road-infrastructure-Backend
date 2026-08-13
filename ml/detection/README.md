# Road Defect Detection Model

YOLOv8m-based object detection model trained to identify road surface defects from images.

## Classes Detected

| Class | Description |
|-------|--------------|
| D00 | Longitudinal crack |
| D10 | Transverse crack |
| D20 | Alligator crack |
| D40 | Pothole |

## Model Performance (Test Set)

| Class | mAP50 |
|-------|-------|
| Overall | 58.6% |
| D00 | 59.0% |
| D10 | 60.3% |
| D20 | 67.4% |
| D40 | 47.7% |

**Known limitation:** D40 (pothole) detection is weaker than other classes due to fewer training examples (6,544 annotations vs. 26,016 for D00). Consider this when interpreting pothole predictions — confidence thresholds may need adjustment, or the model may benefit from additional pothole-focused training data in the future.

## Setup

1. Create and activate a Python environment (Python 3.11 recommended):
```
   conda create -n road-ai python=3.11 -y
   conda activate road-ai
```

2. Install dependencies:
```
   pip install ultralytics torch torchvision albumentations
   pip install xgboost scikit-learn pandas numpy matplotlib seaborn
   pip install openai requests python-dotenv
```

3. Download the trained model weights (`best.pt`) from Google Drive:
   **[Download best.pt](https://drive.google.com/file/d/1_NC3TSy-Bs6Jj2lsASF1GsAKQv7gwaHD/view?usp=drive_link)**

   Place the downloaded `best.pt` file in:
```
   ml/detection/runs/rdd2022/yolov8m_rdd-3/weights/best.pt
```

## Usage

### Running inference on a single image

```
cd ml/detection
python infer.py --image path/to/your/image.jpg
```

### Using `detect_defects()` in your own code

```python
from infer import detect_defects

result = detect_defects("path/to/image.jpg")
print(result)
```

### Output format

```json
{
  "detections": [
    {
      "class": "D00",
      "confidence": 0.7406,
      "bbox": [22.4, 524.86, 66.08, 619.9],
      "severity": "medium"
    }
  ],
  "count": 1
}
```

- `class`: one of D00, D10, D20, D40
- `confidence`: model confidence score (0-1)
- `bbox`: bounding box coordinates `[xmin, ymin, xmax, ymax]` in pixels
- `severity`: derived from confidence — `low` (<0.5), `medium` (0.5-0.75), `high` (≥0.75)
- `count`: total number of detections in the image

## Files

| File | Purpose |
|------|---------|
| `train.py` | Trains YOLOv8m on the RDD2022 dataset |
| `resume_train.py` | Resumes training from a saved checkpoint |
| `export.py` | Exports trained model to ONNX format |
| `infer.py` | Inference interface — `detect_defects(image_path)` |
| `convert_annotations.py` | Converts XML annotations to YOLO format and splits dataset |
| `results/` | Confusion matrix and evaluation outputs |

## Dataset

Trained on [RDD2022](https://github.com/sekilab/RoadDamageDetector), using all 6 available countries (Japan, India, Czech Republic, Norway, United States, China). Dataset itself is not included in this repo (see `.gitignore`) due to size — see `convert_annotations.py` for how to regenerate the processed dataset from the raw source.