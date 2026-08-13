from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.database import schemas, models, crud
from backend.utils.security import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=schemas.DashboardSummary)
def dashboard(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    counts = crud.dashboard_counts(db)
    return schemas.DashboardSummary(**counts)
