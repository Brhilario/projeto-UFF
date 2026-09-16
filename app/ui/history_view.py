from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.domain.filter_service import FilterService
from app.domain.models import Job, JobStatus
from app.ui.spectrum_widget import SpectrumDialog

_COLUMNS = ["Job ID", "Dataset", "Status", "Cutoff (Hz)", "Ordem", "Progresso", "Ações"]


class HistoryView(QWidget):
    """
    Tela de histórico de execuções com suporte a:
    - Filtro por status e dataset (conforme contrato do PDF)
    - Visualização gráfica de QC do espectro antes/depois para jobs concluídos
    - Ação de retomar (resume) jobs cancelados ou interrompidos (Trilha de Criatividade)
    """

    resume_requested = pyqtSignal(object)  # Job

    def __init__(self, filter_service: FilterService, dataset_repository=None, trace_store=None, parent=None):
        super().__init__(parent)
        self._filter_service = filter_service
        self._dataset_repo = dataset_repository
        self._trace_store = trace_store

        # Filtro de Dataset
        self._dataset_filter = QComboBox()
        self._dataset_filter.addItem("Todos os Datasets", userData=None)
        self._dataset_filter.currentIndexChanged.connect(self._refresh_table)

        # Filtro de Status
        self._status_filter = QComboBox()
        self._status_filter.addItem("Todos os Status", userData=None)
        for status in JobStatus:
            self._status_filter.addItem(status.value, userData=status)
        self._status_filter.currentIndexChanged.connect(self._refresh_table)

        self._refresh_button = QPushButton("Atualizar")
        self._refresh_button.clicked.connect(self.refresh)

        # Tabela de histórico
        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(len(_COLUMNS) - 1, QHeaderView.ResizeToContents)

        filters_row = QHBoxLayout()
        filters_row.addWidget(QLabel("Dataset:"))
        filters_row.addWidget(self._dataset_filter)
        filters_row.addWidget(QLabel("Status:"))
        filters_row.addWidget(self._status_filter)
        filters_row.addWidget(self._refresh_button)
        filters_row.addStretch()

        layout = QVBoxLayout()
        layout.addLayout(filters_row)
        layout.addWidget(self._table)
        self.setLayout(layout)

        self.refresh()

    def refresh(self) -> None:
        """Público para ser chamado pelo MainWindow ao entrar nesta aba."""
        self._refresh_datasets_combo()
        self._refresh_table()

    def _refresh_datasets_combo(self) -> None:
        if self._dataset_repo is None:
            return

        current_id = self._dataset_filter.currentData()
        self._dataset_filter.blockSignals(True)
        self._dataset_filter.clear()
        self._dataset_filter.addItem("Todos os Datasets", userData=None)

        for ds in self._dataset_repo.list():
            self._dataset_filter.addItem(f"{ds.name} ({ds.id[:8]})", userData=ds.id)

        if current_id is not None:
            idx = self._dataset_filter.findData(current_id)
            if idx >= 0:
                self._dataset_filter.setCurrentIndex(idx)
        self._dataset_filter.blockSignals(False)

    def _refresh_table(self) -> None:
        try:
            status = self._status_filter.currentData()
            dataset_id = self._dataset_filter.currentData()
            jobs = self._filter_service.list_jobs(dataset_id=dataset_id, status=status)

            # Pre-fetch dos datasets para evitar consultas repetitivas em loop
            datasets_by_id: dict[str, str] = {}
            if self._dataset_repo is not None:
                for ds in self._dataset_repo.list():
                    datasets_by_id[ds.id] = ds.name

            self._table.setRowCount(len(jobs))
            for row, job in enumerate(jobs):
                ds_name = datasets_by_id.get(job.dataset_id, job.dataset_id[:8])

                values = [
                    job.id[:8],
                    ds_name,
                    job.status.value,
                    f"{job.cutoff_hz:.1f}",
                    str(job.order),
                    f"{job.progress_pct:.1f}%",
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    self._table.setItem(row, col, item)

                # Botões de Ação na última coluna
                action_widget = self._build_action_widget(job)
                self._table.setCellWidget(row, len(_COLUMNS) - 1, action_widget)
        except Exception as exc:
            import logging
            logging.error(f"[HistoryView] Erro ao atualizar tabela: {exc}")

    def _build_action_widget(self, job: Job) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        # Botão "Ver Espectro (QC)" se estiver concluído
        if job.status == JobStatus.COMPLETED and self._trace_store is not None and self._dataset_repo is not None:
            btn_qc = QPushButton("Ver Espectro (QC)")
            btn_qc.clicked.connect(lambda _, j=job: self._open_spectrum_qc(j))
            layout.addWidget(btn_qc)

        # Botão "Retomar" se foi interrompido/cancelado ou falhou com chunks parciais
        can_resume = (
            job.status in (JobStatus.CANCELLED, JobStatus.FAILED, JobStatus.RUNNING)
            and job.last_completed_chunk_idx is not None
        )
        if can_resume:
            btn_resume = QPushButton("Retomar")
            btn_resume.clicked.connect(lambda _, j=job: self.resume_requested.emit(j))
            layout.addWidget(btn_resume)

            btn_rollback = QPushButton("Descartar")
            btn_rollback.clicked.connect(lambda _, j=job: self._rollback_partial(j))
            layout.addWidget(btn_rollback)


        widget.setLayout(layout)
        return widget

    def _open_spectrum_qc(self, job: Job) -> None:
        dataset = self._dataset_repo.get(job.dataset_id)
        if not dataset:
            QMessageBox.warning(self, "Aviso", "Dataset original não encontrado.")
            return

        dialog = SpectrumDialog(job, dataset, self._trace_store, parent=self)
        dialog.exec_()

    def _rollback_partial(self, job: Job) -> None:
        confirm = QMessageBox.question(
            self,
            "Confirmar descarte",
            f"Deseja realmente descartar a saída parcial do job {job.id[:8]}?\n"
            "Isso impedirá a retomada deste job.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self._filter_service.rollback_job_output(job.id)
            self._refresh_table()

