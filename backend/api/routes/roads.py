"""
Roads CRUD. Not one of the 6 route files explicitly named in the integration
spec, but added because: (1) the frontend guide's Simulator page fetches
GET /api/roads for its dropdown, and (2) /api/detect and /api/simulate both
accept an optional road_id that has to come from somewhere.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.database import schemas, models, crud
from backend.utils.security import get_current_user, require_roles

router = APIRouter(prefix="/api/roads", tags=["roads"])


@router.get("", response_model=list[schemas.RoadOut])
def list_roads(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return crud.list_roads(db)


@router.post("", response_model=schemas.RoadOut, status_code=201)
def create_road(payload: schemas.RoadCreate, db: Session = Depends(get_db),
                 current_user: models.User = Depends(require_roles("admin", "engineer"))):
    return crud.create_road(db, **payload.dict())


@router.get("/{road_id}", response_model=schemas.RoadOut)
def get_road(road_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    road = crud.get_road(db, road_id)
    if not road:
        raise HTTPException(status_code=404, detail="Road not found")
    return road
