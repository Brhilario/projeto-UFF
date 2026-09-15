"""
Widget de visualização comparativa do espectro de amplitude antes e depois
do filtro (QC visual - item opcional e fluxo da especificação).

Utiliza matplotlib embutido em PyQt5 via FigureCanvasQTAgg.
Aparência nativa, sem estilizações customizadas.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)
import numpy as np
import segyio

from app.domain.butterworth import amplitude_spectrum
from app.domain.models import Job, SeismicDataset
from app.persistence.trace_store import TraceStore


class SpectrumDialog(QDialog):
    """
    Diálogo para inspeção de QC de um Job finalizado.
    Compara o espectro de Fourier do traço original (.sgy) contra o traço filtrado (.h5).
    """

    def __init__(
        self,
        job: Job,
        dataset: SeismicDataset,
        trace_store: TraceStore,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"QC de Espectro — Job {job.id[:8]} ({dataset.name})")
        self.resize(800, 550)

        self._job = job
        self._dataset = dataset
        self._trace_store = trace_store

        # Layout superior de controle de traço
        control_layout = QHBoxLayout()
        control_layout.addWidget(QLabel("Índice do Traço para inspeção:"))

        self._trace_spin = QSpinBox()
        total_traces = dataset.n_traces
        self._trace_spin.setRange(0, max(0, total_traces - 1))
        self._trace_spin.setValue(0)
        self._trace_spin.valueChanged.connect(self._plot_spectrum)
        control_layout.addWidget(self._trace_spin)

        self._info_label = QLabel(
            f"Frequência de Corte: {job.cutoff_hz:.1f} Hz | "
            f"Ordem: {job.order} | Nyquist: {dataset.nyquist_hz:.1f} Hz"
        )
        control_layout.addWidget(self._info_label)
        control_layout.addStretch()

        # Canvas Matplotlib
        self._figure = Figure(figsize=(8, 4), tight_layout=True)
        self._canvas = FigureCanvas(self._figure)
        self._ax = self._figure.add_subplot(111)

        # Botão fechar
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.accept)
        bottom_layout.addWidget(close_button)

        main_layout = QVBoxLayout()
        main_layout.addLayout(control_layout)
        main_layout.addWidget(self._canvas)
        main_layout.addLayout(bottom_layout)
        self.setLayout(main_layout)

        # Plota o primeiro traço
        self._plot_spectrum()

    def _plot_spectrum(self) -> None:
        trace_idx = self._trace_spin.value()
        self._ax.clear()

        try:
            # 1) Leitura do traço original do SEG-Y
            with segyio.open(self._dataset.source_path, "r", ignore_geometry=True) as f:
                if trace_idx >= f.tracecount:
                    QMessageBox.warning(self, "Aviso", "Índice de traço inválido no SEG-Y.")
                    return
                raw_trace = np.array(f.trace[trace_idx], dtype=np.float32)

            # 2) Leitura do traço filtrado do HDF5
            filtered_trace = self._trace_store.read_full_trace(self._job.id, trace_idx)

            # 3) Cálculo do espectro de amplitude
            freqs_raw, amp_raw = amplitude_spectrum(raw_trace, self._dataset.sample_rate_ms)
            freqs_filt, amp_filt = amplitude_spectrum(filtered_trace, self._dataset.sample_rate_ms)

            # 4) Desenha curvas
            self._ax.plot(freqs_raw, amp_raw, label="Original (Bruto)", color="#1f77b4", alpha=0.7)
            self._ax.plot(freqs_filt, amp_filt, label="Filtrado (Butterworth)", color="#2ca02c", linewidth=1.5)
            self._ax.axvline(
                self._job.cutoff_hz,
                color="red",
                linestyle="--",
                linewidth=1.5,
                label=f"Frequência de Corte ({self._job.cutoff_hz:.1f} Hz)",
            )

            self._ax.set_title(f"Espectro de Amplitude — Traço #{trace_idx}")
            self._ax.set_xlabel("Frequência (Hz)")
            self._ax.set_ylabel("Amplitude")
            self._ax.set_xlim(0, self._dataset.nyquist_hz)
            self._ax.grid(True, linestyle=":", alpha=0.6)
            self._ax.legend(loc="upper right")

            self._canvas.draw()

        except Exception as exc:
            self._ax.text(
                0.5,
                0.5,
                f"Erro ao carregar dados do traço: {exc}",
                horizontalalignment="center",
                verticalalignment="center",
                transform=self._ax.transAxes,
                color="red",
            )
            self._canvas.draw()
