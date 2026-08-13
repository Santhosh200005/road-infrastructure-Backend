"""
SQLAlchemy models.

Schema notes / deliberate design decisions:

- Detection.class_code / severity mirror the REAL output of ml/detection/infer.py
  (`class`: "D00"/"D10"/"D20"/"D40", `severity`: "low"/"medium"/"high").
  We additionally store class_name and severity_level (Critical/High/Medium/Low)
  computed in the service layer, because the frontend needs those four buckets.

- SimulationResult stores the raw ML output PLUS three derived heuristic fields
  (condition, remaining_life_years, failure_probability) computed in simulator_service.py.

- AgentDecision stores CrewAI agent run results — one row per POST /api/agents/run.
  The fields match the frontend's AgentReports page expected shape exactly:
  { id, date, defects_processed, priority_breakdown, total_estimated_cost, reasoning }

- RequestLog covers the "log every request / inference time / errors" requirement.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Float, Integer, DateTime, ForeignKey, JSON, Text, Boolean
)
from sqlalchemy.orm import relationship

from backend.database.db import Base


def gen_uuid():
    return str(uuid.uuid4())


class UserRole(str, enum.Enum):
    admin = "admin"
    engineer = "engineer"
    inspector = "inspector"
    viewer = "viewer"


class RepairStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"


class RepairPriority(str, enum.Enum):
    critical = "Critical"
    high = "High"
    medium = "Medium"
    low = "Low"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default=UserRole.viewer.value, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    detections = relationship("Detection", back_populates="user")
    simulations = relationship("SimulationResult", back_populates="user")


class Road(Base):
    __tablename__ = "roads"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    length_km = Column(Float, nullable=True)
    road_age_years = Column(Float, nullable=True)
    material_type = Column(Integer, nullable=True)   # simulator feature: 0-3
    daily_vehicles = Column(Integer, nullable=True)
    last_repair_days = Column(Integer, nullable=True)  # days since last repair
    created_at = Column(DateTime, default=datetime.utcnow)

    detections = relationship("Detection", back_populates="road")
    repairs = relationship("Repair", back_populates="road")
    simulations = relationship("SimulationResult", back_populates="road")


class Detection(Base):
    __tablename__ = "detections"

    id = Column(String, primary_key=True, default=gen_uuid)
    road_id = Column(String, ForeignKey("roads.id"), nullable=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)

    image_path = Column(String, nullable=False)

    # Raw fields exactly as returned by ml/detection/infer.py::detect_defects()
    class_code = Column(String, nullable=False)        # "D00" | "D10" | "D20" | "D40"
    confidence = Column(Float, nullable=False)          # 0.0 – 1.0
    bbox = Column(JSON, nullable=False)                 # [xmin, ymin, xmax, ymax] pixel coords
    severity = Column(String, nullable=False)           # "low" | "medium" | "high"

    # Derived by detection_service.py for frontend convenience
    class_name = Column(String, nullable=False)         # e.g. "Pothole"
    severity_level = Column(String, nullable=False)     # "Critical"|"High"|"Medium"|"Low"

    detected_at = Column(DateTime, default=datetime.utcnow)

    road = relationship("Road", back_populates="detections")
    user = relationship("User", back_populates="detections")
    repairs = relationship("Repair", back_populates="detection")


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id = Column(String, primary_key=True, default=gen_uuid)
    road_id = Column(String, ForeignKey("roads.id"), nullable=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)

    # Raw inputs sent to forecast_severity()
    inputs = Column(JSON, nullable=False)

    # Raw output fields from ml/simulator/simulate.py::forecast_severity()
    current_severity = Column(Float, nullable=False)
    forecast_days = Column(Integer, nullable=False)
    predicted_severity = Column(Float, nullable=False)

    # Derived fields — NOT model-native, computed heuristically in simulator_service.py
    condition = Column(String, nullable=True)              # "Good"|"Fair"|"Poor"|"Critical"
    remaining_life_years = Column(Float, nullable=True)
    failure_probability = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    road = relationship("Road", back_populates="simulations")
    user = relationship("User", back_populates="simulations")


class Repair(Base):
    __tablename__ = "repairs"

    id = Column(String, primary_key=True, default=gen_uuid)
    road_id = Column(String, ForeignKey("roads.id"), nullable=True)
    detection_id = Column(String, ForeignKey("detections.id"), nullable=True)

    defect_class = Column(String, nullable=True)
    # String columns (not SQLAlchemy Enum) so display-style values like
    # "Critical"/"in_progress" round-trip correctly without name vs. value confusion.
    priority = Column(String, default=RepairPriority.medium.value)
    status = Column(String, default=RepairStatus.pending.value)

    recommended_repair = Column(String, nullable=True)
    estimated_cost = Column(Float, nullable=True)
    time_required_days = Column(Float, nullable=True)

    assigned_crew = Column(String, nullable=True)
    scheduled_date = Column(DateTime, nullable=True)
    completed_date = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    road = relationship("Road", back_populates="repairs")
    detection = relationship("Detection", back_populates="repairs")


class AgentDecision(Base):
    """
    One row per POST /api/agents/run.
    Response shape matches the frontend's AgentReports.jsx exactly:
        { id, date, defects_processed, priority_breakdown, total_estimated_cost, reasoning }
    """
    __tablename__ = "agent_decisions"

    id = Column(String, primary_key=True, default=gen_uuid)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Display date string ("YYYY-MM-DD") for the frontend — derived from created_at
    date = Column(String, nullable=False)

    # Run context
    defects_processed = Column(Integer, nullable=False, default=0)
    budget_available = Column(Float, nullable=True)
    num_crews = Column(Integer, nullable=True)

    # Structured results
    priority_breakdown = Column(JSON, nullable=True)    # {"Critical": N, "High": N, ...}
    total_estimated_cost = Column(Float, nullable=True)

    # Human-readable CrewAI output (shown in expanded card on frontend)
    reasoning = Column(Text, nullable=True)

    # Full raw crew output preserved for debugging
    raw_output = Column(Text, nullable=True)


class RequestLog(Base):
    __tablename__ = "request_logs"

    id = Column(String, primary_key=True, default=gen_uuid)
    path = Column(String, nullable=False)
    method = Column(String, nullable=False)
    status_code = Column(Integer, nullable=False)
    duration_ms = Column(Float, nullable=False)
    user_id = Column(String, nullable=True)
    error_detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
