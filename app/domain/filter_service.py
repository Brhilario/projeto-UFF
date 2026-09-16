"""
Contratos mínimos da camada de negócio, conforme o enunciado da prova.
Esta é a superfície que deve ser 100% testável via pytest, sem PyQt5.

Injeção de dependências (repository, trace_store) é feita por construtor
para permitir testes com fakes/in-memory, sem precisar de SQLite/HDF5 reais.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from app.domain.butterworth import apply_lowpass
from app.domain.exceptions import (
    DatasetNotFoundError,
    InvalidFilterParamsError,
    JobCancelledError,
    JobNotFoundError,
)
from app.domain.job_state_machine import transition
from app.domain.models import Job, JobLog, JobStatus
from app.domain.segy_reader import iter_trace_chunks
from app.workers.cancel_token import CancelToken

MIN_ORDER = 2
MAX_ORDER = 8

ProgressCallback = Callable[[float], None]


class FilterService:
    """
    Implementação de referência dos contratos exigidos. A UI (workers/filter_worker.py)
    chama estes métodos e só traduz callbacks/exceções em sinais Qt.
    """

    def __init__(self, dataset_repository, job_repository, trace_store, log_repository=None):
        self._datasets = dataset_repository
        self._jobs = job_repository
        self._trace_store = trace_store
        self._log_repo = log_repository
        self._active_tokens: dict[str, CancelToken] = {}

    def _log(self, job_id: str, level: str, message: str) -> None:
        if self._log_repo is not None:
            self._log_repo.save(JobLog(job_id=job_id, level=level, message=message))

    def create_filter_job(self, dataset_id: str, cutoff_hz: float, order: int) -> Job:
        dataset = self._datasets.get(dataset_id)
        if dataset is None:
            raise DatasetNotFoundError(f"Dataset {dataset_id} não encontrado")

        if not (0 < cutoff_hz < dataset.nyquist_hz):
            raise InvalidFilterParamsError(
                f"cutoff_hz={cutoff_hz} deve respeitar 0 < cutoff_hz < "
                f"Nyquist ({dataset.nyquist_hz} Hz)"
            )
        if not (MIN_ORDER <= order <= MAX_ORDER):
            raise InvalidFilterParamsError(
                f"order={order} fora da faixa permitida [{MIN_ORDER}, {MAX_ORDER}]"
            )

        job = Job(dataset_id=dataset_id, cutoff_hz=cutoff_hz, order=order)
        self._jobs.save(job)
        self._log(job.id, "INFO", f"Job criado para dataset {dataset.name} ({cutoff_hz}Hz, ordem {order})")
        return job

    def run_filter_job(
        self,
        job_id: str,
        progress_callback: ProgressCallback,
        cancel_token: CancelToken,
    ) -> Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError(f"Job {job_id} não encontrado")

        dataset = self._datasets.get(job.dataset_id)
        if dataset is None:
            raise DatasetNotFoundError(f"Dataset {job.dataset_id} não encontrado")

        # Registra cancel_token ativo para este job
        self._active_tokens[job_id] = cancel_token

        transition(job, JobStatus.RUNNING)
        job.started_at = datetime.now(timezone.utc)
        self._jobs.save(job)

        try:
            resume_from = job.last_completed_chunk_idx  # suporte a resume (trilha criatividade)
            total_chunks = self._estimate_total_chunks(dataset)

            if resume_from is not None:
                self._log(job.id, "INFO", f"Retomando execução a partir do chunk {resume_from + 1}/{total_chunks}")
                initial_pct = ((resume_from + 1) / total_chunks) * 100
                job.progress_pct = initial_pct
                progress_callback(initial_pct)
            else:
                self._log(job.id, "INFO", f"Iniciando execução: {total_chunks} chunks estimados")

            for chunk_idx, raw_chunk in iter_trace_chunks(dataset.source_path):
                if resume_from is not None and chunk_idx <= resume_from:
                    continue  # já processado em execução anterior

                if cancel_token.is_set():
                    raise JobCancelledError("Cancelamento solicitado pelo usuário")

                filtered_chunk = apply_lowpass(
                    raw_chunk, job.cutoff_hz, job.order, dataset.sample_rate_ms
                )
                self._trace_store.write_chunk(job.id, chunk_idx, filtered_chunk)

                job.last_completed_chunk_idx = chunk_idx
                job.progress_pct = ((chunk_idx + 1) / total_chunks) * 100
                if chunk_idx % 5 == 0 or chunk_idx == total_chunks - 1:
                    self._jobs.save(job)
                progress_callback(job.progress_pct)


            job.output_path = self._trace_store.finalize(job.id)
            transition(job, JobStatus.COMPLETED)
            self._log(job.id, "INFO", f"Job concluído com sucesso. Arquivo: {job.output_path}")

        except JobCancelledError as exc:
            job.error_message = str(exc)
            transition(job, JobStatus.CANCELLED)
            self._log(job.id, "WARNING", f"Job cancelado pelo usuário: {exc}")
        except Exception as exc:  # noqa: BLE001 - erro genérico vira FAILED, não propaga cru
            job.error_message = str(exc)
            transition(job, JobStatus.FAILED)
            self._log(job.id, "ERROR", f"Job falhou com erro: {exc}")
        finally:
            job.finished_at = datetime.now(timezone.utc)
            self._active_tokens.pop(job_id, None)
            self._jobs.save(job)

        return job

    def cancel_job(
        self,
        job_id: str,
        cancel_token: CancelToken | None = None,
        rollback: bool = False,
    ) -> None:
        """
        Cancela o job cooperativamente. Se cancel_token não for passado,
        utiliza o token ativo registrado na execução do job.
        Se rollback=True, remove o arquivo parcial de saída (item opcional).
        """
        token = cancel_token or self._active_tokens.get(job_id)
        if token is not None:
            token.set()

        if rollback:
            self._trace_store.rollback_partial(job_id)
            self._log(job_id, "INFO", "Rollback de saída parcial executado.")

    def rollback_job_output(self, job_id: str) -> None:
        """Item opcional: descarta o arquivo de saída parcial de um job cancelado/falho."""
        self._trace_store.rollback_partial(job_id)
        job = self._jobs.get(job_id)
        if job is not None:
            job.output_path = None
            job.last_completed_chunk_idx = None
            self._jobs.save(job)
            self._log(job_id, "INFO", "Arquivo de saída parcial removido.")

    def get_job_status(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError(f"Job {job_id} não encontrado")
        return job

    def list_jobs(self, dataset_id: str | None = None, status: JobStatus | None = None) -> list[Job]:
        return self._jobs.list(dataset_id=dataset_id, status=status)

    def get_job_logs(self, job_id: str) -> list[JobLog]:
        if self._log_repo is not None:
            return self._log_repo.list_for_job(job_id)
        return []

    def _estimate_total_chunks(self, dataset) -> int:
        chunk_size = 500
        return max(1, -(-dataset.n_traces // chunk_size))  # ceil division

