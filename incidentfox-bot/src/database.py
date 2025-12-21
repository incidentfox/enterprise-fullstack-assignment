"""Database connection and session management."""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import settings
from .models import Base

# Create engine
engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=10,
    max_overflow=20,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize database (create all tables)."""
    Base.metadata.create_all(bind=engine)

    # Lightweight schema fixups for Postgres when models evolve.
    # (create_all doesn't alter existing columns)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            try:
                # Ensure workflow_runs.run_id is BIGINT (GitHub Actions run IDs exceed 32-bit)
                data_type = conn.execute(
                    text(
                        """
                        SELECT data_type
                        FROM information_schema.columns
                        WHERE table_name = 'workflow_runs'
                          AND column_name = 'run_id'
                        """
                    )
                ).scalar()

                if data_type == "integer":
                    conn.execute(text("ALTER TABLE workflow_runs ALTER COLUMN run_id TYPE BIGINT"))
            except Exception:
                # Best-effort; if table doesn't exist yet or permissions differ, ignore.
                pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for database sessions outside FastAPI."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
