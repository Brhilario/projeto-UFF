from unittest.mock import patch
import numpy as np
import pytest

from app.domain.exceptions import DatasetNotFoundError, InvalidFilterParamsError
from app.domain.filter_service import FilterService
from app.domain.models import JobStatus
from app.workers.cancel_token import CancelToken


@pytest.fixture
def service(fake_repos):
    dataset_repo, job_repo, trace_store = fake_repos
    return FilterService(dataset_repo, job_repo, trace_store), dataset_repo, job_repo, trace_store


def test_create_filter_job_raises_if_dataset_missing(service):
    svc, _, _, _ = service
    with pytest.raises(DatasetNotFoundError):
        svc.create_filter_job(dataset_id="nao-existe", cutoff_hz=60.0, order=4)


def test_create_filter_job_raises_if_cutoff_above_nyquist(service, sample_dataset):
    svc, dataset_repo, _, _ = service
    dataset_repo.save(sample_dataset)  # Nyquist = 125Hz

    with pytest.raises(InvalidFilterParamsError):
        svc.create_filter_job(dataset_id=sample_dataset.id, cutoff_hz=200.0, order=4)


def test_create_filter_job_raises_if_cutoff_zero_or_negative(service, sample_dataset):
    svc, dataset_repo, _, _ = service
    dataset_repo.save(sample_dataset)

    with pytest.raises(InvalidFilterParamsError):
        svc.create_filter_job(dataset_id=sample_dataset.id, cutoff_hz=0.0, order=4)


@pytest.mark.parametrize("invalid_order", [0, 1, 9, 20])
def test_create_filter_job_raises_if_order_out_of_range(service, sample_dataset, invalid_order):
    svc, dataset_repo, _, _ = service
    dataset_repo.save(sample_dataset)

    with pytest.raises(InvalidFilterParamsError):
        svc.create_filter_job(dataset_id=sample_dataset.id, cutoff_hz=60.0, order=invalid_order)


def test_create_filter_job_succeeds_with_valid_params(service, sample_dataset):
    svc, dataset_repo, job_repo, _ = service
    dataset_repo.save(sample_dataset)

    job = svc.create_filter_job(dataset_id=sample_dataset.id, cutoff_hz=60.0, order=4)

    assert job.status == JobStatus.CREATED
    assert job_repo.get(job.id) is not None


def test_cancel_job_with_single_argument_contract(service, sample_dataset):
    """Garante que cancel_job(job_id) sem o token explícito funciona conforme o contrato."""
    svc, dataset_repo, job_repo, _ = service
    dataset_repo.save(sample_dataset)
    job = svc.create_filter_job(dataset_id=sample_dataset.id, cutoff_hz=40.0, order=4)

    token = CancelToken()
    # Simula o início do job registrando o token no FilterService
    svc._active_tokens[job.id] = token

    # Chamada com apenas job_id conforme especificação
    svc.cancel_job(job.id)
    assert token.is_set()


def test_job_execution_records_timestamps(service, sample_dataset):
    """Garante que started_at e finished_at são devidamente preenchidos."""
    svc, dataset_repo, _, _ = service
    dataset_repo.save(sample_dataset)
    job = svc.create_filter_job(dataset_id=sample_dataset.id, cutoff_hz=40.0, order=4)

    def fake_chunks(path):
        yield 0, np.random.randn(100, sample_dataset.n_samples).astype(np.float32)

    with patch("app.domain.filter_service.iter_trace_chunks", side_effect=fake_chunks):
        finished_job = svc.run_filter_job(job.id, progress_callback=lambda pct: None, cancel_token=CancelToken())

    assert finished_job.status == JobStatus.COMPLETED
    assert finished_job.started_at is not None
    assert finished_job.finished_at is not None
    assert finished_job.finished_at >= finished_job.started_at


def test_resume_job_from_interrupted_chunk(service, sample_dataset):
    """Trilha de criatividade: retoma o job a partir do último chunk concluído com sucesso."""
    svc, dataset_repo, job_repo, trace_store = service
    dataset_repo.save(sample_dataset)
    job = svc.create_filter_job(dataset_id=sample_dataset.id, cutoff_hz=40.0, order=4)

    # Simula interrupção prévia no chunk 0 (de 3 chunks)
    job.last_completed_chunk_idx = 0
    job.status = JobStatus.CANCELLED
    job_repo.save(job)

    processed_chunks = []

    def fake_chunks(path):
        for idx in range(3):
            processed_chunks.append(idx)
            yield idx, np.random.randn(100, sample_dataset.n_samples).astype(np.float32)

    with patch("app.domain.filter_service.iter_trace_chunks", side_effect=fake_chunks):
        resumed_job = svc.run_filter_job(job.id, progress_callback=lambda pct: None, cancel_token=CancelToken())

    assert resumed_job.status == JobStatus.COMPLETED
    # Chunk 0 foi pulado na escrita do trace_store (apenas chunks 1 e 2 gravados nesta sessão)
    written_indices = [idx for _, idx in trace_store.written_chunks]
    assert written_indices == [1, 2]
    assert resumed_job.last_completed_chunk_idx == 2

