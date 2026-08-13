# BACKEND_ANALYSIS.md

## 1. What already existed

The uploaded ZIP (`road-infrastructure-ai-integrated.zip`) already contained a
**working first draft** of Person B's backend, built by a previous pass, plus
Person A's real ML code and Person C's Docker/nginx scaffolding. This is not
a from-scratch build — it's a completion pass on top of that draft, focused on
closing every gap between what existed and what the frontend (`frontend.zip`)
and the Person B PDF actually require.

What was already correct and preserved unmodified:
- `ml/detection/infer.py` → `detect_defects(image_path)` — real YOLOv8 wrapper
- `ml/simulator/simulate.py` → `forecast_severity(inputs, days)` — real XGBoost wrapper
- `ml/simulator/degradation_model.py`, `ml/simulator/weather.py`
- `backend/ml_bridge/*` — thin, non-duplicating wrappers around the above
- `backend/database/models.py`, `crud.py`, `db.py` (base schema)
- `backend/services/detection_service.py`, `repair_service.py`
- `backend/utils/security.py` (JWT + bcrypt), `logging_middleware.py`
- `backend/api/routes/auth.py`, `detect.py`, `roads.py`, `dashboard.py`, `repairs.py`
- `backend/Dockerfile`, root `docker-compose.yml`

## 2. Person A integration points (confirmed by reading the actual code)

| Function | File | Signature | Notes |
|---|---|---|---|
| `detect_defects(image_path)` | `ml/detection/infer.py` | returns `{"detections":[{"class","confidence","bbox","severity"}], "count"}` | Loads `runs/rdd2022/yolov8m_rdd-3/weights/best.pt` **on every call** — no caching in Person A's code. `ml_bridge/yolo_runner.py` calls this unmodified; it does not reimplement inference. |
| `forecast_severity(inputs, days=30)` | `ml/simulator/simulate.py` | takes 7-key dict (`FEATURE_ORDER`), returns `{"current_severity","forecast_days","predicted_severity"}` | Model is 30-day-native; for other `days` values the function itself does a linear scale — this is Person A's behavior, not something the backend changes. |
| `calculate_daily_delta(...)` | `ml/simulator/degradation_model.py` | used only internally by `simulator_service._annual_degradation_rate()` to estimate a heuristic remaining-life figure | Reused, not duplicated. |
| `get_forecast(lat, lon, days)` | `ml/simulator/weather.py` | OpenWeatherMap wrapper, needs `OPENWEATHER_API_KEY` | Not currently wired into an API route — it's available for the agent service's `weather_context` input if a future iteration wants live weather instead of a manually-supplied string. |

Neither YOLO nor XGBoost logic was rewritten anywhere. `backend/ml_bridge/*`
only adds: path setup, missing-file → `RuntimeError` translation, and timing
instrumentation.

## 3. Person C (frontend) API contract — read from `src/services/api.js`

`api.js` explicitly marks several endpoints `PERSON B ACTION REQUIRED` because
they weren't yet confirmed. Here's what was resolved and how:

| Frontend call | Method/Path | Resolution |
|---|---|---|
| `runDetection(file)` | `POST /api/detect`, `multipart/form-data`, field `file` | Implemented exactly. Returns `{status, detections[], count, image_url, detection_ids[]}`. |
| `fetchRepairs()` / `createRepair()` / `updateRepair()` | `GET/POST /api/repairs`, `PATCH /api/repairs/:id` | Field names confirmed: `{id, road_id, detection_id, defect_class, priority, status, recommended_repair, estimated_cost, time_required_days, assigned_crew, scheduled_date, completed_date, created_at}`. |
| `fetchRoads()` | `GET /api/roads` | Returns full `RoadOut` objects (not just `{id,name,lat,lon}` as the frontend comment guessed) — richer shape is backward compatible since the frontend only reads `.id`/`.name` in the dropdown. |
| `fetchMapDefects()` | `GET /api/analytics/map` | **Flat array**, not GeoJSON (frontend comment already assumed the flat-array fallback is safe — confirmed as the actual implementation). |
| `fetchBudgetAnalytics()` | `GET /api/analytics/budget` | **This endpoint did not exist before this pass.** Implemented from scratch to match the frontend's own mock shape in `Analytics.jsx` exactly: `{monthly:[{month,allocated,spent}], byType:[{type,value}], cumulative:[{month,spend,budgetLimit}]}`, computed from real `Repair` rows (`estimated_cost`, `status`, `completed_date`). |
| `runSimulation(inputs, dayValues)` | `POST /api/simulate` — called once per `days` value | **Conflict found and fixed**, see §4. |
| `runAgents(payload)` | `POST /api/agents/run` | **Did not exist before this pass.** Implemented as a CrewAI 4-agent sequential workflow (§5). |
| `fetchAgentReports()` | `GET /api/agents/reports` | **Did not exist before this pass.** New `AgentDecision` table + route; response shape matches `AgentReports.jsx` field-for-field (`id, date, defects_processed, priority_breakdown, total_estimated_cost, reasoning`). |
| `login(credentials)` | `POST /api/auth/login` | Implemented exactly: `{username,password} → {access_token, token_type}`. |

## 4. Conflict: frontend sends `days`, backend expected `forecast_days`

**The bug:** `api.js`'s `runSimulation()` posts `{ ...inputs, days }`, but the
existing `SimulateRequest` schema only accepted `forecast_days`. Pydantic
would have silently ignored the unknown `days` field and always used the
default `forecast_days=30`, breaking the frontend's 0–180 day chart (every
point would show the same 30-day prediction).

**Resolution:** `SimulateRequest` now accepts both `forecast_days` and an
optional `days` alias, with a `model_validator` that normalises `days` →
`forecast_days` when present. This satisfies the frontend's actual request
body without asking Person C to change already-shipped code, and without
breaking the Person B PDF's `forecast_days` naming. A `POST /api/simulate/series`
endpoint was also added so the frontend *could* switch to one call instead of
seven, but the primary fix keeps the existing per-call pattern working.

## 5. Agentic AI — what the PDF required vs. what existed

The Person B PDF calls for a CrewAI workflow with **Priority, Budget,
Schedule, and Traffic agents**, operating on real project data, with results
persisted to the database. None of this existed in the uploaded ZIP — no
`backend/agents/` package, no `AgentDecision` model, no `/api/agents/*` routes.

Built in this pass:
- `backend/agents/agents.py` — 4 `crewai.Agent` definitions with roles/goals/backstories matching the PDF
- `backend/agents/tasks.py` — 4 sequential `crewai.Task`s that inject **real** defect data (pulled from the `detections` table), real cost-reference tables (same numbers as `repair_service.py`, kept consistent), and the caller's budget/crew count
- `backend/agents/crew.py` — `run_crew()`: assembles `Crew(process=Process.sequential)`, kicks it off, parses the priority breakdown and total cost out of the final agent's text output
- `backend/services/agent_service.py` — DB-facing orchestration: builds the damage report from real `Detection` rows, calls `run_crew`, persists an `AgentDecision` row
- `backend/database/models.py::AgentDecision` — new table, one row per run
- `backend/api/routes/agents.py` — `POST /api/agents/run` (admin/engineer only), `GET /api/agents/reports` (any authenticated role)

Design choices:
- **LLM**: `gpt-4o-mini` via `langchain-openai`, needs `OPENAI_API_KEY`. Missing
  key → `RuntimeError` → route returns **503**, not 500, so the frontend can
  distinguish "not configured" from "actually broke."
- **Determinism/testability**: `agents/crew.py` is the only module that talks
  to CrewAI/OpenAI. Tests mock `backend.agents.crew.run_crew` entirely — no
  real API key or network call is required to run the test suite.
- **No hardcoded demo data**: `_build_damage_report()` in `agent_service.py`
  pulls actual `Detection` rows from the database, not a fixture.

## 6. Database design

Existing tables (unmodified): `users`, `roads`, `detections`,
`simulation_results`, `repairs`, `request_logs`.

New table: `agent_decisions` (§5).

**PostGIS note:** the PDF lists PostGIS as a requirement. The existing `Road`
model uses plain `Float` `latitude`/`longitude` columns rather than a PostGIS
`geometry(Point)` column. This was **kept as-is** rather than migrated,
because:
1. The frontend's map/analytics code consumes flat `{latitude, longitude}`
   numbers directly — switching to a PostGIS geometry column would require
   either GeoAlchemy2 + WKT (de)serialization in every route touching `Road`,
   or a parallel plain-float "view," for no functional benefit at this
   feature set's current scale (point markers, no radius/polygon queries).
2. Nothing in Person C's frontend or Person B's PDF endpoints actually
   requires a spatial query (e.g., "roads within 5km") today.

The `docker-compose.yml` Postgres image was switched to `postgis/postgis:16-3.4-alpine`
(PostGIS extension available in the DB) so that a future migration to real
geometry columns / spatial indexes is a pure Alembic migration, not an
infrastructure change. This is a deliberate middle ground: PostGIS is
available per the spec, without forcing a schema change that breaks the
current frontend contract.

## 7. Dependency analysis

Added to `backend/requirements.txt` (nothing else — no speculative packages):
- `crewai`, `langchain-openai` — required by the new agent workflow
- `pytest`, `httpx` — required to run the test suite
- `bcrypt==4.0.1` pinned explicitly — `passlib==1.7.4`'s bcrypt backend
  detection breaks against `bcrypt>=4.1` (raises a spurious
  "password cannot be longer than 72 bytes" error on its own internal
  self-test, unrelated to any real password). This is a known passlib/bcrypt
  compatibility issue, fixed here by pinning, not by touching auth logic.

Nothing was added "because it's popular" — every new package is imported by
name somewhere in `backend/agents/` or `tests/`.

## 8. CORS / Docker

`FRONTEND_ORIGINS` already covered both `localhost:5173` (Vite dev) and
`localhost:3000` (dockerized build) — matches `frontend/nginx.conf`'s
`proxy_pass http://backend:8000` and `frontend/Dockerfile`'s Vite build.
No changes needed. `docker-compose.yml` gained two new backend env vars
(`OPENAI_API_KEY`, `MONTHLY_BUDGET_LIMIT`) for the new features — no port or
service changes.

## 9. Summary of every gap closed in this pass

1. `POST /api/agents/run` — implemented (was missing entirely)
2. `GET /api/agents/reports` — implemented (was missing entirely)
3. `AgentDecision` model + CRUD — implemented (was missing entirely)
4. `GET /api/analytics/budget` — implemented (was missing entirely)
5. `SimulateRequest` `days`/`forecast_days` mismatch — fixed
6. Full test suite (52 tests, all passing) — added (was missing entirely)
7. Alembic migration scaffolding (`alembic.ini`, `alembic/env.py`) — added (was missing entirely)
8. `bcrypt` version pin — fixed (blocked every authenticated test/request)
9. PostGIS-enabled Postgres image in Docker Compose — added, schema-compatible, non-breaking
