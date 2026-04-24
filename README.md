# Lethe

[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![Status: alpha](https://img.shields.io/badge/status-alpha-orange)](#status)

**AI noise reduction for passive acoustic recordings.**
*Hear what matters. Every detail. Every time.*

Lethe is an [OCEANCODA](#) passive-acoustics tool for surgically
reducing noise in hydrophone and field recordings while preserving
biologically or scientifically meaningful signal. Built agent-native
from day one: species-aware, configurable, and designed to be driven
by a human *or* a supervising AI via an MCP server.

Named for the Greek river of oblivion — what passes through is
forgotten. Part of OCEANCODA's mythological pantheon alongside
POSEIDON, OLÓRIN, and GANDALF.

---

## Requirements

- Python **3.10 or newer** (required by the MCP SDK)
- macOS or Linux (Windows works for CLI; MCP path untested)

## Install

```bash
git clone https://github.com/robertdcurrier/lethe.git
cd lethe
pip install -e .          # CLI only
pip install -e ".[mcp]"   # CLI + MCP server for Claude Desktop
```

Editable install via `pyproject.toml` pulls dependencies (`numpy`,
`scipy`, `soundfile`, `tqdm`, `colorama`; plus `mcp` with the
`[mcp]` extra) and registers two console commands:

- `lethe` — the CLI
- `lethe-mcp` — the MCP server (with the `[mcp]` extra)

Prefer not to install? Just run the package directly:

```bash
python -m lethe ...       # uses the installed deps
```

On first run, Lethe initializes a small SQLite config database from
`lethe/data/schema.sql` + `lethe/data/seeds.sql`.

## Quick start — CLI

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

Output filenames are `<input_stem>_<YYYYMMDD_HHMMSS>.wav`, so
successive runs never collide (and platform audio caches like Apple
Music can't fool you into re-hearing the original).

### Chunking

Default output is a single concatenated WAV — the same file you'd
get without chunking at all, bit-for-bit. Chunking is primarily a
**diagnostic tool**: use `--emit-chunks` to write short segments
you can drop into Audacity, Raven, or any reviewer that chokes on
30-minute files:

```bash
lethe --species bottlenose_dolphin --profile whistle \
      --chunk-length 10 --emit-chunks \
      --input-file gold_standard.wav \
      --output-dir out/
# => out/gold_standard_<stamp>_chunk_000.wav ... _chunk_005.wav
```

Under the hood, every run is processed in 60 s windows (override
with `--chunk-length SECONDS`) so the agentic envelope always
carries a `chunks[]` array with per-chunk pre/post RMS and
sub/signal/super band energies. A supervising agent can localize
signal — "which 10-second window has the best
`signal_band_db - sub_band_db`?" — without additional tooling. This
streaming also keeps memory bounded on long hydrophone deployments.

Pass `--chunk-length 0` to disable chunking entirely (single chunk
spanning the whole file; behaves exactly like v0.1.0).

## Quick start — Claude Desktop

Install with the MCP extra (`pip install -e ".[mcp]"`), then add to
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

Find your absolute path with `which lethe-mcp`. Restart Claude
Desktop. Four tools appear:

| MCP tool | Purpose |
|---|---|
| `lethe_list_species` | Discover available species |
| `lethe_list_profiles` | List signal profiles for a species |
| `lethe_list_noise_sources` | List the noise-source catalog |
| `lethe_denoise` | Run denoising on a WAV file |

Each tool returns the same structured JSON envelope documented below.
The CLI's `--agentic` contract *is* the MCP contract — no duplicated
surface.

### Example conversation

> **User:** Denoise `/data/gold_standard.wav` using lethe. Target
> bottlenose dolphin whistles. Save output in `/tmp` and give me a
> report on the findings.

> **Claude (paraphrased, using the returned JSON):**
> Clean run. Output saved to `/tmp/gold_standard_<stamp>.wav`.
> Input: 60 s, 48 kHz stereo PCM-16.
>
> | Band | Pre (dB) | Post (dB) | Δ |
> |---|---|---|---|
> | Sub (< 4 kHz) | −36.1 | −58.5 | −22.4 |
> | Signal (4–20 kHz) | −36.8 | −36.9 | −0.2 |
> | Super (> 20 kHz) | −43.3 | −62.7 | −19.4 |
>
> Signal band is effectively untouched while both out-of-band
> regions are hammered by ~20 dB each. The sub-band knockdown
> is the operationally valuable one — ship engine and flow noise
> live there.  0.62 s wall-clock for 60 s stereo (~96× realtime).

Claude reasons about SNR from `band_energy` values without any
extra plumbing.

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
| `--chunk-length SECONDS` | Chunk size in seconds (default 60; `<=0` disables) |
| `--emit-chunks` | Write one WAV per chunk instead of a single concatenated output |
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

### Processing payload

```json
{
  "lethe_version": "0.1.0",
  "stamp": "20260423_101413",
  "exit_code": 0,
  "config": {
    "species": {...},
    "profile": {...},
    "freq_range": [4000, 20000],
    "noise_sources": [...],
    "chunk_length_s": 60.0,
    "emit_chunks": false
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
      "chunk_length_s": 60.0,
      "chunk_count": 6,
      "chunks": [
        {
          "idx": 0,
          "start_s": 0.0,
          "end_s": 10.0,
          "frames": 480000,
          "pre_rms_dbfs": -33.6,
          "post_rms_dbfs": -38.2,
          "pre_band_db": {...},
          "post_band_db": {...}
        }
      ],
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

### Chunks

`chunks[]` is always present. File-level `pre_rms_dbfs`,
`post_rms_dbfs`, and band metrics are power-weighted aggregates of
the per-chunk values, so an agent can either summarize at the file
level or localize — "which 10-second window has the best
`signal_band_db - sub_band_db`?" — without additional tooling.

When `emit_chunks` is `true`:

- The file record has **no** top-level `out_path`.
- Each chunk dict carries its own `out_path` at
  `<stem>_<stamp>_chunk_<NNN>.wav`, matching the guardian handoff
  naming convention.

### Error payload

When something fails under `--agentic`, structured errors replace
human-facing messages:

```json
{
  "lethe_version": "0.1.0",
  "exit_code": 3,
  "errors": [
    {
      "stage": "resolve_cfg",
      "message": "unknown species: 'narwhal'"
    }
  ]
}
```

## Configuration database

Config lives in a small SQLite database at `lethe/data/lethe.db`
(gitignored; regenerated from SQL). Tables:

- **`species`** — scientific and common name
- **`signal_profile`** — per-species band of interest (e.g.,
  bottlenose dolphin `whistle` = 4000–20000 Hz)
- **`noise_source`** — catalog of known acoustic noise sources
  (ship_engine, propeller_cavitation, snapping_shrimp,
  seismic_airgun, flow_noise)

### Extending the database

Add a new species and profile directly via SQL:

```sql
INSERT INTO species (scientific_name, common_name, notes)
VALUES ('Orcinus orca', 'killer whale', 'Delphinidae');

INSERT INTO signal_profile
  (species_id, name, freq_lo, freq_hi, notes)
SELECT id, 'whistle', 500, 25000, 'Orca whistles and pulsed calls'
FROM species WHERE scientific_name = 'Orcinus orca';
```

Or append to `lethe/data/seeds.sql` and regenerate:

```bash
lethe --init-db
```

The same pattern applies to `noise_source`.

## Audio data

**Lethe ships no audio.** You bring your own recordings. Audio files
of any common format (`*.wav`, `*.flac`, `*.mp3`, `*.aif`, `*.m4a`,
`*.ogg`) are gitignored by policy — end users manage their own data.

## Architecture

```
lethe/
├── pyproject.toml           # Install metadata + console entries
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

## Troubleshooting

**`lethe: command not found` after install**
Editable installs can miss the `bin/` directory on PATH. Try
`python -m lethe ...` instead, or `pip install -e .` again inside
an activated virtualenv.

**Claude Desktop doesn't see the `lethe` tools**
1. Confirm the absolute path in `claude_desktop_config.json` matches
   `which lethe-mcp`.
2. Fully quit and restart Claude Desktop (⌘Q, then relaunch).
3. Check the Claude Desktop log for MCP errors.

**"species has multiple profiles; use --profile to pick one of..."**
The DB has more than one profile for that species (e.g. bottlenose
dolphin has `whistle`, `burst_pulse`, `echolocation_click`). Pick
one explicitly with `--profile`.

**"high (N) must be < Nyquist (M)"**
Your `--freq-range` upper bound exceeds half the sample rate. Lower
the high frequency or resample to a higher SR.

## Standards

- Python 3.10+, PEP-8
- ≤ 79 char lines, ≤ 35 line functions (excluding docstrings)
- Stdlib + `numpy`, `scipy`, `soundfile`, `tqdm`, `colorama`,
  optionally `mcp`

## Status

**v0.1.0** — CLI, config DB, batch processing, agentic JSON surface,
MCP server for Claude Desktop, single DSP stage (Butterworth
bandpass). Next: targeted stages driven by `--noise-source` (tonal
notching, impulsive gating) and a supervising-agent self-tuning
loop.

## License

[MIT](LICENSE)
