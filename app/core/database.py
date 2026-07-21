"""Singleton SQLAlchemy engine/session provider (see feedback-prompts-and-singleton-conventions)."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


class DatabaseSessionProvider:
    """Process-wide engine + session factory, built once and reused."""

    _instance: "DatabaseSessionProvider | None" = None
    _engine: Engine
    _session_factory: sessionmaker[Session]

    def __new__(cls) -> "DatabaseSessionProvider":
        if cls._instance is None:
            instance = super().__new__(cls)
            settings = get_settings()
            instance._engine = create_engine(settings.database_url, pool_pre_ping=True)
            instance._session_factory = sessionmaker(bind=instance._engine, expire_on_commit=False)
            cls._instance = instance
        return cls._instance

    @property
    def engine(self) -> Engine:
        return self._engine

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Yield a session, committing on success and rolling back on error."""
        db_session = self._session_factory()
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise
        finally:
            db_session.close()
