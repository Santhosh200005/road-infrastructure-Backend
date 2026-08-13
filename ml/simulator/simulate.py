import xgboost as xgb
import numpy as np
import json
import os

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "xgb_simulator.json"
)

FEATURE_ORDER = ["current_severity", "daily_vehicles", "rainfall_mm", "avg_temp",
                 "road_age_years", "last_repair_days", "material_type"]

def load_model():
    model = xgb.XGBRegressor()
    model.load_model(MODEL_PATH)
    return model


def forecast_severity(inputs, days=30):
    """
    inputs: dict with keys matching FEATURE_ORDER
      e.g. {
        "current_severity": 3.0,
        "daily_vehicles": 8000,
        "rainfall_mm": 20,
        "avg_temp": 15,
        "road_age_years": 10,
        "last_repair_days": 500,
        "material_type": 1
      }
    days: forecast horizon (model was trained on 30-day horizon specifically)
    """
    model = load_model()

    # arrange features in correct order
    feature_values = [[inputs[col] for col in FEATURE_ORDER]]
    predicted_severity = model.predict(feature_values)[0]

    # Note: model is trained specifically for a 30-day horizon.
    # For other day counts, we scale linearly as an approximation.
    if days != 30:
        delta = predicted_severity - inputs["current_severity"]
        scaled_delta = delta * (days / 30)
        predicted_severity = inputs["current_severity"] + scaled_delta

    return {
        "current_severity": inputs["current_severity"],
        "forecast_days": days,
        "predicted_severity": round(float(predicted_severity), 4)
    }


if __name__ == "__main__":
    sample_input = {
        "current_severity": 3.0,
        "daily_vehicles": 8000,
        "rainfall_mm": 20,
        "avg_temp": 15,
        "road_age_years": 10,
        "last_repair_days": 500,
        "material_type": 1
    }

    result = forecast_severity(sample_input, days=30)
    print(json.dumps(result, indent=2))