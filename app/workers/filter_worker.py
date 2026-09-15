"""
Ponte entre a camada de negócio (domain/filter_service.py) e a UI Qt.
Este é o ÚNICO lugar onde domain e PyQt5 se encontram.

Uso típico em main_window.py:

    self.thread = QThread()
    self.worker = FilterWorker(filter_service, job.id)
    self.worker.moveToThread(self.thread)

    self.thread.started.connect(self.worker.run)
    self.worker.progress.connect(self.progress_bar.setValue)
    self.worker.finished.connect(self.on_job_finished)
    self.worker.error.connect(self.on_job_error)
    self.worker.finished.connect(self.thread.quit)

    self.thread.start()

    # no botão Cancelar:
    self.worker.cancel_token.set()
"""
from __future__ import annotations

from PyQt5.QtCore import QObject, pyqtSignal

from app.domain.filter_service import FilterService
from app.workers.cancel_token import CancelToken


class FilterWorker(QObject):
    progress = pyqtSignal(float)      # pct 0-100
    finished = pyqtSignal(object)     # Job final (COMPLETED/FAILED/CANCELLED)
    error = pyqtSignal(str)           # erro inesperado fora do fluxo normal do Job

    def __init__(self, filter_service: FilterService, job_id: str):
        super().__init__()
        self._filter_service = filter_service
        self._job_id = job_id
        self.cancel_token = CancelToken()

    def run(self) -> None:
        """
        Executado na thread de background (via QThread.started). Nunca
        toca em widgets diretamente — só emite sinais, que são entregues
        ao thread principal via queued connection automática do Qt.
        """
        try:
            job = self._filter_service.run_filter_job(
                job_id=self._job_id,
                progress_callback=self.progress.emit,
                cancel_token=self.cancel_token,
            )
            self.finished.emit(job)
        except Exception as exc:  # noqa: BLE001 - erro fora do fluxo normal do Job
            self.error.emit(str(exc))

