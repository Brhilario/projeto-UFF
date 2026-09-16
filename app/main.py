"""Entry point. Monta as dependências (DB, repositories, service) e sobe a UI."""
from __future__ import annotations

import logging
import sys
import traceback

from PyQt5.QtWidgets import QApplication

from app.domain.filter_service import FilterService
from app.persistence.db import make_engine, make_session_factory
from app.persistence.repository import DatasetRepository, JobLogRepository, JobRepository
from app.persistence.trace_store import TraceStore
from app.ui.main_window import MainWindow


def _global_excepthook(exc_type, exc_value, exc_tb):
    logging.error("Exceção não tratada capturada:", exc_info=(exc_type, exc_value, exc_tb))


def main() -> None:
    sys.excepthook = _global_excepthook
    app = QApplication(sys.argv)


    engine = make_engine()
    # scoped_session gerencia sessões thread-local automaticamente
    session_scoped = make_session_factory(engine)

    dataset_repository = DatasetRepository(session_scoped)
    job_repository = JobRepository(session_scoped)
    trace_store = TraceStore()
    job_log_repository = JobLogRepository(session_scoped)

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
