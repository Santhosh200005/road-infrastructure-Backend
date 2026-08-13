"""Tests for SQLAlchemy models: creation, relationships, defaults."""
from datetime import datetime
from backend.database import models


def test_create_road(db):
    road = models.Road(
        name="Test Road", latitude=17.38, longitude=78.47,
        length_km=5.0, road_age_years=8, material_type=1,
        daily_vehicles=6000, last_repair_days=200,
    )
    db.add(road)
    db.commit()
    db.refresh(road)
    assert road.id is not None
    assert road.name == "Test Road"
    assert road.created_at is not None


def test_create_detection_linked_to_road(db):
    road = models.Road(name="Detection Road", latitude=1.0, longitude=1.0)
    db.add(road)
    db.commit()
    db.refresh(road)

    detection = models.Detection(
        road_id=road.id,
        image_path="/uploads/test.jpg",
        class_code="D40",
        confidence=0.85,
        bbox=[1.0, 2.0, 3.0, 4.0],
        severity="high",
        class_name="Pothole",
        severity_level="Critical",
    )
    db.add(detection)
    db.commit()
    db.refresh(detection)

    assert detection.id is not None
    assert detection.road_id == road.id
    assert detection.road.name == "Detection Road"
    assert road.detections[-1].id == detection.id


def test_create_simulation_result(db):
    sim = models.SimulationResult(
        inputs={"current_severity": 3.0},
        current_severity=3.0,
        forecast_days=30,
        predicted_severity=3.7,
        condition="Fair",
        remaining_life_years=12.5,
        failure_probability=0.02,
    )
    db.add(sim)
    db.commit()
    db.refresh(sim)
    assert sim.id is not None
    assert sim.condition == "Fair"


def test_create_repair_defaults(db):
    repair = models.Repair(defect_class="D00")
    db.add(repair)
    db.commit()
    db.refresh(repair)
    assert repair.status == "pending"
    assert repair.priority == "Medium"


def test_create_agent_decision(db):
    decision = models.AgentDecision(
        date="2026-08-09",
        defects_processed=10,
        budget_available=500000.0,
        num_crews=3,
        priority_breakdown={"Critical": 2, "High": 3, "Medium": 4, "Low": 1},
        total_estimated_cost=45000.0,
        reasoning="Test reasoning",
        raw_output="Full raw output",
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    assert decision.id is not None
    assert decision.priority_breakdown["Critical"] == 2


def test_user_role_default(db):
    user = models.User(
        username="modeltestuser",
        email="modeltest@test.com",
        hashed_password="hashed",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    assert user.role == "viewer"
    assert user.is_active is True
