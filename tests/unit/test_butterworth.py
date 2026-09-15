import numpy as np
import pytest

from app.domain.butterworth import apply_lowpass, design_lowpass_sos


SAMPLE_RATE_MS = 2.0  # 2ms -> fs = 500Hz, Nyquist = 250Hz


def test_design_lowpass_sos_rejects_cutoff_above_nyquist():
    with pytest.raises(ValueError):
        design_lowpass_sos(cutoff_hz=300.0, order=4, sample_rate_ms=SAMPLE_RATE_MS)


def test_design_lowpass_sos_rejects_zero_or_negative_cutoff():
    with pytest.raises(ValueError):
        design_lowpass_sos(cutoff_hz=0.0, order=4, sample_rate_ms=SAMPLE_RATE_MS)


def test_design_lowpass_sos_returns_valid_shape_for_order():
    sos = design_lowpass_sos(cutoff_hz=50.0, order=4, sample_rate_ms=SAMPLE_RATE_MS)
    # SOS para ordem N tem ceil(N/2) seções, cada uma com 6 coeficientes
    assert sos.shape == (2, 6)


def test_apply_lowpass_attenuates_high_frequency_signal():
    """
    Corretude funcional: um sinal de alta frequência (acima do cutoff)
    deve ter sua amplitude fortemente reduzida após o filtro.
    """
    fs_hz = 1000.0 / SAMPLE_RATE_MS
    duration_s = 1.0
    n_samples = int(fs_hz * duration_s)
    t = np.linspace(0, duration_s, n_samples, endpoint=False)

    high_freq_hz = 200.0  # bem acima do cutoff de 30Hz, abaixo do Nyquist de 250Hz
    signal = np.sin(2 * np.pi * high_freq_hz * t)
    trace_chunk = signal.reshape(1, -1)  # 1 traço, n_samples

    filtered = apply_lowpass(trace_chunk, cutoff_hz=30.0, order=4, sample_rate_ms=SAMPLE_RATE_MS)

    original_rms = np.sqrt(np.mean(signal**2))
    filtered_rms = np.sqrt(np.mean(filtered**2))
    assert filtered_rms < original_rms * 0.1  # atenuação forte esperada


def test_apply_lowpass_preserves_low_frequency_signal():
    """Sinal bem abaixo do cutoff deve passar quase intacto."""
    fs_hz = 1000.0 / SAMPLE_RATE_MS
    duration_s = 1.0
    n_samples = int(fs_hz * duration_s)
    t = np.linspace(0, duration_s, n_samples, endpoint=False)

    low_freq_hz = 5.0
    signal = np.sin(2 * np.pi * low_freq_hz * t)
    trace_chunk = signal.reshape(1, -1)

    filtered = apply_lowpass(trace_chunk, cutoff_hz=50.0, order=4, sample_rate_ms=SAMPLE_RATE_MS)

    original_rms = np.sqrt(np.mean(signal**2))
    filtered_rms = np.sqrt(np.mean(filtered**2))
    assert filtered_rms > original_rms * 0.9  # pouca atenuação esperada


def test_apply_lowpass_preserves_shape():
    chunk = np.random.randn(10, 250)  # 10 traços, 250 amostras
    filtered = apply_lowpass(chunk, cutoff_hz=50.0, order=4, sample_rate_ms=SAMPLE_RATE_MS)
    assert filtered.shape == chunk.shape
