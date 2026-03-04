# =============================================================================
# app/core/database.py — SQLite Database Configuration (SQLAlchemy 2.x)
# =============================================================================
# PURPOSE:
#   Single source of truth for the database engine, session factory, and
#   ORM base class.  Every module that needs DB access imports from here.
#
# WHY SQLite?
#   • Zero installation — it's built into Python's standard library.
#   • No external server — the database is a single file (anpr.db).
#   • Perfect for development, prototyping, and single-user production.
#   • Swap to PostgreSQL later by changing only DATABASE_URL.
#
# WHY check_same_thread=False?
#   SQLite's default is to disallow sharing a connection across threads.
#   FastAPI uses a thread pool for sync endpoints, so a single request
#   may be served on a different thread than the one that opened the
#   connection.  Setting check_same_thread=False tells Python's sqlite3
#   driver to relax this check.  SQLAlchemy's connection pooling +
#   scoped sessions already prevent true concurrent writes.
#
# WHY DEPENDENCY INJECTION (get_db)?
#   • Each request gets its own session → no cross-request leaks.
#   • The `finally` block guarantees the session is closed even on errors.
#   • Easy to override in tests (just swap the dependency).
#   • FastAPI's `Depends()` handles the lifecycle automatically.
# =============================================================================

import logging
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker, declarative_base

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database URL — from settings (which reads .env / env vars)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# If the settings DATABASE_URL is a relative SQLite path, make it absolute
# relative to the backend project root.
_settings_url = settings.DATABASE_URL
if _settings_url.startswith("sqlite:///./"):
    _relative = _settings_url.replace("sqlite:///./", "")
    DATABASE_URL = f"sqlite:///{_PROJECT_ROOT / _relative}"
else:
    DATABASE_URL = _settings_url

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
# echo=True  → logs every SQL statement (disable in production)
# connect_args → required for SQLite + multi-thread (see docstring above)
# ---------------------------------------------------------------------------
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,  # Verify connection is alive before using it
)


# ---------------------------------------------------------------------------
# Enable SQLite WAL mode + foreign keys on every new connection
# ---------------------------------------------------------------------------
# WAL (Write-Ahead Logging) allows concurrent reads while a write is
# in progress — dramatically improves performance for read-heavy workloads.
# ---------------------------------------------------------------------------
@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


# ---------------------------------------------------------------------------
# Session Factory
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # Keep attributes accessible after commit
)

# ---------------------------------------------------------------------------
# Declarative Base — all ORM models inherit from this
# ---------------------------------------------------------------------------
Base = declarative_base()


# ---------------------------------------------------------------------------
# Dependency: get_db
# ---------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session.

    Usage in routes:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...

    The session is automatically committed on success or rolled back
    on exception, then closed in the `finally` block.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


logger.info("Database configured: %s", DATABASE_URL)
