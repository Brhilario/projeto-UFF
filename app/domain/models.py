"""
Modelos de domínio puros. NÃO importar PyQt5 aqui — esta camada precisa
rodar isoladamente em pytest, sem QApplication.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class SeismicDataset:
    """
    Representa um levantamento sísmico importado. Criado a partir da
    leitura de trace headers apenas (ver domain/segy_reader.py) — nunca
    carrega os traços em si neste objeto.
    """
    name: str
    source_path: str
    n_inlines: int
    n_crosslines: int
    n_samples: int
    sample_rate_ms: float
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=_utcnow)

    @property
    def n_traces(self) -> int:
        return self.n_inlines * self.n_crosslines

    @property
    def nyquist_hz(self) -> float:
        """
        Frequência de Nyquist em Hz, a partir do intervalo de amostragem
        em milissegundos. sample_rate_ms=4 (4ms) -> Nyquist = 125 Hz.
        """
        return 1000.0 / (2.0 * self.sample_rate_ms)


@dataclass
class Job:
    """
    Representa uma execução de filtragem sobre um SeismicDataset.
    Transições de estado são validadas por job_state_machine.py,
    não diretamente aqui.
    """
    dataset_id: str
    cutoff_hz: float
    order: int
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.CREATED
    progress_pct: float = 0.0
    output_path: str | None = None
    error_message: str | None = None
    last_completed_chunk_idx: int | None = None  # usado no resume (trilha de criatividade)
    created_at: datetime = field(default_factory=_utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass
class JobLog:
    """Representa um evento de log da execução de um Job."""
    job_id: str
    message: str
    level: str = "INFO"
    id: int | None = None
    timestamp: datetime = field(default_factory=_utcnow)
