"""
Thin wrapper around ml/simulator/simulate.py (XGBoost model) and, optionally,
ml/simulator/weather.py.

Never reimplements simulation math — calls Person A's forecast_severity()
exactly as written. FEATURE_ORDER, the 7 required inputs, and the 30-day-native
/ linear-approximation-beyond-30-days behavior all belong to that function and
are left untouched.
"""
import os
import sys
import time
import logging

logger = logging.getLogger("ml_bridge.simulator_runner")

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ML_SIMULATOR_DIR = os.path.normpath(os.path.join(_THIS_DIR, "..", "..", "ml", "simulator"))

if _ML_SIMULATOR_DIR not in sys.path:
    sys.path.insert(0, _ML_SIMULATOR_DIR)

REQUIRED_FEATURES = [
    "current_severity", "daily_vehicles", "rainfall_mm", "avg_temp",
    "road_age_years", "last_repair_days", "material_type",
]

# Sensible defaults used ONLY when a road/request is missing a feature the
# model requires. These are not predictions — just fallback inputs so the
# endpoint doesn't hard-fail on incomplete road records. Documented here so
# it's obvious to whoever wires up the frontend.
DEFAULTS = {
    "current_severity": 3.0,
    "daily_vehicles": 5000,
    "rainfall_mm": 15.0,
    "avg_temp": 20.0,
    "road_age_years": 10.0,
    "last_repair_days": 365,
    "material_type": 1,
}


def _load_forecast_severity():
    try:
        from simulate import forecast_severity  # Person A's actual function, untouched
        return forecast_severity
    except ImportError as e:
        raise RuntimeError(
            "Could not import forecast_severity() from ml/simulator/simulate.py. "
            f"Make sure xgboost is installed and xgb_simulator.json is present. Original error: {e}"
        )


def build_inputs(overrides: dict) -> dict:
    """Merge caller-provided values over the defaults, keeping only the 7
    keys forecast_severity() actually expects (FEATURE_ORDER in simulate.py)."""
    inputs = dict(DEFAULTS)
    for key in REQUIRED_FEATURES:
        if overrides.get(key) is not None:
            inputs[key] = overrides[key]
    return inputs


def run_simulation(inputs: dict, days: int = 30) -> dict:
    """
    Calls Person A's forecast_severity(inputs, days) unmodified.

    Returns the RAW ml output, unchanged:
        {"current_severity": 3.0, "forecast_days": 30, "predicted_severity": 3.7265}
    """
    forecast_severity = _load_forecast_severity()

    missing = [k for k in REQUIRED_FEATURES if k not in inputs]
    if missing:
        raise RuntimeError(f"Missing required simulator inputs: {missing}")

    start = time.perf_counter()
    try:
        result = forecast_severity(inputs, days=days)
    except Exception as e:
        logger.exception("Simulation failed")
        raise RuntimeError(f"Simulation failed: {e}")
    elapsed_ms = (time.perf_counter() - start) * 1000

    logger.info("Simulation (days=%d) completed in %.1fms -> predicted_severity=%.4f",
                days, elapsed_ms, result["predicted_severity"])

    result["_inference_time_ms"] = round(elapsed_ms, 1)
    return result


def run_simulation_series(inputs: dict, day_points=None) -> list:
    """
    Builds the 0-180 day series the frontend's Simulator page LineChart needs
    (Step 6 of the frontend guide) by calling forecast_severity repeatedly,
    since the ML function only returns a single point per call.

    Per Person A's note: the model is 30-day-native: predictions further from
    day 30 are a linear approximation (handled inside forecast_severity itself),
    so the curve straightens out the further from day 30 you get. That's
    expected behavior of the underlying function, not something this wrapper
    changes.
    """
    if day_points is None:
        day_points = [0, 10, 20, 30, 45, 60, 90, 120, 150, 180]

    forecast_severity = _load_forecast_severity()
    missing = [k for k in REQUIRED_FEATURES if k not in inputs]
    if missing:
        raise RuntimeError(f"Missing required simulator inputs: {missing}")

    series = []
    for d in day_points:
        try:
            point = forecast_severity(inputs, days=d) if d > 0 else {
                "current_severity": inputs["current_severity"],
                "forecast_days": 0,
                "predicted_severity": inputs["current_severity"],
            }
        except Exception as e:
            logger.exception("Simulation series point failed at days=%d", d)
            raise RuntimeError(f"Simulation failed at days={d}: {e}")
        series.append(point)
    return series
