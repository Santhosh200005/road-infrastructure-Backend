"""
Agent routes.

POST /api/agents/run    — trigger the CrewAI 4-agent workflow, persist result
GET  /api/agents/reports — list all past agent sessions (for AgentReports page)
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database.db import get_db
from backend.database import schemas, models
from backend.services import agent_service
from backend.utils.security import get_current_user, require_roles

logger = logging.getLogger("routes.agents")

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post("/run", response_model=schemas.AgentDecisionOut,
             status_code=status.HTTP_201_CREATED)
def run_agents(
    payload: schemas.AgentRunRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles("admin", "engineer")),
):
    """
    Trigger the CrewAI 4-agent sequential workflow.

    The service layer pulls current detections from the database, runs the
    crew with the supplied budget / crew count / weather context, and persists
    the decision to the agent_decisions table.

    Requires OPENAI_API_KEY to be set in the environment.
    Returns 503 if the LLM key is missing or crewai isn't installed.
    Returns 500 on any other crew failure.
    """
    try:
        result = agent_service.run_agent_analysis(
            db=db,
            budget=payload.budget or 500000.0,
            num_crews=payload.num_crews or 3,
            road_ids=payload.road_ids,
            weather_context=payload.weather_context or "",
        )
    except RuntimeError as e:
        msg = str(e)
        if "OPENAI_API_KEY" in msg or "not installed" in msg:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=msg,
            )
        logger.exception("Agent run failed")
        raise HTTPException(status_code=500, detail=msg)

    return result


@router.get("/reports", response_model=List[schemas.AgentDecisionOut])
def list_agent_reports(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List all past agent analysis sessions, newest first."""
    return agent_service.list_agent_reports(db)
