"""
Thin CRUD helpers. Business logic (severity mapping, cost estimation, derived
simulation fields, agent analysis) lives in backend/services/, not here.
"""
from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import models


# ---------- Users ----------

def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.username == username).first()


def create_user(db: Session, username: str, email: str,
                hashed_password: str, role: str) -> models.User:
    user = models.User(
        username=username, email=email,
        hashed_password=hashed_password, role=role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------- Roads ----------

def get_road(db: Session, road_id: str) -> Optional[models.Road]:
    return db.query(models.Road).filter(models.Road.id == road_id).first()


def list_roads(db: Session) -> List[models.Road]:
    return db.query(models.Road).all()


def create_road(db: Session, **kwargs) -> models.Road:
    road = models.Road(**kwargs)
    db.add(road)
    db.commit()
    db.refresh(road)
    return road


# ---------- Detections ----------

def create_detection(db: Session, **kwargs) -> models.Detection:
    detection = models.Detection(**kwargs)
    db.add(detection)
    db.commit()
    db.refresh(detection)
    return detection


def list_detections(db: Session, road_id: Optional[str] = None,
                    limit: int = 500) -> List[models.Detection]:
    q = db.query(models.Detection)
    if road_id:
        q = q.filter(models.Detection.road_id == road_id)
    return q.order_by(models.Detection.detected_at.desc()).limit(limit).all()


def count_detections_by_class(db: Session, class_code: str) -> int:
    return db.query(models.Detection).filter(
        models.Detection.class_code == class_code
    ).count()


# ---------- Simulation results ----------

def create_simulation_result(db: Session, **kwargs) -> models.SimulationResult:
    sim = models.SimulationResult(**kwargs)
    db.add(sim)
    db.commit()
    db.refresh(sim)
    return sim


def list_simulation_results(db: Session, road_id: Optional[str] = None,
                             limit: int = 200) -> List[models.SimulationResult]:
    q = db.query(models.SimulationResult)
    if road_id:
        q = q.filter(models.SimulationResult.road_id == road_id)
    return q.order_by(models.SimulationResult.created_at.desc()).limit(limit).all()


# ---------- Repairs ----------

def create_repair(db: Session, **kwargs) -> models.Repair:
    repair = models.Repair(**kwargs)
    db.add(repair)
    db.commit()
    db.refresh(repair)
    return repair


def list_repairs(db: Session, status: Optional[str] = None,
                 priority: Optional[str] = None) -> List[models.Repair]:
    q = db.query(models.Repair)
    if status:
        q = q.filter(models.Repair.status == status)
    if priority:
        q = q.filter(models.Repair.priority == priority)
    return q.order_by(models.Repair.created_at.desc()).all()


def get_repair(db: Session, repair_id: str) -> Optional[models.Repair]:
    return db.query(models.Repair).filter(models.Repair.id == repair_id).first()


def update_repair(db: Session, repair: models.Repair, updates: dict) -> models.Repair:
    for k, v in updates.items():
        if v is not None:
            setattr(repair, k, v)
    if updates.get("status") == "completed":
        repair.completed_date = datetime.utcnow()
    db.commit()
    db.refresh(repair)
    return repair


# ---------- Agent Decisions ----------

def create_agent_decision(db: Session, **kwargs) -> models.AgentDecision:
    decision = models.AgentDecision(**kwargs)
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return decision


def list_agent_decisions(db: Session, limit: int = 100) -> List[models.AgentDecision]:
    return (
        db.query(models.AgentDecision)
        .order_by(models.AgentDecision.created_at.desc())
        .limit(limit)
        .all()
    )


def get_agent_decision(db: Session, decision_id: str) -> Optional[models.AgentDecision]:
    return db.query(models.AgentDecision).filter(
        models.AgentDecision.id == decision_id
    ).first()


# ---------- Dashboard aggregates ----------

def dashboard_counts(db: Session) -> dict:
    total_roads = db.query(models.Road).count()
    total_detections = db.query(models.Detection).count()
    total_potholes = db.query(models.Detection).filter(
        models.Detection.class_code == "D40"
    ).count()
    high_risk_roads = (
        db.query(models.Detection.road_id)
        .filter(models.Detection.severity == "high",
                models.Detection.road_id.isnot(None))
        .distinct()
        .count()
    )
    pending_repairs = db.query(models.Repair).filter(
        models.Repair.status == "pending"
    ).count()
    completed_repairs = db.query(models.Repair).filter(
        models.Repair.status == "completed"
    ).count()
    avg_confidence = db.query(func.avg(models.Detection.confidence)).scalar() or 0.0
    avg_remaining_life = db.query(
        func.avg(models.SimulationResult.remaining_life_years)
    ).scalar() or 0.0

    return {
        "total_roads": total_roads,
        "total_potholes": total_potholes,
        "total_detections": total_detections,
        "high_risk_roads": high_risk_roads,
        "pending_repairs": pending_repairs,
        "completed_repairs": completed_repairs,
        "average_confidence": round(float(avg_confidence), 4),
        "average_remaining_life": round(float(avg_remaining_life), 2),
    }


# ---------- Request Logging ----------

def log_request(db: Session, path: str, method: str, status_code: int,
                duration_ms: float, user_id: Optional[str] = None,
                error_detail: Optional[str] = None) -> None:
    log = models.RequestLog(
        path=path, method=method, status_code=status_code,
        duration_ms=duration_ms, user_id=user_id, error_detail=error_detail,
    )
    db.add(log)
    db.commit()
