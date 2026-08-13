"""
Pydantic request/response schemas.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field, model_validator


# ---------- Auth / Users ----------

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "viewer"  # admin | engineer | inspector | viewer


class UserOut(BaseModel):
    id: str
    username: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


# ---------- Roads ----------

class RoadCreate(BaseModel):
    name: str
    latitude: float
    longitude: float
    length_km: Optional[float] = None
    road_age_years: Optional[float] = None
    material_type: Optional[int] = None
    daily_vehicles: Optional[int] = None
    last_repair_days: Optional[int] = None


class RoadOut(RoadCreate):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Detection ----------

class DetectionItem(BaseModel):
    """Mirrors the raw shape returned by ml/detection/infer.py::detect_defects(),
    plus derived fields the frontend needs (class_name, severity_level)."""
    class_code: str = Field(..., description="Raw model class: D00 | D10 | D20 | D40")
    class_name: str
    confidence: float
    bbox: List[float]
    severity: str            # low | medium | high  (raw, from ML)
    severity_level: str      # Critical | High | Medium | Low  (derived, for map markers)


class DetectionResponse(BaseModel):
    status: str
    detections: List[DetectionItem]
    count: int
    image_url: str
    detection_ids: List[str]


class DetectionRecordOut(BaseModel):
    id: str
    road_id: Optional[str]
    image_path: str
    class_code: str
    class_name: str
    confidence: float
    bbox: List[float]
    severity: str
    severity_level: str
    detected_at: datetime

    class Config:
        from_attributes = True


# ---------- Simulation ----------

class SimulateRequest(BaseModel):
    """Frontend-facing simulate request.
    Accepts BOTH 'forecast_days' (internal name) AND 'days' (what the
    frontend's api.js actually sends: { ...inputs, days }). The validator
    below normalises to forecast_days before the route uses it.
    """
    road_id: Optional[str] = None
    current_severity: Optional[float] = None
    daily_vehicles: Optional[int] = None
    rainfall_mm: Optional[float] = None
    avg_temp: Optional[float] = None
    road_age_years: Optional[float] = None
    last_repair_days: Optional[int] = None
    material_type: Optional[int] = None
    forecast_days: int = 30
    # 'days' alias — the frontend sends this key
    days: Optional[int] = None

    @model_validator(mode="after")
    def normalise_days(self) -> "SimulateRequest":
        """If the caller passed 'days', treat it as forecast_days."""
        if self.days is not None:
            self.forecast_days = self.days
        return self


class SimulateResponse(BaseModel):
    # raw ML output
    current_severity: float
    forecast_days: int
    predicted_severity: float
    # derived (heuristic, not model-native — see simulator_service.py)
    condition: str
    remaining_life_years: float
    failure_probability: float
    simulation_id: str


class SimulateSeriesResponse(BaseModel):
    """0-180 day series for the frontend LineChart, built by calling
    forecast_severity repeatedly at different day counts."""
    road_id: Optional[str]
    points: List[SimulateResponse]


# ---------- Repairs ----------

class RepairCreate(BaseModel):
    road_id: Optional[str] = None
    detection_id: Optional[str] = None
    defect_class: Optional[str] = None
    priority: Optional[str] = "Medium"
    assigned_crew: Optional[str] = None
    scheduled_date: Optional[datetime] = None


class RepairUpdate(BaseModel):
    status: Optional[str] = None
    assigned_crew: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    priority: Optional[str] = None


class RepairOut(BaseModel):
    id: str
    road_id: Optional[str]
    detection_id: Optional[str]
    defect_class: Optional[str]
    priority: str
    status: str
    recommended_repair: Optional[str]
    estimated_cost: Optional[float]
    time_required_days: Optional[float]
    assigned_crew: Optional[str]
    scheduled_date: Optional[datetime]
    completed_date: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Agents ----------

class AgentRunRequest(BaseModel):
    """Request body for POST /api/agents/run.
    All fields optional — the agent service will pull current detections
    from the database if road_ids is omitted.
    """
    budget: Optional[float] = Field(default=500000.0, description="Available budget in INR")
    num_crews: Optional[int] = Field(default=3, description="Number of repair crews available")
    road_ids: Optional[List[str]] = Field(
        default=None,
        description="Limit analysis to specific road IDs. Omit to analyse all roads."
    )
    weather_context: Optional[str] = Field(
        default=None,
        description="Optional weather summary to include in agent context"
    )


class AgentDecisionOut(BaseModel):
    """Matches the frontend's AgentReports.jsx expected shape exactly."""
    id: str
    date: str
    defects_processed: int
    priority_breakdown: Optional[Dict[str, int]]
    total_estimated_cost: Optional[float]
    reasoning: Optional[str]

    class Config:
        from_attributes = True


# ---------- Dashboard / Analytics ----------

class DashboardSummary(BaseModel):
    total_roads: int
    total_potholes: int
    total_detections: int
    high_risk_roads: int
    pending_repairs: int
    completed_repairs: int
    average_confidence: float
    average_remaining_life: float


class DamageStatistics(BaseModel):
    by_class: Dict[str, int]
    by_severity: Dict[str, int]


class MonthlyReportPoint(BaseModel):
    month: str
    detections: int
    repairs_completed: int
    cost_spent: float


class HeatmapPoint(BaseModel):
    latitude: float
    longitude: float
    weight: int


class RoadHealthTrendPoint(BaseModel):
    date: str
    average_severity: float


class AnalyticsResponse(BaseModel):
    damage_statistics: DamageStatistics
    monthly_reports: List[MonthlyReportPoint]
    heatmap: List[HeatmapPoint]
    road_health_trend: List[RoadHealthTrendPoint]
    prediction_history: List[SimulateResponse]


# ---------- Budget Analytics (GET /api/analytics/budget) ----------
# Shape confirmed from Person C's Analytics.jsx mock:
#   { monthly: [{month, allocated, spent}],
#     byType: [{type, value}],
#     cumulative: [{month, spend, budgetLimit}] }

class BudgetMonthly(BaseModel):
    month: str
    allocated: float
    spent: float


class BudgetByType(BaseModel):
    type: str
    value: float


class BudgetCumulative(BaseModel):
    month: str
    spend: float
    budgetLimit: float


class BudgetAnalyticsResponse(BaseModel):
    monthly: List[BudgetMonthly]
    byType: List[BudgetByType]
    cumulative: List[BudgetCumulative]
