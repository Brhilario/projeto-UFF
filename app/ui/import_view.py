from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QFileDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.domain.models import SeismicDataset
from app.domain.segy_reader import read_header_summary


class ImportView(QWidget):
    dataset_imported = pyqtSignal(object)  # SeismicDataset

    def __init__(self, dataset_repository, parent=None):
        super().__init__(parent)
        self._dataset_repository = dataset_repository

        self._select_button = QPushButton("Selecionar arquivo .sgy...")
        self._select_button.clicked.connect(self._on_select_file)

        self._info_label = QLabel("Nenhum arquivo selecionado.")
        self._dataset_list = QListWidget()
        self._refresh_dataset_list()

        layout = QVBoxLayout()
        layout.addWidget(self._select_button)
        layout.addWidget(self._info_label)
        layout.addWidget(QLabel("Datasets importados:"))
        layout.addWidget(self._dataset_list)
        self.setLayout(layout)

    def _on_select_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar SEG-Y", "", "SEG-Y (*.sgy *.segy)")
        if not path:
            return

        try:
            # Lê só os headers — rápido mesmo em arquivos de 25GB+
            summary = read_header_summary(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Erro ao importar", str(exc))
            return

        dataset = SeismicDataset(
            name=path.split("/")[-1],
            source_path=path,
            n_inlines=summary.n_inlines,
            n_crosslines=summary.n_crosslines,
            n_samples=summary.n_samples,
            sample_rate_ms=summary.sample_rate_ms,
        )
        self._dataset_repository.save(dataset)
        self._info_label.setText(
            f"Importado: {dataset.name} | {summary.n_traces} traços | "
            f"{summary.n_samples} amostras | Nyquist = {dataset.nyquist_hz:.1f} Hz"
        )
        self._refresh_dataset_list()
        self.dataset_imported.emit(dataset)

    def _refresh_dataset_list(self) -> None:
        self._dataset_list.clear()
        for ds in self._dataset_repository.list():
            self._dataset_list.addItem(f"{ds.name}  ({ds.id[:8]})")
