"""Entry point. Monta as dependências (DB, repositories, service) e sobe a UI."""
from __future__ import annotations

import sys

from PyQt5.QtWidgets import QApplication

from app.persistence.db import make_engine, make_session_factory
from app.persistence.repository import DatasetRepository, JobLogRepository, JobRepository
from app.persistence.trace_store import TraceStore
from app.domain.filter_service import FilterService
from app.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)

    engine = make_engine()
    session_factory = make_session_factory(engine)
    session = session_factory()

    dataset_repository = DatasetRepository(session)
    job_repository = JobRepository(session)
    trace_store = TraceStore()
    job_log_repository = JobLogRepository(session)

    filter_service = FilterService(
        dataset_repository,
        job_repository,
        trace_store,
        log_repository=job_log_repository,
    )

    window = MainWindow(filter_service, dataset_repository, trace_store)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
