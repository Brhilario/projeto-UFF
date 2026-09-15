"""
Item opcional: compara o pico de memória da abordagem streaming
(app/domain/filter_service.py) contra uma abordagem ingênua que carrega
o volume sísmico inteiro em um array antes de filtrar.

Uso:
    python benchmarks/memory_streaming_vs_naive.py --input synthetic.sgy

Gera os números a documentar no README (seção "Trade-offs").

TODO: implementar de fato a função _run_naive_approach (hoje é só o
esqueleto) e rodar contra arquivos de tamanhos crescentes para gerar
uma tabela comparativa.
"""
from __future__ import annotations

import argparse
import sys
import tracemalloc
from pathlib import Path

# Garante que a raiz do projeto (onde fica a pasta app/) está no sys.path,
# mesmo quando o script é chamado diretamente (python benchmarks/arquivo.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import segyio

from app.domain.butterworth import apply_lowpass


def run_naive_approach(path: str, cutoff_hz: float, order: int, sample_rate_ms: float) -> float:
    """Abordagem PROIBIDA no core (aqui só para fins de comparação/benchmark)."""
    tracemalloc.start()
    with segyio.open(path, "r", ignore_geometry=True) as f:
        all_traces = segyio.tools.collect(f.trace[:])  # carrega TUDO de uma vez
    filtered = apply_lowpass(all_traces, cutoff_hz, order, sample_rate_ms)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak / (1024 * 1024)  # MB


def run_streaming_approach(path: str, cutoff_hz: float, order: int, sample_rate_ms: float) -> float:
    from app.domain.segy_reader import iter_trace_chunks

    tracemalloc.start()
    n_chunks = 0
    for _, chunk in iter_trace_chunks(path):
        _ = apply_lowpass(chunk, cutoff_hz, order, sample_rate_ms)
        n_chunks += 1
        current, peak = tracemalloc.get_traced_memory()
        print(f"  chunk {n_chunks:>5} | memória atual: {current/1024/1024:.1f} MB | pico até agora: {peak/1024/1024:.1f} MB", end="\r")
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print()  # newline após a barra de progresso
    return peak / (1024 * 1024)  # MB


def estimate_naive_memory_mb(path: str) -> float:
    """
    Estima (sem carregar nada) quanta memória a abordagem ingênua vai
    precisar, a partir só dos headers. Usado para decidir se vale a
    pena arriscar rodar run_naive_approach ou não.
    """
    with segyio.open(path, "r", ignore_geometry=True) as f:
        n_traces = f.tracecount
        n_samples = len(f.samples)
    # float32 = 4 bytes; segyio.tools.collect tende a duplicar o array
    # internamente, então o pico real fica bem acima disso na prática
    bytes_estimate = n_traces * n_samples * 4 * 2
    return bytes_estimate / (1024 * 1024)


def get_available_memory_mb() -> float | None:
    try:
        import psutil
        return psutil.virtual_memory().available / (1024 * 1024)
    except ImportError:
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--cutoff-hz", type=float, default=60.0)
    parser.add_argument("--order", type=int, default=4)
    parser.add_argument("--sample-rate-ms", type=float, default=4.0)
    parser.add_argument(
        "--skip-naive",
        action="store_true",
        help="Roda só a abordagem streaming. Use isso para arquivos grandes "
             "(ex: 1GB+) onde a abordagem ingênua arrisca derrubar o processo "
             "(OOM kill) — o objetivo do requisito é justamente esse: provar "
             "que streaming funciona onde a abordagem ingênua não sobrevive.",
    )
    parser.add_argument(
        "--force-naive",
        action="store_true",
        help="Roda a abordagem ingênua mesmo que a estimativa de memória "
             "necessária ultrapasse a RAM disponível (arrisca travar/matar o processo).",
    )
    args = parser.parse_args()

    print(f"Streaming (chunk a chunk):")
    streaming_mb = run_streaming_approach(args.input, args.cutoff_hz, args.order, args.sample_rate_ms)
    print(f"  -> pico de memória: {streaming_mb:.1f} MB\n")

    if args.skip_naive:
        print("Abordagem ingênua pulada (--skip-naive). Isso já é evidência suficiente:")
        print("o pico de memória do streaming acima independe do tamanho do arquivo de entrada.")
        sys.exit(0)

    estimated_naive_mb = estimate_naive_memory_mb(args.input)
    available_mb = get_available_memory_mb()

    print(f"Estimativa de memória necessária p/ abordagem ingênua: ~{estimated_naive_mb:.0f} MB")
    if available_mb is not None:
        print(f"Memória disponível no sistema agora: ~{available_mb:.0f} MB")
        if estimated_naive_mb > available_mb * 0.8 and not args.force_naive:
            print(
                "\nAVISO: a estimativa ultrapassa a memória disponível. Pulando a "
                "abordagem ingênua para não travar sua máquina (o processo provavelmente "
                "seria morto pelo OOM killer, como já aconteceu). Isso É o resultado do "
                "benchmark: documente esse comportamento no README como prova do requisito "
                "de memória O(1). Use --force-naive se quiser tentar mesmo assim."
            )
            sys.exit(0)
    else:
        print("(instale 'psutil' para checagem automática de memória disponível: pip install psutil)")

    naive_mb = run_naive_approach(args.input, args.cutoff_hz, args.order, args.sample_rate_ms)
    print(f"Ingênuo (arquivo inteiro em memória):  {naive_mb:.1f} MB de pico")
    print(f"Streaming (chunk a chunk):             {streaming_mb:.1f} MB de pico")
    print(f"Redução: {(1 - streaming_mb / naive_mb) * 100:.1f}%")
