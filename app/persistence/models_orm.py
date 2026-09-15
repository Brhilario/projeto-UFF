"""
Tabelas SQLAlchemy. Mapeiam 1:1 os campos de app/domain/models.py, mas
ficam em arquivo separado para manter o domínio livre de detalhes de ORM
(SoC: domínio não deve saber que existe SQLAlchemy).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.models import JobStatus


class Base(DeclarativeBase):
    pass


class SeismicDatasetORM(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str]
    source_path: Mapped[str]
    n_inlines: Mapped[int]
    n_crosslines: Mapped[int]
    n_samples: Mapped[int]
    sample_rate_ms: Mapped[float]
    created_at: Mapped[datetime]


class JobORM(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"))
    status: Mapped[JobStatus] = mapped_column(SAEnum(JobStatus))
    cutoff_hz: Mapped[float]
    order: Mapped[int]
    progress_pct: Mapped[float] = mapped_column(default=0.0)
    output_path: Mapped[str | None] = mapped_column(default=None)
    error_message: Mapped[str | None] = mapped_column(default=None)
    last_completed_chunk_idx: Mapped[int | None] = mapped_column(default=None)
    created_at: Mapped[datetime]
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)


class JobLogORM(Base):
    """Log de execução persistido por job (item opcional)."""
    __tablename__ = "job_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    timestamp: Mapped[datetime]
    level: Mapped[str]  # INFO, WARNING, ERROR
    message: Mapped[str]
