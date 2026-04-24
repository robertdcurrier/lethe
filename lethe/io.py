"""WAV load/save helpers that preserve bit-depth.

Two modes:

* Whole-file: ``load_wav`` / ``save_wav`` round-trip a
  file in a single buffer. Simple and fast for short
  clips.
* Streaming: ``wav_info`` + ``iter_chunks`` read long
  files in bounded memory. Each chunk is yielded with
  neighbor-sample padding so downstream zero-phase
  filters see real context, not reflection artifacts,
  at every boundary.
"""
import glob
import os

import soundfile as sf


WAV_EXT = ".wav"


def load_wav(path):
    """Load a WAV as float32.

    Returns
    -------
    data : ndarray
        (N,) for mono, (N, C) for multi-channel.
    sr : int
        Sample rate in Hz.
    subtype : str
        soundfile subtype tag (e.g., 'PCM_16') so save_wav
        can round-trip the original bit-depth.
    """
    info = sf.info(path)
    data, sr = sf.read(path, dtype="float32")
    return data, sr, info.subtype


def save_wav(path, data, sr, subtype):
    """Write float audio as a WAV with the given subtype."""
    os.makedirs(
        os.path.dirname(os.path.abspath(path)),
        exist_ok=True,
    )
    sf.write(path, data, sr, subtype=subtype)


def list_wavs(directory):
    """Return sorted list of .wav paths in a directory."""
    pattern = os.path.join(directory, f"*{WAV_EXT}")
    return sorted(glob.glob(pattern))


def wav_info(path):
    """Return (sr, channels, subtype, frames, duration_s).

    Cheap: reads only the header. Used by the chunked
    pipeline to size things before streaming.
    """
    info = sf.info(path)
    return {
        "sr": info.samplerate,
        "channels": info.channels,
        "subtype": info.subtype,
        "frames": info.frames,
        "duration_s": info.frames / float(info.samplerate),
    }


def scan_inputs(paths):
    """Sum bytes + duration across a list of WAVs.

    Header-only (soundfile.info) so it's cheap even for
    thousands of files. Paths that fail to probe are
    silently skipped.
    """
    total_bytes = 0
    total_s = 0.0
    for p in paths:
        try:
            total_bytes += os.path.getsize(p)
        except OSError:
            continue
        try:
            info = sf.info(p)
            total_s += info.frames / float(info.samplerate)
        except Exception:
            continue
    return total_bytes, total_s


def iter_chunks(path, chunk_samples, pad_samples):
    """Yield chunks with neighbor-sample padding.

    Each yielded dict:
        idx          : 0-based chunk index
        start_sample : first sample of the inner chunk
        end_sample   : one-past-last sample of inner
        padded       : float32 buffer with up to
                       pad_samples on each side (less at
                       file edges)
        left_pad     : samples in ``padded`` before inner
        right_pad    : samples in ``padded`` after inner

    The inner chunk is ``padded[left_pad:-right_pad]``
    (or ``padded[left_pad:]`` when right_pad == 0).
    """
    with sf.SoundFile(path) as f:
        total = f.frames
        idx = 0
        start = 0
        while start < total:
            end = min(start + chunk_samples, total)
            read_start = max(0, start - pad_samples)
            read_end = min(total, end + pad_samples)
            f.seek(read_start)
            buf = f.read(
                read_end - read_start, dtype="float32",
            )
            yield {
                "idx": idx,
                "start_sample": start,
                "end_sample": end,
                "padded": buf,
                "left_pad": start - read_start,
                "right_pad": read_end - end,
            }
            idx += 1
            start = end
