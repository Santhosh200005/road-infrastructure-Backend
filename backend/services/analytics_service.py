"""
Analytics service: aggregation queries over Detections / Repairs / SimulationResults.
No ML calls here — pure SQL/Python aggregation for dashboards/charts.

New in this version:
  - budget_analytics() — feeds GET /api/analytics/budget, matches the frontend's
    Analytics.jsx mock shape exactly:
      { monthly: [{month, allocated, spent}],
        byType: [{type, value}],
        cumulative: [{month, spend, budgetLimit}] }
"""
import os
from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import models

# Monthly budget limit (INR) — read from env so deployments can configure it
MONTHLY_BUDGET_LIMIT = float(os.getenv("MONTHLY_BUDGET_LIMIT", "400000"))

# Repair type labels by defect class — for the PieChart
_REPAIR_TYPE_LABELS = {
    "D00": "Crack Sealing",
    "D10": "Crack Sealing",
    "D20": "Resurfacing",
    "D40": "Pothole Fill",
}


# ── Existing analytics ────────────────────────────────────────────────────────

def damage_statistics(db: Session) -> dict:
    by_class = defaultdict(int)
    by_severity = defaultdict(int)
    rows = db.query(models.Detection.class_code, models.Detection.severity).all()
    for class_code, severity in rows:
        by_class[class_code] += 1
        by_severity[severity] += 1
    return {"by_class": dict(by_class), "by_severity": dict(by_severity)}


def monthly_reports(db: Session) -> list:
    """Aggregated in Python so it works with both SQLite (dev) and Postgres (prod)."""
    det_map = defaultdict(int)
    for (detected_at,) in db.query(models.Detection.detected_at).all():
        if detected_at:
            det_map[detected_at.strftime("%Y-%m")] += 1

    repair_map = defaultdict(lambda: [0, 0.0])
    completed = (
        db.query(models.Repair.completed_date, models.Repair.estimated_cost)
        .filter(models.Repair.status == "completed")
        .all()
    )
    for completed_date, cost in completed:
        if completed_date:
            key = completed_date.strftime("%Y-%m")
            repair_map[key][0] += 1
            repair_map[key][1] += cost or 0.0

    months = sorted(set(det_map) | set(repair_map))
    out = []
    for m in months:
        r_count, r_cost = repair_map.get(m, [0, 0.0])
        out.append({
            "month": m,
            "detections": det_map.get(m, 0),
            "repairs_completed": r_count,
            "cost_spent": round(float(r_cost), 2),
        })
    return out


def heatmap(db: Session) -> list:
    rows = (
        db.query(models.Road.latitude, models.Road.longitude,
                 func.count(models.Detection.id))
        .join(models.Detection, models.Detection.road_id == models.Road.id)
        .group_by(models.Road.id)
        .all()
    )
    return [{"latitude": lat, "longitude": lon, "weight": count}
            for lat, lon, count in rows]


def road_health_trend(db: Session) -> list:
    rows = db.query(
        models.SimulationResult.created_at,
        models.SimulationResult.predicted_severity,
    ).all()
    by_day = defaultdict(list)
    for created_at, severity in rows:
        if created_at:
            by_day[created_at.strftime("%Y-%m-%d")].append(severity)

    return [
        {"date": day, "average_severity": round(sum(vals) / len(vals), 3)}
        for day, vals in sorted(by_day.items())
    ]


def prediction_history(db: Session, limit: int = 50) -> list:
    rows = (
        db.query(models.SimulationResult)
        .order_by(models.SimulationResult.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "current_severity": r.current_severity,
            "forecast_days": r.forecast_days,
            "predicted_severity": r.predicted_severity,
            "condition": r.condition,
            "remaining_life_years": r.remaining_life_years,
            "failure_probability": r.failure_probability,
            "simulation_id": r.id,
        }
        for r in rows
    ]


# ── Budget analytics (new) ────────────────────────────────────────────────────

def budget_analytics(db: Session) -> dict:
    """
    Build the three datasets the frontend's Analytics.jsx expects.

    Data is derived from the repairs table:
      - allocated = estimated_cost of all repairs created in that month
      - spent     = estimated_cost of completed repairs in that month
      - byType    = breakdown by repair category (Crack Sealing / Pothole Fill / Resurfacing)
      - cumulative = running total of spent, with a flat MONTHLY_BUDGET_LIMIT * months line
    """
    repairs = db.query(models.Repair).all()

    allocated_map: dict = defaultdict(float)  # month -> total estimated_cost
    spent_map: dict = defaultdict(float)       # month -> completed estimated_cost
    type_map: dict = defaultdict(float)        # label -> total cost

    for r in repairs:
        cost = r.estimated_cost or 0.0
        label = _REPAIR_TYPE_LABELS.get(r.defect_class or "", "Other")
        type_map[label] += cost

        if r.created_at:
            month_key = r.created_at.strftime("%b")
            allocated_map[month_key] += cost

        if r.status == "completed" and r.completed_date:
            month_key = r.completed_date.strftime("%b")
            spent_map[month_key] += cost

    # Build monthly list in chronological order
    all_months_keys = sorted(
        set(allocated_map) | set(spent_map),
        key=lambda m: datetime.strptime(m, "%b").month,
    )

    monthly = [
        {
            "month": m,
            "allocated": round(allocated_map.get(m, 0.0), 2),
            "spent": round(spent_map.get(m, 0.0), 2),
        }
        for m in all_months_keys
    ]

    # byType — percentage share for the PieChart
    total_type_cost = sum(type_map.values()) or 1.0
    by_type = [
        {"type": t, "value": round((v / total_type_cost) * 100, 1)}
        for t, v in type_map.items()
    ]

    # cumulative — running spent sum vs flat budget limit line
    cumulative_spend = 0.0
    budget_limit = MONTHLY_BUDGET_LIMIT * max(len(all_months_keys), 1)
    cumulative = []
    for m in all_months_keys:
        cumulative_spend += spent_map.get(m, 0.0)
        cumulative.append({
            "month": m,
            "spend": round(cumulative_spend, 2),
            "budgetLimit": round(budget_limit, 2),
        })

    return {
        "monthly": monthly,
        "byType": by_type,
        "cumulative": cumulative,
    }
