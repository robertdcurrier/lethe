"""Stage orchestration for the lethe pipeline.

Each stage is a callable with the signature:
    stage(data, sr, cfg) -> data
Stages are applied in order from STAGES. New denoising
approaches are added by defining a stage and appending
it to STAGES (or by config-driven selection later).

Files are processed in chunks even when short, so the
agentic envelope always carries a ``chunks[]`` array.
Short files yield exactly one chunk spanning the whole
waveform; the output is bit-for-bit equivalent to
whole-file filtering (sosfiltfilt sees the same context
either way). Long files stream through in bounded memory
and expose per-chunk band-energy metrics for downstream
agents to localize signal.
"""
import os
import time
from datetime import datetime

import numpy as np
import soundfile as sf
from scipy import signal as sp_signal

from lethe.dsp import bandpass
from lethe.io import iter_chunks, save_wav, wav_info


STAMP_FMT = "%Y%m%d_%H%M%S"
CHUNK_PAD_S = 0.5


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


def _slice_inner(buf, left, right):
    """Return buf with left/right padding stripped."""
    end = buf.shape[0] - right if right else buf.shape[0]
    if buf.ndim == 1:
        return buf[left:end]
    return buf[left:end, :]


def _chunk_samples(cfg, info):
    """Chunk size in samples; <=0 => whole file in one chunk."""
    cl = cfg.get("chunk_length_s") or 0
    if cl <= 0:
        return max(info["frames"], 1)
    return max(int(round(cl * info["sr"])), 1)


def _plan_paths(in_path, output_dir, stamp, cfg):
    """Compose output paths.

    Returns a dict: ``single`` (path or None) and
    ``chunk_fmt`` (format with {idx:03d} slot or None).
    Exactly one of the two is set, based on emit_chunks.
    """
    base = os.path.basename(in_path)
    stem, ext = os.path.splitext(base)
    if cfg.get("emit_chunks"):
        return {
            "single": None,
            "chunk_fmt": os.path.join(
                output_dir,
                f"{stem}_{stamp}_chunk_{{idx:03d}}{ext}",
            ),
        }
    return {
        "single": os.path.join(
            output_dir, f"{stem}_{stamp}{ext}",
        ),
        "chunk_fmt": None,
    }


def _open_single_writer(paths, info):
    """Open a streaming writer for single-output mode.

    Returns None when we're emitting per-chunk files.
    """
    if paths["single"] is None:
        return None
    os.makedirs(
        os.path.dirname(os.path.abspath(paths["single"])),
        exist_ok=True,
    )
    return sf.SoundFile(
        paths["single"], "w",
        samplerate=info["sr"],
        channels=info["channels"],
        subtype=info["subtype"],
    )


def _sink_chunk(inner, writer, idx, paths, info):
    """Write inner samples; return chunk out-path or None."""
    if writer is not None:
        writer.write(inner)
        return None
    path = paths["chunk_fmt"].format(idx=idx)
    save_wav(path, inner, info["sr"], info["subtype"])
    return path


def _process_chunk(chunk, sr, cfg):
    """Filter a padded chunk; return (inner_out, metrics)."""
    padded = chunk["padded"]
    left, right = chunk["left_pad"], chunk["right_pad"]
    inner_in = _slice_inner(padded, left, right)
    pre_rms = rms_dbfs(inner_in)
    pre_band = band_energy(inner_in, sr, cfg["freq_range"])
    filtered = padded
    for stage in STAGES:
        filtered = stage(filtered, sr, cfg)
    inner_out = _slice_inner(filtered, left, right)
    post_rms = rms_dbfs(inner_out)
    post_band = band_energy(inner_out, sr, cfg["freq_range"])
    meta = {
        "idx": chunk["idx"],
        "start_s": chunk["start_sample"] / float(sr),
        "end_s": chunk["end_sample"] / float(sr),
        "frames": chunk["end_sample"] - chunk["start_sample"],
        "pre_rms_dbfs": pre_rms,
        "post_rms_dbfs": post_rms,
        "pre_band_db": pre_band,
        "post_band_db": post_band,
    }
    return inner_out, meta


def _agg_db(db_list, frames_list):
    """Power-weighted average of dB values by frame count."""
    total = sum(frames_list)
    if total == 0:
        return float("-inf")
    acc = 0.0
    for db, n in zip(db_list, frames_list):
        if db == float("-inf"):
            continue
        acc += (10.0 ** (db / 10.0)) * n
    if acc <= 0:
        return float("-inf")
    return 10.0 * float(np.log10(acc / total))


def _agg_band(chunks_meta, key, frames_list):
    """Power-weighted dB aggregation per band key."""
    bands = chunks_meta[0][key].keys()
    return {
        band: _agg_db(
            [c[key][band] for c in chunks_meta], frames_list,
        )
        for band in bands
    }


def _file_metric(in_path, paths, info, chunks_meta,
                 cfg, elapsed):
    """Assemble the file-level metrics dict."""
    frames_list = [c["frames"] for c in chunks_meta]
    pre_rms = _agg_db(
        [c["pre_rms_dbfs"] for c in chunks_meta], frames_list,
    )
    post_rms = _agg_db(
        [c["post_rms_dbfs"] for c in chunks_meta], frames_list,
    )
    out = {
        "in_path": in_path,
        "sr": info["sr"],
        "channels": info["channels"],
        "duration_s": info["duration_s"],
        "subtype": info["subtype"],
        "pre_rms_dbfs": pre_rms,
        "post_rms_dbfs": post_rms,
        "delta_db": pre_rms - post_rms,
        "pre_band_db": _agg_band(
            chunks_meta, "pre_band_db", frames_list,
        ),
        "post_band_db": _agg_band(
            chunks_meta, "post_band_db", frames_list,
        ),
        "chunk_length_s": cfg.get("chunk_length_s") or 0,
        "chunk_count": len(chunks_meta),
        "chunks": chunks_meta,
        "elapsed_s": elapsed,
    }
    if paths["single"]:
        out["out_path"] = paths["single"]
    return out


def process_file(in_path, cfg, output_dir, stamp):
    """Stream a file through the pipeline; return metrics.

    Always chunks (even short files yield one chunk), so
    the agentic envelope schema is uniform. Output is a
    single streamed WAV, or per-chunk WAVs when
    ``cfg['emit_chunks']`` is truthy.
    """
    t0 = time.time()
    info = wav_info(in_path)
    chunk_n = _chunk_samples(cfg, info)
    pad_n = int(round(CHUNK_PAD_S * info["sr"]))
    paths = _plan_paths(in_path, output_dir, stamp, cfg)
    os.makedirs(output_dir, exist_ok=True)
    chunks_meta = []
    writer = _open_single_writer(paths, info)
    try:
        for chunk in iter_chunks(in_path, chunk_n, pad_n):
            inner, meta = _process_chunk(
                chunk, info["sr"], cfg,
            )
            out_path = _sink_chunk(
                inner, writer, chunk["idx"], paths, info,
            )
            if out_path is not None:
                meta["out_path"] = out_path
            chunks_meta.append(meta)
    finally:
        if writer is not None:
            writer.close()
    return _file_metric(
        in_path, paths, info, chunks_meta,
        cfg, time.time() - t0,
    )
