from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.persistence.models_orm import Base

DEFAULT_DB_PATH = "giecar_seismic.db"


def make_engine(db_path: str = DEFAULT_DB_PATH):
    # TODO: trocar por Alembic em produção; create_all() é ok para o MVP da prova
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    return engine


def make_session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
