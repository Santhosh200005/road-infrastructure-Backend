from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.database import schemas, models, crud
from backend.services import simulator_service
from backend.utils.security import get_current_user

router = APIRouter(prefix="/api", tags=["simulation"])


def _resolve_inputs(payload: schemas.SimulateRequest, db: Session) -> dict:
    """
    If road_id is given, use the Road record's stored attributes to fill any
    fields the caller didn't provide explicitly.
    The schema's model_validator has already normalised 'days' → forecast_days.
    """
    overrides = payload.model_dump(exclude={"road_id", "forecast_days", "days"})
    if payload.road_id:
        road = crud.get_road(db, payload.road_id)
        if not road:
            raise HTTPException(
                status_code=404, detail=f"road_id {payload.road_id} not found"
            )
        if overrides.get("daily_vehicles") is None:
            overrides["daily_vehicles"] = road.daily_vehicles
        if overrides.get("road_age_years") is None:
            overrides["road_age_years"] = road.road_age_years
        if overrides.get("material_type") is None:
            overrides["material_type"] = road.material_type
        if overrides.get("last_repair_days") is None:
            overrides["last_repair_days"] = road.last_repair_days
    return overrides


@router.post("/simulate", response_model=schemas.SimulateResponse)
def simulate(
    payload: schemas.SimulateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Single-point severity forecast.
    Accepts both 'forecast_days' and 'days' (the latter is what api.js sends).
    """
    overrides = _resolve_inputs(payload, db)
    try:
        result = simulator_service.run_and_persist_simulation(
            db,
            raw_inputs=overrides,
            days=payload.forecast_days,
            road_id=payload.road_id,
            user_id=current_user.id,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return schemas.SimulateResponse(**result)


@router.post("/simulate/series", response_model=schemas.SimulateSeriesResponse)
def simulate_series(
    payload: schemas.SimulateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    0-180 day series for the Simulator page LineChart.
    Calls forecast_severity() repeatedly at multiple day-points and
    assembles the series server-side (avoids 7 separate frontend calls).
    """
    overrides = _resolve_inputs(payload, db)
    try:
        points = simulator_service.run_series(
            db,
            raw_inputs=overrides,
            road_id=payload.road_id,
            user_id=current_user.id,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return schemas.SimulateSeriesResponse(
        road_id=payload.road_id,
        points=[schemas.SimulateResponse(**p) for p in points],
    )
