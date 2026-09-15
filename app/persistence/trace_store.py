"""
Persistência incremental dos traços filtrados em HDF5. Usa dataset
resizable (maxshape) para nunca precisar saber o tamanho final de
antemão nem alocar tudo de uma vez.

Trade-off HDF5 vs Zarr: documentar a decisão final no README.
"""
from __future__ import annotations

import os

import h5py
import numpy as np

OUTPUT_DIR = "output_traces"


class TraceStore:
    def __init__(self, output_dir: str = OUTPUT_DIR):
        self._output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def _path_for(self, job_id: str) -> str:
        return os.path.join(self._output_dir, f"{job_id}.h5")

    def write_chunk(self, job_id: str, chunk_idx: int, chunk: np.ndarray) -> None:
        """
        Escreve/expande o dataset HDF5 incrementalmente. Aberto em modo
        append ('a') para permitir chamadas sucessivas sem reescrever o
        arquivo inteiro a cada chunk.
        """
        path = self._path_for(job_id)
        n_new_traces, n_samples = chunk.shape

        with h5py.File(path, "a") as f:
            if "traces" not in f:
                f.create_dataset(
                    "traces",
                    shape=(0, n_samples),
                    maxshape=(None, n_samples),  # eixo 0 ilimitado -> streaming
                    chunks=(min(500, max(1, n_new_traces)), n_samples),
                    dtype=chunk.dtype,
                )
            dset = f["traces"]
            old_size = dset.shape[0]
            dset.resize(old_size + n_new_traces, axis=0)
            dset[old_size : old_size + n_new_traces] = chunk
            f.attrs["last_completed_chunk_idx"] = chunk_idx

    def finalize(self, job_id: str) -> str:
        """Chamado ao final do job bem-sucedido. Retorna o output_path definitivo."""
        return self._path_for(job_id)

    def rollback_partial(self, job_id: str) -> None:
        """Item opcional: remove o arquivo parcial em caso de cancelamento."""
        path = self._path_for(job_id)
        if os.path.exists(path):
            os.remove(path)

    def read_full_trace(self, job_id: str, trace_idx: int) -> np.ndarray:
        """Leitura pontual (ex: para plot de QC), não usada no pipeline de escrita."""
        path = self._path_for(job_id)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Arquivo HDF5 para job {job_id} não encontrado: {path}")
        with h5py.File(path, "r") as f:
            if "traces" not in f:
                raise KeyError(f"Dataset 'traces' não encontrado no arquivo {path}")
            n_traces = f["traces"].shape[0]
            if trace_idx < 0 or trace_idx >= n_traces:
                raise IndexError(f"trace_idx={trace_idx} fora dos limites [0, {n_traces - 1}]")
            return np.array(f["traces"][trace_idx])

    def get_trace_count(self, job_id: str) -> int:
        """Retorna a quantidade de traços gravados no arquivo HDF5 do job."""
        path = self._path_for(job_id)
        if not os.path.exists(path):
            return 0
        with h5py.File(path, "r") as f:
            return f["traces"].shape[0] if "traces" in f else 0

