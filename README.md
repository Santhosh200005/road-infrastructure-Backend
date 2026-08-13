# Road Infrastructure AI — Backend

FastAPI backend connecting Person A's YOLO detection + XGBoost degradation
models, PostgreSQL/PostGIS storage, and a CrewAI 4-agent repair-planning
workflow, to Person C's React frontend.

See `BACKEND_ANALYSIS.md` for the full integration analysis, conflict
resolution notes, and design decisions.

## Project structure

```
backend/
├── main.py                    # FastAPI app, routers, CORS, middleware
├── core config lives in env vars, read directly (see .env.example)
├── database/
│   ├── db.py                  # engine, session, init_db()
│   ├── models.py              # SQLAlchemy models (Road, Detection, Repair, AgentDecision, ...)
│   ├── schemas.py              # Pydantic request/response schemas
│   └── crud.py                # thin DB helpers
├── api/routes/
│   ├── auth.py                 # /api/auth/register, /login, /me
│   ├── detect.py                # /api/detect, /api/detections
│   ├── simulate.py              # /api/simulate, /api/simulate/series
│   ├── repairs.py               # /api/repairs (GET/POST/PATCH)
│   ├── roads.py                 # /api/roads
│   ├── analytics.py             # /api/analytics, /map, /budget
│   ├── dashboard.py             # /api/dashboard
│   └── agents.py                # /api/agents/run, /api/agents/reports
├── services/                    # business logic layer (severity mapping,
│                                 # cost estimation, budget analytics, agent orchestration)
├── ml_bridge/                    # thin wrappers around ml/ — NEVER reimplements ML
├── agents/                       # CrewAI: agents.py, tasks.py, crew.py
└── utils/                        # JWT/bcrypt security, request logging middleware

ml/                                # Person A's ML code — untouched
alembic/                           # DB migrations
tests/                             # pytest suite (52 tests, all mocked — no GPU/API key needed)
```

## Local setup (without Docker)

```bash
cd road-backend
python3 -m venv venv && source venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env   # fill in JWT_SECRET_KEY at minimum; DB defaults to local sqlite if unset

# run the API (auto-creates tables on startup against DATABASE_URL, or sqlite fallback)
uvicorn backend.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` for interactive Swagger docs.

## Running tests

```bash
PYTHONPATH=. pytest tests/ -v
```

All 52 tests pass without a live database, without model weights, and
without an OpenAI API key — YOLO, XGBoost, and CrewAI calls are mocked at
the `ml_bridge` / `agents.crew` boundary.

## Running with Docker (full stack: Postgres + backend + frontend)

```bash
cp .env.example .env   # fill in real secrets
docker compose up --build
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- Postgres (PostGIS-enabled): `localhost:5432`

**Before running detection for real:** download `best.pt` per
`ml/detection/README.md` and place it at
`ml/detection/runs/rdd2022/yolov8m_rdd-3/weights/best.pt` — it's mounted into
the container via `docker-compose.yml`'s volume mapping, not baked into the image.

## Database migrations (Alembic)

```bash
# generate a new migration after changing backend/database/models.py
DATABASE_URL=<your-postgres-url> alembic revision --autogenerate -m "description"

# apply migrations
DATABASE_URL=<your-postgres-url> alembic upgrade head
```

An initial migration (`alembic/versions/c0d309d2bd74_initial_schema.py`) is
included, covering all 7 tables.

## Environment variables

See `.env.example`. Required for full functionality:
- `DATABASE_URL` — Postgres connection string (falls back to local sqlite if unset)
- `JWT_SECRET_KEY` — auth token signing secret
- `OPENWEATHER_API_KEY` — used by `ml/simulator/weather.py` (Person A's code)
- `OPENAI_API_KEY` — required only for `POST /api/agents/run` (CrewAI); every
  other endpoint works without it

## Agent workflow

`POST /api/agents/run` (admin/engineer role required) triggers a sequential
CrewAI run: **Priority Agent → Budget Agent → Schedule Agent → Traffic
Agent**, operating on real `Detection` rows from the database. Results are
persisted to `agent_decisions` and surfaced via `GET /api/agents/reports`,
which the frontend's `AgentReports` page consumes directly.
