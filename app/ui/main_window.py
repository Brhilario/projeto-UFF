"""
Janela principal. Monta as 4 telas exigidas em QTabWidget e injeta o
FilterService (vindo de main.py) em cada uma. Widgets 100% nativos do
PyQt5 — sem QSS customizado, conforme requisito de "aparência nativa".
"""
from __future__ import annotations

from PyQt5.QtWidgets import QMainWindow, QTabWidget

from app.domain.filter_service import FilterService
from app.ui.execution_view import ExecutionView
from app.ui.filter_config_view import FilterConfigView
from app.ui.history_view import HistoryView
from app.ui.import_view import ImportView


class MainWindow(QMainWindow):
    def __init__(self, filter_service: FilterService, dataset_repository, trace_store=None):
        super().__init__()
        self.setWindowTitle("GIECAR — Filtro Sísmico Passa-Baixa")
        self.resize(950, 620)

        self._filter_service = filter_service
        self._dataset_repository = dataset_repository
        self._trace_store = trace_store or getattr(filter_service, "_trace_store", None)

        tabs = QTabWidget()
        self._tabs = tabs
        self.import_view = ImportView(dataset_repository)
        self.filter_config_view = FilterConfigView(filter_service, dataset_repository)
        self.execution_view = ExecutionView(filter_service)
        self.history_view = HistoryView(
            filter_service,
            dataset_repository=dataset_repository,
            trace_store=self._trace_store,
        )

        tabs.addTab(self.import_view, "Importar Sísmica")
        tabs.addTab(self.filter_config_view, "Configurar Filtro")
        tabs.addTab(self.execution_view, "Execução/Progresso")
        tabs.addTab(self.history_view, "Histórico de Jobs")

        self.setCentralWidget(tabs)

        # Sem isso, um dataset importado depois da janela abrir nunca
        # aparecia no combo da aba "Configurar Filtro" — reportado como bug.
        self.import_view.dataset_imported.connect(lambda _ds: self.filter_config_view.refresh_datasets())

        # Ao criar um job, leva o usuário direto para a aba de execução e
        # já dispara o processamento
        self.filter_config_view.job_created.connect(self._on_job_created)

        # Ao solicitar a retomada de um job a partir do histórico
        self.history_view.resume_requested.connect(self._on_job_created)

        # Sempre que o usuário entrar na aba de configuração ou
        # histórico, atualiza os dados exibidos
        tabs.currentChanged.connect(self._on_tab_changed)

    def _on_job_created(self, job) -> None:
        self.execution_view.start_job(job)
        self._tabs.setCurrentWidget(self.execution_view)

    def _on_tab_changed(self, index: int) -> None:
        try:
            widget = self.centralWidget().widget(index)
            if widget is self.filter_config_view:
                self.filter_config_view.refresh_datasets()
            elif widget is self.history_view:
                self.history_view.refresh()
        except Exception as exc:
            import logging
            logging.error(f"[MainWindow] Erro seguro ao atualizar aba {index}: {exc}")

