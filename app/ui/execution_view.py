from __future__ import annotations

from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import (
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.domain.filter_service import FilterService
from app.domain.models import Job
from app.workers.filter_worker import FilterWorker


class ExecutionView(QWidget):
    """
    Critério de aceite chave desta tela: a janela precisa continuar
    respondendo a cliques/arrasto DURANTE toda a execução — por isso
    o processamento roda em FilterWorker numa QThread separada.
    """

    def __init__(self, filter_service: FilterService, parent=None):
        super().__init__(parent)
        self._filter_service = filter_service
        self._thread: QThread | None = None
        self._worker: FilterWorker | None = None

        self._status_label = QLabel("Nenhum job em execução.")
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)

        self._cancel_button = QPushButton("Cancelar")
        self._cancel_button.setEnabled(False)
        self._cancel_button.clicked.connect(self._on_cancel_clicked)

        layout = QVBoxLayout()
        layout.addWidget(self._status_label)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._cancel_button)
        self.setLayout(layout)

    def start_job(self, job: Job) -> None:
        is_resumed = job.last_completed_chunk_idx is not None
        status_text = (
            f"Retomando job {job.id[:8]} (a partir de {job.progress_pct:.0f}%)..."
            if is_resumed
            else f"Executando job {job.id[:8]}..."
        )
        self._status_label.setText(status_text)
        self._progress_bar.setValue(int(job.progress_pct))
        self._cancel_button.setEnabled(True)

        self._thread = QThread()
        self._worker = FilterWorker(self._filter_service, job.id)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)

        self._thread.start()

    def _on_progress(self, pct: float) -> None:
        self._progress_bar.setValue(int(pct))

    def _on_finished(self, job: Job) -> None:
        if job.status.value == "FAILED":
            self._status_label.setText(f"Job {job.id[:8]} FALHOU: {job.error_message}")
        elif job.status.value == "CANCELLED":
            self._status_label.setText(f"Job {job.id[:8]} cancelado: {job.error_message}")
        else:
            self._status_label.setText(f"Job {job.id[:8]} finalizado: {job.status.value}")
        self._cancel_button.setEnabled(False)

    def _on_error(self, message: str) -> None:
        self._status_label.setText(f"Erro inesperado: {message}")
        self._cancel_button.setEnabled(False)

    def _on_cancel_clicked(self) -> None:
        if self._worker is not None:
            self._filter_service.cancel_job(self._worker._job_id, self._worker.cancel_token)
            self._cancel_button.setEnabled(False)
