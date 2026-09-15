"""
Repositories: única camada que sabe converter entre dataclasses de domínio
(app/domain/models.py) e linhas ORM (models_orm.py). filter_service.py
depende só desta interface, nunca de SQLAlchemy diretamente.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.models import Job, JobLog, JobStatus, SeismicDataset
from app.persistence.models_orm import JobLogORM, JobORM, SeismicDatasetORM


class DatasetRepository:
    def __init__(self, session: Session):
        self._session = session

    def save(self, dataset: SeismicDataset) -> None:
        row = SeismicDatasetORM(
            id=dataset.id,
            name=dataset.name,
            source_path=dataset.source_path,
            n_inlines=dataset.n_inlines,
            n_crosslines=dataset.n_crosslines,
            n_samples=dataset.n_samples,
            sample_rate_ms=dataset.sample_rate_ms,
            created_at=dataset.created_at,
        )
        self._session.merge(row)
        self._session.commit()

    def get(self, dataset_id: str) -> SeismicDataset | None:
        row = self._session.get(SeismicDatasetORM, dataset_id)
        return self._to_domain(row) if row else None

    def list(self) -> list[SeismicDataset]:
        rows = self._session.query(SeismicDatasetORM).all()
        return [self._to_domain(r) for r in rows]

    @staticmethod
    def _to_domain(row: SeismicDatasetORM) -> SeismicDataset:
        return SeismicDataset(
            id=row.id,
            name=row.name,
            source_path=row.source_path,
            n_inlines=row.n_inlines,
            n_crosslines=row.n_crosslines,
            n_samples=row.n_samples,
            sample_rate_ms=row.sample_rate_ms,
            created_at=row.created_at,
        )


class JobRepository:
    def __init__(self, session: Session):
        self._session = session

    def save(self, job: Job) -> None:
        row = JobORM(
            id=job.id,
            dataset_id=job.dataset_id,
            status=job.status,
            cutoff_hz=job.cutoff_hz,
            order=job.order,
            progress_pct=job.progress_pct,
            output_path=job.output_path,
            error_message=job.error_message,
            last_completed_chunk_idx=job.last_completed_chunk_idx,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )
        self._session.merge(row)
        self._session.commit()

    def get(self, job_id: str) -> Job | None:
        row = self._session.get(JobORM, job_id)
        return self._to_domain(row) if row else None

    def list(self, dataset_id: str | None = None, status: JobStatus | None = None) -> list[Job]:
        query = self._session.query(JobORM)
        if dataset_id is not None:
            query = query.filter(JobORM.dataset_id == dataset_id)
        if status is not None:
            query = query.filter(JobORM.status == status)
        return [self._to_domain(r) for r in query.all()]

    @staticmethod
    def _to_domain(row: JobORM) -> Job:
        return Job(
            id=row.id,
            dataset_id=row.dataset_id,
            status=row.status,
            cutoff_hz=row.cutoff_hz,
            order=row.order,
            progress_pct=row.progress_pct,
            output_path=row.output_path,
            error_message=row.error_message,
            last_completed_chunk_idx=row.last_completed_chunk_idx,
            created_at=row.created_at,
            started_at=row.started_at,
            finished_at=row.finished_at,
        )


class JobLogRepository:
    """Repositório para persistência e consulta dos logs de execução de jobs."""

    def __init__(self, session: Session):
        self._session = session

    def save(self, log: JobLog) -> None:
        row = JobLogORM(
            job_id=log.job_id,
            timestamp=log.timestamp,
            level=log.level,
            message=log.message,
        )
        self._session.add(row)
        self._session.commit()

    def list_for_job(self, job_id: str) -> list[JobLog]:
        rows = (
            self._session.query(JobLogORM)
            .filter(JobLogORM.job_id == job_id)
            .order_by(JobLogORM.timestamp.asc())
            .all()
        )
        return [
            JobLog(
                id=r.id,
                job_id=r.job_id,
                timestamp=r.timestamp,
                level=r.level,
                message=r.message,
            )
            for r in rows
        ]
