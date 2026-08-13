"""
CrewAI Agent definitions for the Road Infrastructure Management System.

Four sequential agents:
1. Priority Agent
2. Budget Agent
3. Schedule Agent
4. Traffic Agent
"""

import os
import logging

logger = logging.getLogger("agents.agents")


def _get_llm():
    """Create the OpenAI LLM used by all CrewAI agents."""

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is not set. "
            "Add it to your .env file to use the CrewAI agent system."
        )

    try:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=api_key,
            temperature=0,
        )

    except ImportError as e:
        raise RuntimeError(
            "langchain-openai is not installed. "
            "Run: pip install langchain-openai. "
            f"Original error: {e}"
        )


def build_agents():
    """
    Build the four CrewAI agents.
    """

    try:
        from crewai import Agent

    except ImportError as e:
        raise RuntimeError(
            "crewai is not installed. "
            "Run: pip install crewai. "
            f"Original error: {e}"
        )

    llm = _get_llm()

    common_settings = {
        "llm": llm,
        "verbose": False,
        "allow_delegation": False,
        "tools": [],
        "max_iter": 3,
        "max_execution_time": 180,
        "max_retry_limit": 1,
        "allow_code_execution": False,
    }

    priority_agent = Agent(
        role="Road Defect Priority Analyst",
        goal=(
            "Analyse the supplied road defects and assign each defect "
            "a priority of Critical, High, Medium, or Low. "
            "Follow the supplied priority rules exactly. "
            "Return a concise structured result and then stop."
        ),
        backstory=(
            "You are a senior road-safety engineer working on municipal "
            "road maintenance. You specialise in analysing YOLO-detected "
            "road defects and determining repair urgency. "
            "You make decisions from the supplied data only."
        ),
        **common_settings,
    )

    budget_agent = Agent(
        role="Infrastructure Budget Planner",
        goal=(
            "Use the priority analysis from the previous agent to decide "
            "which repairs should be funded within the supplied budget. "
            "Calculate the estimated repair cost and reserve. "
            "Return a concise budget decision and then stop."
        ),
        backstory=(
            "You are a municipal infrastructure budget officer. "
            "You prioritise safety-critical road repairs while respecting "
            "the available maintenance budget and emergency reserve."
        ),
        **common_settings,
    )

    schedule_agent = Agent(
        role="Repair Scheduling Coordinator",
        goal=(
            "Use the previous priority and budget decisions to create "
            "a practical repair schedule using the available crews and "
            "weather information. Return a concise schedule and then stop."
        ),
        backstory=(
            "You are an experienced road maintenance scheduling coordinator. "
            "You assign repair jobs to available crews while considering "
            "repair duration, weather, traffic and operational constraints."
        ),
        **common_settings,
    )

    traffic_agent = Agent(
        role="Traffic Impact Assessor",
        goal=(
            "Review the previous repair schedule and produce the final "
            "maintenance recommendation. Identify traffic risks, suggest "
            "off-peak scheduling where necessary, and provide a concise "
            "final summary. Then stop."
        ),
        backstory=(
            "You are a traffic engineer responsible for minimising "
            "congestion and disruption caused by road maintenance. "
            "You review the proposed schedule and make practical "
            "traffic-management recommendations."
        ),
        **common_settings,
    )

    logger.info(
        "CrewAI agents created with max_iter=3 and max_execution_time=180s"
    )

    return (
        priority_agent,
        budget_agent,
        schedule_agent,
        traffic_agent,
    )