from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.domain.exceptions import DomainError
from app.domain.filter_service import MAX_ORDER, MIN_ORDER, FilterService


class FilterConfigView(QWidget):
    job_created = pyqtSignal(object)  # Job

    def __init__(self, filter_service: FilterService, dataset_repository, parent=None):
        super().__init__(parent)
        self._filter_service = filter_service
        self._dataset_repository = dataset_repository

        self._dataset_combo = QComboBox()
        self._dataset_combo.currentIndexChanged.connect(self._on_dataset_changed)

        self._nyquist_label = QLabel("Selecione um dataset para ver a frequência de Nyquist.")

        self._cutoff_spin = QDoubleSpinBox()
        self._cutoff_spin.setDecimals(1)
        self._cutoff_spin.setRange(0.1, 10000.0)
        self._cutoff_spin.setValue(60.0)

        self._order_spin = QSpinBox()
        self._order_spin.setRange(MIN_ORDER, MAX_ORDER)
        self._order_spin.setValue(4)

        self._run_button = QPushButton("Executar")
        self._run_button.clicked.connect(self._on_run_clicked)

        form = QFormLayout()
        form.addRow("Dataset:", self._dataset_combo)
        form.addRow("", self._nyquist_label)
        form.addRow("Frequência de corte (Hz):", self._cutoff_spin)
        form.addRow("Ordem do filtro:", self._order_spin)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(self._run_button)
        self.setLayout(layout)

        self.refresh_datasets()  # popula já no início, caso já existam datasets

    def refresh_datasets(self) -> None:
        """
        Repopula o combo com os datasets atuais. Público de propósito: deve
        ser chamado pelo MainWindow sempre que um novo dataset for importado
        (via ImportView.dataset_imported) ou quando esta aba ganhar foco —
        sem isso, um dataset importado depois da janela abrir nunca aparece aqui.
        """
        current_id = self._dataset_combo.currentData()
        self._dataset_combo.blockSignals(True)
        self._dataset_combo.clear()
        for ds in self._dataset_repository.list():
            self._dataset_combo.addItem(f"{ds.name} ({ds.id[:8]})", userData=ds.id)
        self._dataset_combo.blockSignals(False)

        # tenta manter a seleção anterior se o dataset ainda existir
        if current_id is not None:
            idx = self._dataset_combo.findData(current_id)
            if idx >= 0:
                self._dataset_combo.setCurrentIndex(idx)
        self._on_dataset_changed(self._dataset_combo.currentIndex())

    def _on_dataset_changed(self, _index: int) -> None:
        dataset_id = self._dataset_combo.currentData()
        if dataset_id is None:
            self._nyquist_label.setText("Nenhum dataset selecionado.")
            return
        dataset = self._dataset_repository.get(dataset_id)
        if dataset is None:
            return
        self._nyquist_label.setText(f"Nyquist deste dataset: {dataset.nyquist_hz:.1f} Hz")
        self._cutoff_spin.setMaximum(max(0.1, dataset.nyquist_hz - 0.1))

    def _on_run_clicked(self) -> None:
        dataset_id = self._dataset_combo.currentData()
        if dataset_id is None:
            QMessageBox.warning(self, "Aviso", "Nenhum dataset importado.")
            return

        try:
            job = self._filter_service.create_filter_job(
                dataset_id=dataset_id,
                cutoff_hz=self._cutoff_spin.value(),
                order=self._order_spin.value(),
            )
        except DomainError as exc:
            QMessageBox.critical(self, "Parâmetros inválidos", str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - captura erros não previstos
            QMessageBox.critical(self, "Erro inesperado", str(exc))
            return

        self.job_created.emit(job)
