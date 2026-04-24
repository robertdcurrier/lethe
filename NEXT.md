# Next up: agentic system/status in the JSON envelope

**Why:** Human-facing SYSTEM + RUN boxes are invaluable for Claude
Desktop / supervising agents too, but the information is currently
trapped in stdout (suppressed under `--agentic`). Claude can only
*approximate* wall time from per-file `elapsed_s` (max ≈ wall under
threading; sum is wrong), and has no system context at all.

**Goal:** Let Claude say *"I processed 5 files in 12.9s (252×
realtime) using 5 threads on an M2 Max"* by reading the envelope
directly, with zero client-side arithmetic.

## Schema additions (processing payloads only)

Three new top-level keys. Flat, no `status` wrapper — matches the
existing style of `config` / `files` / `errors` living at top level.

```json
{
  "lethe_version": "0.1.0",
  "stamp": "20260424_154828",
  "exit_code": 0,
  "elapsed_s": 12.92,
  "system": {
    "cpu": "Apple M2 Max",
    "freq_ghz": null,
    "cores_phys": 12,
    "cores_logical": 12,
    "mem_total_gb": 64.0,
    "mem_avail_gb": 28.7,
    "workers": 5
  },
  "totals": {
    "files": 5,
    "succeeded": 5,
    "failed": 0,
    "total_audio_s": 3253.3,
    "total_bytes": 624570880,
    "realtime_multiplier": 251.8
  },
  "config": {...},
  "files": [...],
  "errors": []
}
```

### Why each

- **`elapsed_s`** (top-level): wall clock for the whole run.
  Mirrors the per-file field name. Claude reports directly, no math.
- **`system`**: CPU/cores/memory snapshot + effective worker count.
  Workers lives here because it's a resource decision, not a config
  knob. Source: `ui.system_info()` (already exists).
- **`totals`**: pre-computed aggregates. Claude never needs to sum
  `files[].elapsed_s` (which double-counts under threading).
  `realtime_multiplier = total_audio_s / elapsed_s` is the headline
  metric — expose it so Claude's summary doesn't risk rounding.

### Scope

- **Include** these fields on processing envelopes only
  (i.e., `run_processing` path).
- **Exclude** from `--list-species`, `--list-profiles`,
  `--list-noise-sources`, `--init-db` envelopes — they don't make
  sense there.

## Implementation sketch

~30 lines, no MCP server changes.

1. **`lethe/cli.py::run_processing`** — stamp `t0 = time.time()`
   at function entry; compute `elapsed = time.time() - t0` just
   before emitting. Call `ui.system_info()` once. Build a `totals`
   dict from `scan_inputs(inputs)` + the length of `metrics` and
   `errors`.
2. **`lethe/agent.py::build_envelope`** — take new kwargs
   `elapsed_s`, `system`, `totals`; merge into the returned dict.
   Keep them optional so non-processing callers (init/list) stay
   unchanged.
3. **`README.md`** — add `elapsed_s`, `system`, `totals` to the
   processing-payload example in the Agent contract section.
4. **Smoke test** — rerun SWSS 5-file batch with `--agentic`;
   verify `elapsed_s` matches `time` wall, `totals.succeeded == 5`,
   `totals.realtime_multiplier ≈ 250`.

## Open questions

- **`files_per_s`** in `totals` too? Probably yes — cheap, useful
  for Claude comparing run throughput over time.
- **Run-start wall clock** (ISO8601 string)? `stamp` already
  encodes it, so probably no. Keep the envelope lean.
- **Memory-at-start vs peak**? Peak would need a sampling thread.
  Not worth the complexity for v0.2; revisit if someone asks.
