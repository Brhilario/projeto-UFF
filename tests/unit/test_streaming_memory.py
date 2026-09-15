"""
Garante que o pico de memória do pipeline de filtragem NÃO escala com o
número total de traços — requisito não-negociável do enunciado.

Implementação de referência: substitui segy_reader.iter_trace_chunks por
um gerador sintético (evita depender de um .sgy real de dezenas de GB
rodando em CI) e mede o pico de memória via tracemalloc processando
datasets de tamanhos bem diferentes, comparando os picos.

TODO: complementar com benchmarks/memory_streaming_vs_naive.py usando um
.sgy real (ou gerado por scripts/generate_synthetic_segy.py) para o
item opcional de benchmark documentado no README.
"""
from __future__ import annotations

import tracemalloc
from unittest.mock import patch

import numpy as np
import pytest

from app.domain.filter_service import FilterService
from app.workers.cancel_token import CancelToken


def _fake_chunk_generator(n_chunks: int, chunk_size: int, n_samples: int):
    def _gen(path, chunk_size_arg=500):
        for idx in range(n_chunks):
            yield idx, np.random.randn(chunk_size, n_samples).astype(np.float32)
    return _gen


@pytest.mark.parametrize("n_chunks", [5, 50])
def test_peak_memory_does_not_scale_with_dataset_size(fake_repos, sample_dataset, n_chunks):
    dataset_repo, job_repo, trace_store = fake_repos
    dataset_repo.save(sample_dataset)

    svc = FilterService(dataset_repo, job_repo, trace_store)
    job = svc.create_filter_job(dataset_id=sample_dataset.id, cutoff_hz=40.0, order=4)

    chunk_size, n_samples = 500, sample_dataset.n_samples
    fake_gen = _fake_chunk_generator(n_chunks, chunk_size, n_samples)

    with patch("app.domain.filter_service.iter_trace_chunks", side_effect=lambda path: fake_gen(path)):
        tracemalloc.start()
        svc.run_filter_job(job.id, progress_callback=lambda pct: None, cancel_token=CancelToken())
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

    # Peak esperado é proporcional a UM chunk (chunk_size * n_samples * 4 bytes),
    # com folga generosa para overhead do interpretador/filtro — não ao total
    # de chunks processados (n_chunks), que é o comportamento proibido.
    single_chunk_bytes = chunk_size * n_samples * 4
    assert peak < single_chunk_bytes * 20, (
        f"Pico de memória ({peak} bytes) sugere acúmulo além de um chunk "
        f"por vez — verifique se iter_trace_chunks/write_chunk não estão "
        f"retendo referências a chunks já processados."
    )
