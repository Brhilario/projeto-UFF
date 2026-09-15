from __future__ import annotations

import pytest

from app.domain.models import SeismicDataset


@pytest.fixture
def sample_dataset() -> SeismicDataset:
    """Dataset sintético pequeno para testes rápidos, sample_rate_ms=4 -> Nyquist=125Hz."""
    return SeismicDataset(
        name="synthetic_test.sgy",
        source_path="/tmp/synthetic_test.sgy",
        n_inlines=1,
        n_crosslines=100,
        n_samples=500,
        sample_rate_ms=4.0,
    )


class FakeDatasetRepository:
    """In-memory fake, para testar FilterService sem SQLite real."""

    def __init__(self):
        self._store: dict[str, SeismicDataset] = {}

    def save(self, dataset: SeismicDataset) -> None:
        self._store[dataset.id] = dataset

    def get(self, dataset_id: str):
        return self._store.get(dataset_id)

    def list(self):
        return list(self._store.values())


class FakeJobRepository:
    def __init__(self):
        self._store: dict[str, object] = {}

    def save(self, job) -> None:
        self._store[job.id] = job

    def get(self, job_id: str):
        return self._store.get(job_id)

    def list(self, dataset_id=None, status=None):
        jobs = list(self._store.values())
        if dataset_id is not None:
            jobs = [j for j in jobs if j.dataset_id == dataset_id]
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
        return jobs


class FakeTraceStore:
    """Grava chunks em memória — usado nos testes de negócio, sem tocar em disco/HDF5."""

    def __init__(self):
        self.written_chunks: list[tuple[str, int]] = []

    def write_chunk(self, job_id, chunk_idx, chunk):
        self.written_chunks.append((job_id, chunk_idx))

    def finalize(self, job_id: str) -> str:
        return f"/tmp/fake_output_{job_id}.h5"

    def rollback_partial(self, job_id: str) -> None:
        pass


@pytest.fixture
def fake_repos():
    return FakeDatasetRepository(), FakeJobRepository(), FakeTraceStore()
