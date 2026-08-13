"""
Repair recommendation service.

No ML model produces repair recommendations/cost/priority anywhere in Person
A's code — this is pure backend business logic based on damage type, severity,
and (if available) remaining life from a simulation. Rules are simple and
explicit on purpose so they're easy to tune.
"""
from typing import Optional

REPAIR_BY_CLASS = {
    "D00": "Crack sealing",
    "D10": "Crack sealing",
    "D20": "Resurfacing (alligator cracking indicates structural fatigue)",
    "D40": "Pothole patching",
}

BASE_COST_BY_CLASS = {  # rough per-repair cost estimate, USD
    "D00": 150,
    "D10": 150,
    "D20": 900,
    "D40": 350,
}

TIME_DAYS_BY_CLASS = {
    "D00": 0.5,
    "D10": 0.5,
    "D20": 3,
    "D40": 1,
}

SEVERITY_COST_MULTIPLIER = {"low": 1.0, "medium": 1.4, "high": 2.0}

PRIORITY_BY_SEVERITY_LEVEL = {
    "Critical": "Critical",
    "High": "High",
    "Medium": "Medium",
    "Low": "Low",
}


def recommend_repair(class_code: str, severity: str, severity_level: str,
                      remaining_life_years: Optional[float] = None) -> dict:
    recommended = REPAIR_BY_CLASS.get(class_code, "General maintenance inspection")
    base_cost = BASE_COST_BY_CLASS.get(class_code, 300)
    multiplier = SEVERITY_COST_MULTIPLIER.get(severity, 1.0)
    estimated_cost = round(base_cost * multiplier, 2)
    time_required = TIME_DAYS_BY_CLASS.get(class_code, 1)
    priority = PRIORITY_BY_SEVERITY_LEVEL.get(severity_level, "Medium")

    # Escalate priority if a simulation says remaining life is short, regardless
    # of the raw detection severity.
    if remaining_life_years is not None and remaining_life_years < 1.0:
        priority = "Critical"

    return {
        "recommended_repair": recommended,
        "estimated_cost": estimated_cost,
        "time_required_days": time_required,
        "priority": priority,
    }
