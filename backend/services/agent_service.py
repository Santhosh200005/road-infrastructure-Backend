"""
Agent service: builds the damage_report from real DB data, calls the crew,
persists the result to AgentDecision, and returns the frontend-shaped dict.

This is deliberately separated from agents/crew.py so the crew module stays
pure (no DB imports) and the service layer stays testable (mock crew).
"""
import logging
from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session

from backend.database import crud, models

logger = logging.getLogger("services.agent_service")

# Cost estimates per class × severity multiplier, mirroring repair_service.py
_BASE_COST = {"D00": 150, "D10": 150, "D20": 900, "D40": 350}
_SEVERITY_MULT = {"low": 1.0, "medium": 1.4, "high": 2.0}


def _build_damage_report(db: Session, road_ids: Optional[List[str]] = None) -> dict:
    """
    Pull recent detections from the DB and shape them into the damage_report
    dict that the CrewAI tasks expect.
    """
    detections = crud.list_detections(db, limit=200)
    if road_ids:
        detections = [d for d in detections if d.road_id in road_ids]

    defects = []
    summary = {"total": 0, "D00": 0, "D10": 0, "D20": 0, "D40": 0,
               "high": 0, "medium": 0, "low": 0}

    for d in detections:
        cost = round(
            _BASE_COST.get(d.class_code, 300) *
            _SEVERITY_MULT.get(d.severity, 1.0),
            2,
        )
        defects.append({
            "id": d.id,
            "class_code": d.class_code,
            "class_name": d.class_name,
            "severity": d.severity,
            "severity_level": d.severity_level,
            "confidence": d.confidence,
            "road_id": d.road_id,
            "estimated_cost": cost,
            "detected_at": d.detected_at.isoformat() if d.detected_at else None,
        })
        summary["total"] += 1
        if d.class_code in summary:
            summary[d.class_code] += 1
        if d.severity in summary:
            summary[d.severity] += 1

    return {"defects": defects, "summary": summary}


def run_agent_analysis(db: Session, budget: float, num_crews: int,
                       road_ids: Optional[List[str]], weather_context: str) -> dict:
    """
    Entry-point called by the /api/agents/run route.

    1. Pulls detections from DB
    2. Runs CrewAI sequential workflow
    3. Persists AgentDecision
    4. Returns the frontend-shaped record
    """
    damage_report = _build_damage_report(db, road_ids)
    defects_processed = damage_report["summary"]["total"]

    logger.info(
        "Agent analysis: %d defects, budget=%.0f, crews=%d",
        defects_processed, budget, num_crews,
    )

    from backend.agents.crew import run_crew
    crew_result = run_crew(
        damage_report=damage_report,
        budget=budget,
        num_crews=num_crews,
        weather_context=weather_context,
    )

    today = datetime.utcnow().strftime("%Y-%m-%d")
    decision = crud.create_agent_decision(
        db,
        date=today,
        defects_processed=defects_processed,
        budget_available=budget,
        num_crews=num_crews,
        priority_breakdown=crew_result["priority_breakdown"],
        total_estimated_cost=crew_result["total_estimated_cost"],
        reasoning=crew_result["reasoning"],
        raw_output=crew_result["raw_output"],
    )

    return _serialize(decision)


def list_agent_reports(db: Session) -> list:
    decisions = crud.list_agent_decisions(db)
    return [_serialize(d) for d in decisions]


def _serialize(d: models.AgentDecision) -> dict:
    return {
        "id": d.id,
        "date": d.date,
        "defects_processed": d.defects_processed,
        "priority_breakdown": d.priority_breakdown or {},
        "total_estimated_cost": d.total_estimated_cost or 0.0,
        "reasoning": d.reasoning or "",
    }
