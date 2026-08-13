from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.database import schemas, models
from backend.services import analytics_service
from backend.utils.security import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("", response_model=schemas.AnalyticsResponse)
def analytics(db: Session = Depends(get_db),
              current_user: models.User = Depends(get_current_user)):
    return schemas.AnalyticsResponse(
        damage_statistics=schemas.DamageStatistics(
            **analytics_service.damage_statistics(db)
        ),
        monthly_reports=[
            schemas.MonthlyReportPoint(**m)
            for m in analytics_service.monthly_reports(db)
        ],
        heatmap=[
            schemas.HeatmapPoint(**h) for h in analytics_service.heatmap(db)
        ],
        road_health_trend=[
            schemas.RoadHealthTrendPoint(**t)
            for t in analytics_service.road_health_trend(db)
        ],
        prediction_history=[
            schemas.SimulateResponse(**p)
            for p in analytics_service.prediction_history(db)
        ],
    )


@router.get("/map")
def analytics_map(db: Session = Depends(get_db),
                  current_user: models.User = Depends(get_current_user)):
    """
    Feeds Person C's MapView page — one entry per detection with a road
    location, class, severity, confidence, and detected_at.

    Returns a flat array (not GeoJSON) matching the frontend's fetchMapDefects()
    assumption in api.js:
      [{ id, latitude, longitude, class, class_name, severity, severity_level,
         confidence, detected_at }]
    """
    from backend.database import crud as _crud
    detections = _crud.list_detections(db)
    out = []
    for d in detections:
        road = d.road
        if not road:
            continue
        out.append({
            "id": d.id,
            "latitude": road.latitude,
            "longitude": road.longitude,
            "class": d.class_code,
            "class_name": d.class_name,
            "severity": d.severity,
            "severity_level": d.severity_level,
            "confidence": d.confidence,
            "detected_at": d.detected_at.isoformat() if d.detected_at else None,
        })
    return out


@router.get("/budget", response_model=schemas.BudgetAnalyticsResponse)
def budget(db: Session = Depends(get_db),
           current_user: models.User = Depends(get_current_user)):
    """
    Budget analytics for the three charts on Analytics.jsx:
      Chart 1 (BarChart):   monthly.allocated vs monthly.spent
      Chart 2 (PieChart):   byType (Crack Sealing / Pothole Fill / Resurfacing)
      Chart 3 (LineChart):  cumulative spend vs budget limit over time
    """
    result = analytics_service.budget_analytics(db)
    return schemas.BudgetAnalyticsResponse(
        monthly=[schemas.BudgetMonthly(**m) for m in result["monthly"]],
        byType=[schemas.BudgetByType(**t) for t in result["byType"]],
        cumulative=[schemas.BudgetCumulative(**c) for c in result["cumulative"]],
    )
