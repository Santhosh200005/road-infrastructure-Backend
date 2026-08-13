"""
Database engine + session management.

Reads DATABASE_URL from the environment, e.g.:
    postgresql+psycopg2://road_user:road_pass@localhost:5432/road_infra_db

Falls back to a local sqlite file if DATABASE_URL isn't set, purely so the
backend is runnable out of the box for local dev/demo without requiring
Postgres to be up. Production deployments MUST set DATABASE_URL.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./road_infra_dev.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Called once on startup (see main.py)."""
    # Import models so they're registered on Base.metadata before create_all
    from backend.database import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
