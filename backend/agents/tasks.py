"""
CrewAI Task definitions — one task per agent.

Each task description injects the real project data (defect report, budget,
crews, weather) so agents reason about actual information, not generic examples.
"""
import json

from pydantic import BaseModel, Field


class PriorityBreakdown(BaseModel):
    """Structured output for the Priority Agent's task."""
    critical: int = Field(0, description="Count of Critical priority defects")
    high: int = Field(0, description="Count of High priority defects")
    medium: int = Field(0, description="Count of Medium priority defects")
    low: int = Field(0, description="Count of Low priority defects")
    summary: str = Field(
        "", description="1-2 sentence reasoning for the top-priority items"
    )


class BudgetAllocation(BaseModel):
    """Structured output for the Budget Agent's task."""
    funded_count: int = Field(0, description="Number of repairs funded")
    deferred_count: int = Field(0, description="Number of repairs deferred")
    reserve_amount: float = Field(0, description="Emergency reserve amount kept back")
    summary: str = Field(
        "", description="1-2 sentence summary of the funding decision"
    )


def build_tasks(agents, damage_report: dict, budget: float,
                num_crews: int, weather_context: str = ""):
    """
    Build and return the four sequential tasks.

    Args:
        agents: tuple of (priority_agent, budget_agent, schedule_agent, traffic_agent)
        damage_report: dict with keys 'defects' (list) and summary counts
        budget: available budget in INR
        num_crews: number of available repair crews
        weather_context: optional weather summary string from the weather API
    """
    try:
        from crewai import Task
    except ImportError as e:
        raise RuntimeError(f"crewai not installed: {e}")

    priority_agent, budget_agent, schedule_agent, traffic_agent = agents

    defects_json = json.dumps(damage_report.get("defects", []), indent=2)
    summary = damage_report.get("summary", {})

    # ── Task 1: Priority Analysis ──────────────────────────────────────────
    priority_task = Task(
        description=(
            f"Analyse the following road defects detected by the YOLO-based inspection "
            f"system and produce a prioritised defect list.\n\n"
            f"DEFECT DATA:\n{defects_json}\n\n"
            f"SUMMARY COUNTS:\n"
            f"  Total defects: {summary.get('total', 0)}\n"
            f"  By class: D00={summary.get('D00', 0)}, D10={summary.get('D10', 0)}, "
            f"D20={summary.get('D20', 0)}, D40={summary.get('D40', 0)}\n"
            f"  By severity: high={summary.get('high', 0)}, "
            f"medium={summary.get('medium', 0)}, low={summary.get('low', 0)}\n\n"
            f"DEFECT CLASS GUIDE:\n"
            f"  D00 = Longitudinal Crack (crack sealing, moderate risk)\n"
            f"  D10 = Transverse Crack (crack sealing, moderate risk)\n"
            f"  D20 = Alligator Crack (resurfacing needed, high structural risk)\n"
            f"  D40 = Pothole (immediate danger, highest public safety risk)\n\n"
            f"PRIORITY RULES:\n"
            f"  - D40 + severity=high  → Critical\n"
            f"  - D20 + severity=high  → Critical\n"
            f"  - D40 + severity=medium → High\n"
            f"  - D20 + severity=medium → High\n"
            f"  - D00/D10 + high       → High\n"
            f"  - D00/D10 + medium     → Medium\n"
            f"  - anything + low       → Low\n\n"
            f"OUTPUT: A structured list of prioritised repairs with counts per "
            f"priority level (Critical, High, Medium, Low) and a brief reasoning "
            f"for the top-priority items."
        ),
        expected_output=(
            "The priority counts (Critical, High, Medium, Low) as integers "
            "that sum to the total defect count, plus a 1-2 sentence summary "
            "of the top-priority items. Return only the required fields."
        ),
        agent=priority_agent,
        output_pydantic=PriorityBreakdown,
    )

    # ── Task 2: Budget Allocation ──────────────────────────────────────────
    cost_reference = (
        "REPAIR COST REFERENCE (base cost × severity multiplier):\n"
        "  D00 Crack sealing:  ₹150 × (low=1.0, medium=1.4, high=2.0)\n"
        "  D10 Crack sealing:  ₹150 × multiplier\n"
        "  D20 Resurfacing:    ₹900 × multiplier\n"
        "  D40 Pothole patching: ₹350 × multiplier"
    )

    budget_task = Task(
        description=(
            f"Using the priority analysis from the previous task, allocate the "
            f"available budget across repairs.\n\n"
            f"AVAILABLE BUDGET: ₹{budget:,.0f}\n"
            f"NUMBER OF CREWS: {num_crews}\n\n"
            f"{cost_reference}\n\n"
            f"RULES:\n"
            f"  - Fund all Critical items first\n"
            f"  - Then High, then Medium, then Low — stop when budget is 90% used\n"
            f"  - Keep ₹{budget * 0.1:,.0f} (10%) in reserve for emergencies\n"
            f"  - List deferred items clearly with estimated cost\n\n"
            f"OUTPUT: Total estimated cost of selected repairs, items funded per "
            f"priority level, items deferred, and reserve amount remaining."
        ),
        expected_output=(
            "The funded repair count, deferred repair count, the emergency "
            "reserve amount kept back, and a 1-2 sentence summary of the "
            "funding decision. Return only the required fields."
        ),
        agent=budget_agent,
        output_pydantic=BudgetAllocation,
    )

    # ── Task 3: Repair Schedule ────────────────────────────────────────────
    weather_note = (
        f"CURRENT WEATHER CONTEXT:\n{weather_context}\n\n"
        if weather_context
        else "WEATHER: No live weather data available — assume dry conditions.\n\n"
    )

    schedule_task = Task(
        description=(
            f"Create a practical repair schedule for the funded repairs.\n\n"
            f"{weather_note}"
            f"CREWS AVAILABLE: {num_crews}\n\n"
            f"SCHEDULING RULES:\n"
            f"  - Pothole patching (D40): can proceed in light rain, 1 day per repair\n"
            f"  - Crack sealing (D00/D10): requires dry weather, 0.5 days per repair\n"
            f"  - Resurfacing (D20): requires 2+ consecutive dry days, 3 days per repair\n"
            f"  - Each crew can handle one repair job per day\n"
            f"  - High-traffic roads: prefer night shifts (8pm-6am)\n"
            f"  - Pad all time estimates by 20%% for equipment/logistics delays\n\n"
            f"OUTPUT: A day-by-day schedule showing which crew handles which repair, "
            f"total calendar days needed, and any weather-dependent scheduling notes."
        ),
        expected_output=(
            "A concise schedule: crew-to-repair assignments, total calendar "
            "days required, and any weather-dependent risks. Keep it brief."
        ),
        agent=schedule_agent,
    )

    # ── Task 4: Traffic Impact & Final Summary ─────────────────────────────
    traffic_task = Task(
        description=(
            f"Review the repair schedule and assess traffic impact. "
            f"Then produce the final consolidated maintenance plan.\n\n"
            f"TRAFFIC ASSESSMENT CHECKLIST:\n"
            f"  - Identify repairs on arterial/major roads (high daily_vehicles)\n"
            f"  - Flag any that should use night shifts or weekend scheduling\n"
            f"  - Estimate detour routes if lane closures are needed\n"
            f"  - Summarise overall disruption level (Low/Medium/High)\n\n"
            f"FINAL SUMMARY must include:\n"
            f"  1. Total defects analysed\n"
            f"  2. Priority breakdown (Critical/High/Medium/Low counts)\n"
            f"  3. Total estimated cost of funded repairs\n"
            f"  4. Timeline summary\n"
            f"  5. Key risks and mitigations\n"
            f"  6. Traffic disruption level and any special scheduling recommendations\n\n"
            f"Write the summary in plain English suitable for a municipal manager "
            f"who will use it to brief the field supervisors."
        ),
        expected_output=(
            "A single executive summary (4-6 sentences) for a municipal "
            "manager, covering: defects analysed, priority breakdown, "
            "timeline, key risks, and traffic disruption level. "
            "No headers or bullet lists — plain prose only."
        ),
        agent=traffic_agent,
    )

    return [priority_task, budget_task, schedule_task, traffic_task]
