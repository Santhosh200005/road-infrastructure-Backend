from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.database import schemas, models, crud
from backend.services import repair_service
from backend.utils.security import get_current_user, require_roles

router = APIRouter(prefix="/api/repairs", tags=["repairs"])


@router.get("", response_model=list[schemas.RepairOut])
def list_repairs(status: Optional[str] = None, priority: Optional[str] = None,
                  db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    repairs = crud.list_repairs(db, status=status, priority=priority)
    return [_serialize(r) for r in repairs]


@router.post("", response_model=schemas.RepairOut, status_code=201)
def create_repair(payload: schemas.RepairCreate, db: Session = Depends(get_db),
                   current_user: models.User = Depends(require_roles("admin", "engineer"))):
    recommendation = {}
    if payload.detection_id:
        detection = db.query(models.Detection).filter(models.Detection.id == payload.detection_id).first()
        if not detection:
            raise HTTPException(status_code=404, detail="detection_id not found")
        recommendation = repair_service.recommend_repair(
            detection.class_code, detection.severity, detection.severity_level
        )

    defect_class = payload.defect_class or (detection.class_code if payload.detection_id else None)

    repair = crud.create_repair(
        db,
        road_id=payload.road_id,
        detection_id=payload.detection_id,
        defect_class=defect_class,
        priority=recommendation.get("priority", payload.priority or "Medium"),
        recommended_repair=recommendation.get("recommended_repair"),
        estimated_cost=recommendation.get("estimated_cost"),
        time_required_days=recommendation.get("time_required_days"),
        assigned_crew=payload.assigned_crew,
        scheduled_date=payload.scheduled_date,
    )
    return _serialize(repair)


@router.patch("/{repair_id}", response_model=schemas.RepairOut)
def update_repair(repair_id: str, payload: schemas.RepairUpdate, db: Session = Depends(get_db),
                   current_user: models.User = Depends(require_roles("admin", "engineer"))):
    repair = crud.get_repair(db, repair_id)
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")
    repair = crud.update_repair(db, repair, payload.dict())
    return _serialize(repair)


def _serialize(r: models.Repair) -> schemas.RepairOut:
    return schemas.RepairOut(
        id=r.id, road_id=r.road_id, detection_id=r.detection_id, defect_class=r.defect_class,
        priority=r.priority,
        status=r.status,
        recommended_repair=r.recommended_repair, estimated_cost=r.estimated_cost,
        time_required_days=r.time_required_days, assigned_crew=r.assigned_crew,
        scheduled_date=r.scheduled_date, completed_date=r.completed_date, created_at=r.created_at,
    )
