"""
Simulator service: orchestrates ML bridge -> derived fields -> DB persist.

IMPORTANT — read before trusting these numbers in a demo:
ml/simulator/simulate.py's forecast_severity() only returns
{current_severity, forecast_days, predicted_severity}. It does NOT compute a
"condition" label, "remaining_life", or "failure_probability" — those fields
were requested in the integration spec but don't exist anywhere in Person A's
actual code. Rather than fabricate them silently, they're computed HERE, in
one place, using explicit, documented heuristics on top of predicted_severity:

  - severity is treated as a 0-10 scale (consistent with the sample values in
    Person A's report, e.g. 2.5-3.7 range for "moderate" roads).
  - condition: bucketed thresholds (Good <3, Fair 3-5, Poor 5-7, Critical >7).
  - remaining_life_years: (10 - predicted_severity) / estimated_annual_rate,
    where the annual rate is derived from ml/simulator/degradation_model.py's
    calculate_daily_delta() (the same formula-based degradation model Person A
    already built) x 365, clipped to [0, 30] years.
  - failure_probability: a logistic curve centered at severity=7 (the
    "Critical" threshold), so it climbs sharply as predicted_severity
    approaches/exceeds 7. This is a heuristic, not a calibrated probability.

If you later get real failure/remaining-life ground truth data, retrain a
proper model for these instead of relying on this heuristic layer.
"""
import math
from typing import Optional

from sqlalchemy.orm import Session

from backend.ml_bridge import simulator_runner
from backend.database import crud

SEVERITY_CEILING = 10.0


def _annual_degradation_rate(inputs: dict) -> float:
    """Reuses Person A's existing formula-based degradation_model.py
    (calculate_daily_delta) — untouched — purely to estimate an annual rate
    for the remaining-life heuristic. Falls back to a flat default if that
    module isn't importable for some reason."""
    try:
        import sys, os
        sim_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "ml", "simulator"))
        if sim_dir not in sys.path:
            sys.path.insert(0, sim_dir)
        from degradation_model import calculate_daily_delta

        daily_delta = calculate_daily_delta(
            daily_vehicles=inputs.get("daily_vehicles", 5000),
            rainfall_mm=inputs.get("rainfall_mm", 15),
            freeze_thaw_cycles=inputs.get("freeze_thaw_cycles", 0.1),
            road_age_years=inputs.get("road_age_years", 10),
        )
        return max(daily_delta * 365, 0.01)
    except Exception:
        return 0.3  # fallback: ~0.3 severity points/year


def _condition_label(predicted_severity: float) -> str:
    if predicted_severity < 3:
        return "Good"
    elif predicted_severity < 5:
        return "Fair"
    elif predicted_severity < 7:
        return "Poor"
    return "Critical"


def _failure_probability(predicted_severity: float) -> float:
    # logistic curve centered at 7, steepness tuned so it's ~0.5 at severity=7
    return round(1 / (1 + math.exp(-1.2 * (predicted_severity - 7))), 4)


def _remaining_life_years(predicted_severity: float, inputs: dict) -> float:
    rate = _annual_degradation_rate(inputs)
    remaining = (SEVERITY_CEILING - predicted_severity) / rate
    return round(max(0.0, min(remaining, 30.0)), 2)


def run_and_persist_simulation(db: Session, raw_inputs: dict, days: int,
                                road_id: Optional[str], user_id: Optional[str]) -> dict:
    inputs = simulator_runner.build_inputs(raw_inputs)
    result = simulator_runner.run_simulation(inputs, days=days)  # raw ML output

    predicted_severity = result["predicted_severity"]
    condition = _condition_label(predicted_severity)
    remaining_life = _remaining_life_years(predicted_severity, inputs)
    failure_prob = _failure_probability(predicted_severity)

    record = crud.create_simulation_result(
        db,
        road_id=road_id,
        user_id=user_id,
        inputs=inputs,
        current_severity=result["current_severity"],
        forecast_days=result["forecast_days"],
        predicted_severity=predicted_severity,
        condition=condition,
        remaining_life_years=remaining_life,
        failure_probability=failure_prob,
    )

    return {
        "current_severity": result["current_severity"],
        "forecast_days": result["forecast_days"],
        "predicted_severity": predicted_severity,
        "condition": condition,
        "remaining_life_years": remaining_life,
        "failure_probability": failure_prob,
        "simulation_id": record.id,
    }


def run_series(db: Session, raw_inputs: dict, road_id: Optional[str], user_id: Optional[str]) -> list:
    """Builds the 0-180 day chart series, persisting each point the same way
    a single /api/simulate call would."""
    inputs = simulator_runner.build_inputs(raw_inputs)
    raw_points = simulator_runner.run_simulation_series(inputs)

    out = []
    for raw in raw_points:
        predicted_severity = raw["predicted_severity"]
        condition = _condition_label(predicted_severity)
        remaining_life = _remaining_life_years(predicted_severity, inputs)
        failure_prob = _failure_probability(predicted_severity)

        record = crud.create_simulation_result(
            db,
            road_id=road_id,
            user_id=user_id,
            inputs=inputs,
            current_severity=raw["current_severity"],
            forecast_days=raw["forecast_days"],
            predicted_severity=predicted_severity,
            condition=condition,
            remaining_life_years=remaining_life,
            failure_probability=failure_prob,
        )
        out.append({
            "current_severity": raw["current_severity"],
            "forecast_days": raw["forecast_days"],
            "predicted_severity": predicted_severity,
            "condition": condition,
            "remaining_life_years": remaining_life,
            "failure_probability": failure_prob,
            "simulation_id": record.id,
        })
    return out
