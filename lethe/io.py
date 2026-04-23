"""WAV load/save helpers that preserve bit-depth."""
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
