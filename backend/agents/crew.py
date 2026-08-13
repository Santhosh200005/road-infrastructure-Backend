"""
CrewAI sequential workflow.

Four agents:
1. Priority
2. Budget
3. Schedule
4. Traffic
"""

import logging

logger = logging.getLogger("agents.crew")

# Same priority rules the agent prompts are given (see tasks.py PRIORITY RULES
# block). Kept here as a plain-Python source of truth for priority_breakdown
# and total_estimated_cost so the API response never depends on successfully
# parsing free-form LLM text for numbers that already exist in the DB-derived
# damage_report (each defect already carries its own `estimated_cost`, computed
# upstream in agent_service._build_damage_report using the existing
# _BASE_COST / _SEVERITY_MULT logic — this does not duplicate or replace it).
_HIGH_RISK_CLASSES = {"D20", "D40"}


def _priority_for(class_code: str, severity: str) -> str:
    severity = (severity or "").lower()

    if severity == "low":
        return "Low"
    if class_code in _HIGH_RISK_CLASSES and severity == "high":
        return "Critical"
    if class_code in _HIGH_RISK_CLASSES and severity == "medium":
        return "High"
    if severity == "high":
        # D00 / D10 + high
        return "High"
    if severity == "medium":
        # D00 / D10 + medium
        return "Medium"
    # Unrecognised/missing severity: don't invent a new rule, treat
    # conservatively as Low rather than silently dropping the defect.
    return "Low"


def _compute_priority_and_cost(damage_report: dict) -> tuple[dict, float]:
    """
    Deterministically derive priority_breakdown and total_estimated_cost
    from the real defect data, applying the existing priority rules and
    reusing each defect's pre-computed `estimated_cost`.
    """
    breakdown = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    total_cost = 0.0

    for defect in damage_report.get("defects", []):
        level = _priority_for(
            defect.get("class_code", ""), defect.get("severity", "")
        )
        breakdown[level] += 1
        total_cost += float(defect.get("estimated_cost", 0) or 0)

    return breakdown, round(total_cost, 2)


def _fallback_reasoning(damage_report: dict, breakdown: dict, total_cost: float) -> str:
    """Plain-English summary used only if the CrewAI narrative is missing
    or unusable (e.g. it stalled on the iteration/time limit)."""
    total = damage_report.get("summary", {}).get("total", 0)
    return (
        f"Analysed {total} road defects. Priority breakdown — "
        f"Critical: {breakdown['Critical']}, High: {breakdown['High']}, "
        f"Medium: {breakdown['Medium']}, Low: {breakdown['Low']}. "
        f"Total estimated repair cost: ₹{total_cost:,.2f}."
    )


def _is_unusable_reasoning(text: str) -> bool:
    if not text or not text.strip():
        return True
    lowered = text.lower()
    return (
        "iteration limit" in lowered
        or "time limit" in lowered
        or "agent stopped" in lowered
    )


def run_crew(
    damage_report: dict,
    budget: float = 500000.0,
    num_crews: int = 3,
    weather_context: str = "",
) -> dict:
    """
    Run the sequential four-agent CrewAI workflow.
    """

    try:
        from crewai import Crew, Process

    except ImportError as e:

        raise RuntimeError(
            "crewai not installed. "
            "Run: pip install crewai. "
            f"Error: {e}"
        ) from e

    from backend.agents.agents import build_agents
    from backend.agents.tasks import build_tasks

    defect_count = (
        damage_report
        .get("summary", {})
        .get("total", 0)
    )

    logger.info(
        "Starting CrewAI workflow: defects=%d budget=%.0f crews=%d",
        defect_count,
        budget,
        num_crews,
    )

    # ---------------------------------------------------------
    # BUILD AGENTS
    # ---------------------------------------------------------

    agents = build_agents()

    # ---------------------------------------------------------
    # BUILD TASKS
    # ---------------------------------------------------------

    tasks = build_tasks(
        agents=agents,
        damage_report=damage_report,
        budget=budget,
        num_crews=num_crews,
        weather_context=weather_context,
    )

    # ---------------------------------------------------------
    # CREATE CREW
    # ---------------------------------------------------------

    crew = Crew(
        agents=list(agents),
        tasks=tasks,
        process=Process.sequential,
        verbose=False,
    )

    # ---------------------------------------------------------
    # RUN CREW
    # ---------------------------------------------------------

    try:

        logger.info("Calling CrewAI kickoff()...")

        result = crew.kickoff()

    except Exception as e:

        logger.exception("CrewAI kickoff failed.")

        raise RuntimeError(
            f"Agent crew failed: {e}"
        ) from e

    # ---------------------------------------------------------
    # GET RAW OUTPUT
    # ---------------------------------------------------------

    if hasattr(result, "raw"):

        raw_output = result.raw or ""

    else:

        raw_output = str(result)

    raw_output = str(raw_output)

    logger.info(
        "CrewAI workflow completed. Output length=%d",
        len(raw_output),
    )

    # ---------------------------------------------------------
    # PRIORITY BREAKDOWN + TOTAL COST — computed deterministically from the
    # real defect data (class_code + severity + pre-computed estimated_cost),
    # not parsed out of free-form LLM text. This is what actually fixes
    # total_estimated_cost being 0 and Critical always being 0: those numbers
    # no longer depend on the LLM formatting its answer in a regex-matchable
    # way. The CrewAI run still produces the priority/budget agents'
    # structured (output_pydantic) task results as context for the schedule
    # and traffic agents, and its own narrative is used for `reasoning` below.
    # ---------------------------------------------------------

    priority_breakdown, total_cost = _compute_priority_and_cost(damage_report)

    # ---------------------------------------------------------
    # REASONING — prefer the crew's own final narrative (from the Traffic
    # Agent's task, i.e. `raw_output`). Fall back to a computed summary only
    # if the crew produced nothing usable (e.g. it hit the iteration/time
    # limit), so the API never surfaces the raw CrewAI stop message.
    # ---------------------------------------------------------

    if _is_unusable_reasoning(raw_output):
        logger.warning(
            "CrewAI produced no usable final narrative "
            "(likely hit max_iter/max_execution_time); "
            "falling back to a computed summary for `reasoning`."
        )
        reasoning = _fallback_reasoning(
            damage_report, priority_breakdown, total_cost
        )
    else:
        reasoning = raw_output[:4000]

    # ---------------------------------------------------------
    # RETURN
    # ---------------------------------------------------------

    return {
        "reasoning": reasoning,

        "raw_output": raw_output,

        "priority_breakdown": priority_breakdown,

        "total_estimated_cost": total_cost,
    }