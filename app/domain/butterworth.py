"""
Lógica pura do filtro Butterworth passa-baixa. Sem I/O, sem Qt — só
matemática. Deve ser o arquivo com a maior cobertura de testes unitários
(corretude numérica e resposta em frequência).
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfiltfilt


def design_lowpass_sos(cutoff_hz: float, order: int, sample_rate_ms: float) -> np.ndarray:
    """
    Projeta os coeficientes SOS (second-order sections) do filtro
    Butterworth passa-baixa. SOS é preferível a (b, a) por estabilidade
    numérica em ordens mais altas.

    Args:
        cutoff_hz: frequência de corte em Hz.
        order: ordem do filtro (ex: 2 a 8).
        sample_rate_ms: intervalo de amostragem do dado, em milissegundos.

    Raises:
        ValueError: se cutoff_hz não respeitar 0 < cutoff_hz < Nyquist.
    """
    fs_hz = 1000.0 / sample_rate_ms  # frequência de amostragem em Hz
    nyquist_hz = fs_hz / 2.0

    if not (0 < cutoff_hz < nyquist_hz):
        raise ValueError(
            f"cutoff_hz={cutoff_hz} fora do intervalo válido (0, {nyquist_hz})"
        )

    normalized_cutoff = cutoff_hz / nyquist_hz  # scipy espera 0..1
    sos = butter(order, normalized_cutoff, btype="low", output="sos")
    return sos


def apply_lowpass(
    traces_chunk: np.ndarray,
    cutoff_hz: float,
    order: int,
    sample_rate_ms: float,
) -> np.ndarray:
    """
    Aplica o filtro passa-baixa a um chunk de traços.

    Args:
        traces_chunk: array 2D (n_traces_no_chunk, n_samples). NUNCA o
            volume completo — só um chunk por vez (ver domain/filter_service.py).

    Returns:
        Array filtrado, mesma shape de entrada.
    """
    sos = design_lowpass_sos(cutoff_hz, order, sample_rate_ms)
    # filtfilt (fase zero) ao longo do eixo do tempo (último eixo)
    return sosfiltfilt(sos, traces_chunk, axis=-1)


def amplitude_spectrum(trace: np.ndarray, sample_rate_ms: float) -> tuple[np.ndarray, np.ndarray]:
    """
    Calcula o espectro de amplitude de um único traço, usado na
    visualização de QC (item opcional). Retorna (freqs_hz, amplitudes).
    """
    fs_hz = 1000.0 / sample_rate_ms
    n = len(trace)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs_hz)
    amplitudes = np.abs(np.fft.rfft(trace))
    return freqs, amplitudes
