"""Stage orchestration for the lethe pipeline.

Each stage is a callable with the signature:
    stage(data, sr, cfg) -> data
Stages are applied in order from STAGES. New denoising
approaches are added by defining a stage and appending
it to STAGES (or by config-driven selection later).
"""
import os
import time
from datetime import datetime

import numpy as np
from scipy import signal as sp_signal

from lethe.dsp import bandpass
from lethe.io import load_wav, save_wav


STAMP_FMT = "%Y%m%d_%H%M%S"


def run_stamp():
    """Filesystem-safe timestamp for this invocation."""
    return datetime.now().strftime(STAMP_FMT)


def _band_rms_dbfs(data, sr, lo, hi):
    """RMS (dBFS) of a mono-mixed signal in [lo, hi] Hz."""
    mono = data.mean(axis=1) if data.ndim == 2 else data
    freqs, psd = sp_signal.welch(
        mono, fs=sr, nperseg=4096, noverlap=3072,
    )
    mask = (freqs >= lo) & (freqs <= hi)
    if not mask.any():
        return float("-inf")
    band_power = float(np.trapz(psd[mask], freqs[mask]))
    if band_power <= 0:
        return float("-inf")
    return 10.0 * np.log10(band_power)


def band_energy(data, sr, freq_range):
    """Sub / signal / super band dBFS-ish energies."""
    lo, hi = freq_range
    nyq = sr / 2.0
    return {
        "sub_band_db": _band_rms_dbfs(data, sr, 1.0, lo),
        "signal_band_db": _band_rms_dbfs(data, sr, lo, hi),
        "super_band_db": _band_rms_dbfs(
            data, sr, hi, nyq - 1.0
        ),
    }


def rms_dbfs(data):
    """RMS of a float audio buffer in dBFS (mono-mix)."""
    mono = data.mean(axis=1) if data.ndim == 2 else data
    val = float(np.sqrt(np.mean(mono * mono)))
    return 20.0 * np.log10(val + 1e-12)


def stage_bandpass(data, sr, cfg):
    """Apply bandpass using cfg['freq_range'] = (low, high)."""
    low, high = cfg["freq_range"]
    return bandpass(data, sr, low, high)


STAGES = [
    stage_bandpass,
]


def output_path_for(in_path, output_dir, stamp):
    """Compose output path as '<stem>_<stamp>.wav'."""
    base = os.path.basename(in_path)
    stem, ext = os.path.splitext(base)
    return os.path.join(output_dir, f"{stem}_{stamp}{ext}")


def process_file(in_path, out_path, cfg):
    """Load, run stages, save; return a metrics dict."""
    t0 = time.time()
    data, sr, subtype = load_wav(in_path)
    pre_rms = rms_dbfs(data)
    pre_band = band_energy(data, sr, cfg["freq_range"])
    for stage in STAGES:
        data = stage(data, sr, cfg)
    post_rms = rms_dbfs(data)
    post_band = band_energy(data, sr, cfg["freq_range"])
    save_wav(out_path, data, sr, subtype)
    return {
        "in_path": in_path,
        "out_path": out_path,
        "sr": sr,
        "channels": 1 if data.ndim == 1 else data.shape[1],
        "duration_s": len(data) / sr,
        "subtype": subtype,
        "pre_rms_dbfs": pre_rms,
        "post_rms_dbfs": post_rms,
        "delta_db": pre_rms - post_rms,
        "pre_band_db": pre_band,
        "post_band_db": post_band,
        "elapsed_s": time.time() - t0,
    }
