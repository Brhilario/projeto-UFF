"""
Teste E2E: simula o fluxo completo do usuário (import -> configurar filtro
-> executar -> consultar histórico) direto na camada de negócio, sem UI
real — conforme permitido pelo enunciado ("pode usar pytest-qt ou testar
a camada de negócio diretamente, sem UI real").

TODO: versão alternativa com pytest-qt instanciando MainWindow real e
simulando cliques (QTest.mouseClick) se sobrar tempo — vale como
evidência extra de qualidade, mas não é obrigatório.
"""
from __future__ import annotations

from unittest.mock import patch

import numpy as np

from app.domain.filter_service import FilterService
from app.domain.models import JobStatus, SeismicDataset
from app.workers.cancel_token import CancelToken


def test_full_pipeline_import_filter_persist(fake_repos):
    dataset_repo, job_repo, trace_store = fake_repos
    svc = FilterService(dataset_repo, job_repo, trace_store)

    # 1) "Import": normalmente viria de segy_reader.read_header_summary(path);
    # aqui construímos o SeismicDataset diretamente para isolar o teste
    # da necessidade de um arquivo .sgy real.
    dataset = SeismicDataset(
        name="e2e_test.sgy",
        source_path="/tmp/e2e_test.sgy",
        n_inlines=1,
        n_crosslines=1500,  # 1500 traços / chunk_size=500 -> 3 chunks, batendo com fake_chunks abaixo
        n_samples=300,
        sample_rate_ms=2.0,  # Nyquist = 250Hz
    )
    dataset_repo.save(dataset)

    # 2) Configurar filtro + criar job
    job = svc.create_filter_job(dataset_id=dataset.id, cutoff_hz=60.0, order=4)
    assert job.status == JobStatus.CREATED

    # 3) Executar (streaming simulado, sem depender de .sgy real em disco)
    def fake_chunks(path):
        for idx in range(3):
            yield idx, np.random.randn(500, dataset.n_samples).astype(np.float32)

    with patch("app.domain.filter_service.iter_trace_chunks", side_effect=fake_chunks):
        finished_job = svc.run_filter_job(
            job.id, progress_callback=lambda pct: None, cancel_token=CancelToken()
        )

    assert finished_job.status == JobStatus.COMPLETED
    assert finished_job.progress_pct == 100.0
    assert finished_job.output_path is not None
    assert len(trace_store.written_chunks) == 3

    # 4) Consultar histórico
    jobs = svc.list_jobs(dataset_id=dataset.id)
    assert len(jobs) == 1
    assert jobs[0].id == job.id

    completed_jobs = svc.list_jobs(status=JobStatus.COMPLETED)
    assert len(completed_jobs) == 1


def test_full_pipeline_cancellation(fake_repos, sample_dataset):
    dataset_repo, job_repo, trace_store = fake_repos
    dataset_repo.save(sample_dataset)
    svc = FilterService(dataset_repo, job_repo, trace_store)

    job = svc.create_filter_job(dataset_id=sample_dataset.id, cutoff_hz=40.0, order=4)

    cancel_token = CancelToken()
    cancel_token.set()  # simula clique em "Cancelar" antes do 1o chunk

    def fake_chunks(path):
        for idx in range(5):
            yield idx, np.random.randn(500, sample_dataset.n_samples).astype(np.float32)

    with patch("app.domain.filter_service.iter_trace_chunks", side_effect=fake_chunks):
        finished_job = svc.run_filter_job(
            job.id, progress_callback=lambda pct: None, cancel_token=cancel_token
        )

    assert finished_job.status == JobStatus.CANCELLED
