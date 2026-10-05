"""Database engine, sessions, and schema initialization."""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.infrastructure.db.models import Base


def create_database_engine(database_url: str | None = None, *, echo: bool | None = None) -> Engine:
    url = database_url or settings.DATABASE_URL
    options: dict = {"echo": settings.DATABASE_ECHO if echo is None else echo}
    if url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    database_engine = create_engine(url, **options)
    if url.startswith("sqlite"):
        @event.listens_for(database_engine, "connect")
        def enable_foreign_keys(connection, _record) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return database_engine


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def initialize_database(target_engine: Engine | None = None) -> None:
    """Create tables for local/demo use. Production schema changes belong in migrations."""
    Base.metadata.create_all(target_engine or engine)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
