"""
Gera um arquivo .sgy sintético pequeno para desenvolvimento e testes
manuais, sem depender de baixar datasets públicos grandes.

Uso:
    python scripts/generate_synthetic_segy.py --output synthetic.sgy \
        --n-traces 1000 --n-samples 500 --sample-rate-ms 4

TODO: adicionar opção --size-gb para gerar arquivos maiores e validar
comportamento de memória com dados mais próximos do cenário real (25GB+).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import segyio


def generate(output_path: str, n_traces: int, n_samples: int, sample_rate_ms: float) -> None:
    spec = segyio.spec()
    spec.samples = np.arange(n_samples)
    spec.tracecount = n_traces
    spec.format = 5  # IEEE float32

    with segyio.create(output_path, spec) as f:
        f.bin[segyio.BinField.Interval] = int(sample_rate_ms * 1000)  # microssegundos
        # t precisa usar o MESMO sample_rate_ms gravado no header, senão as
        # frequências do sinal gerado não correspondem ao que será lido de volta
        t = np.arange(n_samples) * (sample_rate_ms / 1000.0)  # em segundos
        for i in range(n_traces):
            # mistura de frequências baixa (sinal) + alta (ruído) para
            # testar visualmente o efeito do filtro depois
            signal = np.sin(2 * np.pi * 8 * t) + 0.4 * np.sin(2 * np.pi * 120 * t)
            f.trace[i] = signal.astype(np.float32)

    print(f"Gerado {output_path}: {n_traces} traços, {n_samples} amostras")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="synthetic.sgy")
    parser.add_argument("--n-traces", type=int, default=1000)
    parser.add_argument("--n-samples", type=int, default=500)
    parser.add_argument("--sample-rate-ms", type=float, default=4.0)
    args = parser.parse_args()

    generate(args.output, args.n_traces, args.n_samples, args.sample_rate_ms)
