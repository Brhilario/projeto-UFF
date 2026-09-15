from __future__ import annotations

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.models import JobLog
from app.persistence.models_orm import Base
from app.persistence.repository import JobLogRepository


@pytest.fixture
def in_memory_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = session_factory()
    yield session
    session.close()


def test_job_log_repository_saves_and_retrieves_logs(in_memory_session):
    repo = JobLogRepository(in_memory_session)

    log1 = JobLog(job_id="job-123", level="INFO", message="Job iniciado", timestamp=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc))
    log2 = JobLog(job_id="job-123", level="WARNING", message="Aviso de teste", timestamp=datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc))
    log3 = JobLog(job_id="outro-job", level="INFO", message="Outro job", timestamp=datetime(2026, 1, 1, 10, 10, tzinfo=timezone.utc))

    repo.save(log1)
    repo.save(log2)
    repo.save(log3)

    logs_job123 = repo.list_for_job("job-123")
    assert len(logs_job123) == 2
    assert logs_job123[0].message == "Job iniciado"
    assert logs_job123[1].level == "WARNING"

    logs_other = repo.list_for_job("outro-job")
    assert len(logs_other) == 1
    assert logs_other[0].message == "Outro job"
