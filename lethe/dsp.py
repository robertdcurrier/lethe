"""Digital signal processing stages for lethe.

Currently: Butterworth bandpass. Future stages (spectral
gating, model-based denoising, etc.) will be added here
as separate functions and registered in pipeline.STAGES.
"""
import numpy as np
from scipy import signal


BANDPASS_ORDER = 6


def _validate_band(low, high, sr):
    """Raise ValueError if the requested band is invalid."""
    nyq = sr / 2.0
    if low <= 0:
        raise ValueError(
            f"low cutoff must be > 0 Hz (got {low})"
        )
    if high <= low:
        raise ValueError(
            f"high must be > low (got {low},{high})"
        )
    if high >= nyq:
        raise ValueError(
            f"high ({high}) must be < Nyquist ({nyq:.0f})"
        )


def _sos_bandpass(low, high, sr, order=BANDPASS_ORDER):
    """Design a Butterworth bandpass as SOS sections."""
    return signal.butter(
        order, [low, high],
        btype="band", fs=sr, output="sos",
    )


def bandpass(data, sr, low, high, order=BANDPASS_ORDER):
    """Zero-phase Butterworth bandpass filter.

    Works on mono (1-D) or multi-channel (N, C) float
    arrays; per-channel filtering to preserve channel
    independence.
    """
    _validate_band(low, high, sr)
    sos = _sos_bandpass(low, high, sr, order=order)
    if data.ndim == 1:
        y = signal.sosfiltfilt(sos, data)
        return y.astype(np.float32)
    out = np.zeros_like(data)
    for c in range(data.shape[1]):
        out[:, c] = signal.sosfiltfilt(sos, data[:, c])
    return out.astype(np.float32)
