from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from app.persistence.models_orm import Base

DEFAULT_DB_PATH = "giecar_seismic.db"


def make_engine(db_path: str = DEFAULT_DB_PATH):
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30.0},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


def make_session_factory(engine) -> scoped_session:
    return scoped_session(sessionmaker(bind=engine, expire_on_commit=False, future=True))

