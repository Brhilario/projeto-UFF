"""
Wrapper streaming sobre segyio. Responsável por:
  1) Ler apenas trace headers no momento do import (barato, rápido).
  2) Ler traços em chunks durante a filtragem (nunca o arquivo inteiro).

TODO: validar comportamento com segyio.open(..., strict=False) para
arquivos SEG-Y não totalmente padronizados (comum em dados reais de campo).
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np
import segyio


@dataclass
class SegyHeaderSummary:
    """Resumo extraído sem ler os traços — usado para popular SeismicDataset."""
    n_traces: int
    n_samples: int
    sample_rate_ms: float
    n_inlines: int
    n_crosslines: int


def read_header_summary(path: str) -> SegyHeaderSummary:
    """
    Abre o arquivo .sgy e lê SOMENTE os cabeçalhos (trace headers +
    binary header), sem tocar nos traços. Usado na etapa de import.
    """
    with segyio.open(path, "r", ignore_geometry=True) as f:
        n_traces = f.tracecount
        n_samples = len(f.samples)
        sample_rate_ms = segyio.tools.dt(f) / 1000.0  # segyio retorna em microssegundos

        # TODO: se o arquivo tiver geometria regular (inline/crossline),
        # reabrir com ignore_geometry=False para extrair n_inlines/n_crosslines
        # reais via f.xlines / f.ilines. Placeholder abaixo:
        n_inlines = 1
        n_crosslines = n_traces

    return SegyHeaderSummary(
        n_traces=n_traces,
        n_samples=n_samples,
        sample_rate_ms=sample_rate_ms,
        n_inlines=n_inlines,
        n_crosslines=n_crosslines,
    )


def iter_trace_chunks(
    path: str, chunk_size: int = 500
) -> Iterator[tuple[int, np.ndarray]]:
    """
    Gera chunks de traços via streaming. Cada iteração devolve
    (chunk_index, array 2D (chunk_size, n_samples)) — nunca o volume inteiro.

    Args:
        chunk_size: quantidade de traços lidos por vez. Ajustável conforme
            trade-off memória/overhead de I/O (documentar no README).
    """
    with segyio.open(path, "r", ignore_geometry=True) as f:
        n_traces = f.tracecount
        for chunk_idx, start in enumerate(range(0, n_traces, chunk_size)):
            end = min(start + chunk_size, n_traces)
            # segyio.trace é lazy; o slice abaixo materializa só este chunk
            chunk = np.stack([f.trace[i] for i in range(start, end)])
            yield chunk_idx, chunk
