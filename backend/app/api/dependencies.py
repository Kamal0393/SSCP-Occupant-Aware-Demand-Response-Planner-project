"""Shared API dependency providers, wired to infrastructure at the boundary."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.infrastructure.db.session import SessionLocal, initialize_database


def get_db() -> Generator[Session, None, None]:
    initialize_database()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
