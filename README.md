# Lethe

**AI noise reduction for passive acoustic recordings.**
*Hear what matters. Every detail. Every time.*

Lethe is an [OCEANCODA](#) passive-acoustics tool for surgically
reducing noise in hydrophone and field recordings while preserving
biologically or scientifically meaningful signal. Built agent-native
from day one: species-aware, configurable, and designed to be driven
by a human *or* a supervising AI.

Named for the Greek river of oblivion — what passes through is
forgotten. Part of OCEANCODA's mythological pantheon alongside
POSEIDON, OLÓRIN, and GANDALF.

---

## Install

```bash
git clone https://github.com/robertdcurrier/lethe.git
cd lethe
pip install -e .
```

Editable install via `pyproject.toml` pulls dependencies (`numpy`,
`scipy`, `soundfile`, `tqdm`, `colorama`) and registers a `lethe`
console command. Prefer not to install? Just run the package
directly with `python -m lethe` (requires deps installed manually).

On first run, Lethe initializes a small SQLite config database from
`lethe/data/schema.sql` + `lethe/data/seeds.sql`.

## Quick start

Process a single WAV using a species-driven band:

```bash
lethe --species bottlenose_dolphin --profile whistle \
      --input-file recording.wav \
      --output-dir out/
```

Batch a directory:

```bash
lethe --species bottlenose_dolphin --profile whistle \
      --input-dir recordings/ \
      --output-dir out/
```

Or skip the database and set the band manually:

```bash
lethe --freq-range 4000,20000 \
      --input-file recording.wav \
      --output-dir out/
```

Same thing without installing:

```bash
python -m lethe --species bottlenose_dolphin --profile whistle \
                --input-file recording.wav \
                --output-dir out/
```

Output filenames are `<input_stem>_<YYYYMMDD_HHMMSS>.wav`, so
successive runs never collide (and platform audio caches like Apple
Music can't fool you into re-hearing the original).

## CLI reference

### Processing

| Flag | Purpose |
|---|---|
| `--input-file PATH` | Single WAV to process |
| `--input-dir DIR` | Directory of WAVs (batch) |
| `--output-dir DIR` | Required; created if missing |
| `--freq-range LOW,HIGH` | Bandpass range in Hz |
| `--species NAME` | Pull freq_range from the DB |
| `--profile NAME` | Named signal profile under `--species` |
| `--noise-source A,B,C` | Noise sources to target (wired for future stages) |
| `-v, --verbose` | Per-file metrics |
| `--agentic` | Emit structured JSON on stdout; silence UI |

### Discovery (for agents)

| Flag | Purpose |
|---|---|
| `--list-species` | List species from the DB |
| `--list-profiles SPECIES` | List signal profiles for a species |
| `--list-noise-sources` | List the noise-source catalog |

### Admin

| Flag | Purpose |
|---|---|
| `--init-db` | Recreate the config DB from schema + seeds |
| `--version` | Print version |

## Agent contract

`--agentic` emits a single JSON document on **stdout** and suppresses
all human-facing UI. stdout is data; stderr is chatter.

Stable exit codes:

| Code | Meaning |
|---|---|
| `0` | Success |
| `2` | Usage error |
| `3` | Config DB error (unknown species / profile / noise source) |
| `4` | I/O error (missing input) |
| `5` | Processing error (one or more files failed) |

Processing payload:

```json
{
  "lethe_version": "0.1.0",
  "stamp": "20260423_101413",
  "exit_code": 0,
  "config": {
    "species": {...},
    "profile": {...},
    "freq_range": [4000, 20000],
    "noise_sources": [...]
  },
  "input_count": 1,
  "output_dir": "/abs/path/out",
  "files": [
    {
      "in_path": "...",
      "out_path": "...",
      "sr": 48000,
      "channels": 2,
      "duration_s": 60.0,
      "subtype": "PCM_16",
      "pre_rms_dbfs": -30.9,
      "post_rms_dbfs": -36.9,
      "delta_db": 6.0,
      "pre_band_db": {
        "sub_band_db": -36.1,
        "signal_band_db": -36.8,
        "super_band_db": -43.3
      },
      "post_band_db": {
        "sub_band_db": -58.5,
        "signal_band_db": -36.9,
        "super_band_db": -62.7
      },
      "elapsed_s": 0.61
    }
  ],
  "errors": []
}
```

The `band_energy` metrics are the agentic differentiator: sub-band
(below `freq_lo`), signal-band (inside `freq_lo..freq_hi`), and
super-band (above `freq_hi`) RMS — enough for a supervising agent to
reason about SNR, not just overall level.

## Configuration database

Config lives in a small SQLite database at `lethe/data/lethe.db`
(gitignored; regenerated from SQL). Tables:

- **`species`** — scientific and common name
- **`signal_profile`** — per-species band of interest (e.g.,
  bottlenose dolphin `whistle` = 4000–20000 Hz)
- **`noise_source`** — catalog of known acoustic noise sources
  (ship_engine, propeller_cavitation, snapping_shrimp,
  seismic_airgun, flow_noise)

Extend by editing `lethe/data/seeds.sql` and running `--init-db`, or
by issuing SQL directly against the DB.

## Audio data

**Lethe ships no audio.** You bring your own recordings. Audio files
of any common format (`*.wav`, `*.flac`, `*.mp3`, `*.aif`, `*.m4a`,
`*.ogg`) are gitignored by policy — end users manage their own data.

## Architecture

```
lethe/
├── pyproject.toml           # Install metadata + `lethe` console entry
├── README.md
├── LICENSE
└── lethe/                   # Package
    ├── __init__.py
    ├── __main__.py          # `python -m lethe` entry
    ├── cli.py               # argparse + dispatch + handlers
    ├── db.py                # SQLite access
    ├── dsp.py               # Filters (v0.1: Butterworth bandpass)
    ├── io.py                # WAV load/save (preserves bit depth)
    ├── pipeline.py          # Stage runner + metrics
    ├── ui.py                # colorama helpers (silenced in --agentic)
    ├── agent.py             # JSON envelope + exit codes
    ├── mcp_server.py        # MCP server (Claude Desktop)
    └── data/
        ├── schema.sql
        └── seeds.sql
```

New denoising stages are added as callables in `pipeline.py`; the
`--noise-source` flag is already wired for stages that consult it.

## Standards

- Python 3
- PEP-8 compliant
- ≤ 79 char lines, ≤ 35 line functions (excluding docstrings)
- Stdlib + `numpy`, `scipy`, `soundfile`, `tqdm`, `colorama`

## Claude Desktop (MCP server)

Lethe ships an optional MCP (Model Context Protocol) server that
exposes its capabilities as tools in Claude Desktop (and any other
MCP-compatible client). Each tool shells out to the `lethe` CLI in
`--agentic` mode — the CLI's JSON contract *is* the MCP contract, so
there is no duplicated surface.

Install with the MCP extra:

```bash
pip install -e ".[mcp]"
```

This registers a `lethe-mcp` console script. Then add it to your
Claude Desktop config at
`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "lethe": {
      "command": "/absolute/path/to/lethe-mcp"
    }
  }
}
```

Find your path with `which lethe-mcp`. Restart Claude Desktop. Lethe
will appear in the tool picker with four tools:

| MCP tool | Purpose |
|---|---|
| `lethe_list_species` | Discover available species |
| `lethe_list_profiles` | List signal profiles for a species |
| `lethe_list_noise_sources` | List the noise-source catalog |
| `lethe_denoise` | Run denoising on a WAV file |

Each returns the same structured JSON envelope documented above.

## Status

**v0.1.0** — CLI, config DB, batch processing, agentic JSON surface,
MCP server for Claude Desktop, single DSP stage (Butterworth
bandpass). More stages coming.

## License

[MIT](LICENSE)
