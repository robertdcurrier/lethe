"""MCP server exposing lethe to Claude Desktop and friends.

Each tool shells out to the installed `lethe` CLI in
--agentic mode and returns the parsed JSON envelope to
the caller. The CLI's agentic contract (config echo,
per-file band-energy metrics, structured errors, stable
exit codes) IS the MCP contract -- no separate surface.

Critical invariant for MCP stdio transport: stdout is
reserved for JSON-RPC. All logging goes to stderr.
"""
import json
import logging
import subprocess
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP


logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("lethe.mcp")

mcp = FastMCP("lethe")


def _run_lethe(args):
    """Invoke the lethe CLI; return parsed JSON (or error)."""
    cmd = [sys.executable, "-m", "lethe", *args, "--agentic"]
    logger.info("exec: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False,
        )
    except FileNotFoundError as exc:
        return {
            "error": "lethe CLI not found",
            "detail": str(exc),
        }
    stdout = result.stdout.strip()
    if stdout:
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            return {
                "error": "malformed JSON from lethe",
                "detail": str(exc),
                "stdout": stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
            }
    return {
        "error": "no output from lethe",
        "stderr": result.stderr,
        "exit_code": result.returncode,
    }


def _denoise_args(input_file, output_dir, species,
                  profile, freq_range, noise_sources,
                  chunk_length, emit_chunks):
    """Build argv list for the `lethe` CLI."""
    args = [
        "--input-file", input_file,
        "--output-dir", output_dir,
    ]
    if species:
        args.extend(["--species", species])
    if profile:
        args.extend(["--profile", profile])
    if freq_range:
        lo, hi = freq_range
        args.extend(["--freq-range", f"{int(lo)},{int(hi)}"])
    if noise_sources:
        args.extend([
            "--noise-source", ",".join(noise_sources),
        ])
    if chunk_length is not None:
        args.extend(["--chunk-length", f"{float(chunk_length)}"])
    if emit_chunks:
        args.append("--emit-chunks")
    return args


@mcp.tool()
async def lethe_list_species() -> dict:
    """List available species from the lethe config DB.

    Returns the full JSON envelope (items=[{id, scientific_name,
    common_name, notes}, ...]). Useful for a supervising agent
    to discover what it can target.
    """
    return _run_lethe(["--list-species"])


@mcp.tool()
async def lethe_list_profiles(species: str) -> dict:
    """List signal profiles for a given species.

    Args:
        species: common or scientific name (underscores or
            spaces accepted), e.g. 'bottlenose_dolphin' or
            'Tursiops truncatus'.

    Returns the species record plus its profiles
    (name, freq_lo, freq_hi, notes).
    """
    return _run_lethe(["--list-profiles", species])


@mcp.tool()
async def lethe_list_noise_sources() -> dict:
    """List the catalog of known noise sources.

    Returns items with name, category, freq_lo, freq_hi,
    temporal_character, notes. Used to populate the
    `noise_sources` argument on lethe_denoise.
    """
    return _run_lethe(["--list-noise-sources"])


@mcp.tool()
async def lethe_denoise(
    input_file: str,
    output_dir: str,
    species: Optional[str] = None,
    profile: Optional[str] = None,
    freq_range: Optional[list] = None,
    noise_sources: Optional[list] = None,
    chunk_length: float = 60.0,
    emit_chunks: bool = False,
) -> dict:
    """Denoise one WAV file with lethe.

    Provide EITHER species (with optional profile) OR
    freq_range. freq_range overrides if both are given.

    Chunking
    --------
    Long recordings are processed in chunks of
    ``chunk_length`` seconds (default 60). Chunking is
    always on so the returned envelope carries a
    ``chunks[]`` array — set ``chunk_length <= 0`` to
    coerce a single chunk spanning the whole file.

    Output shape depends on ``emit_chunks``:

    * ``emit_chunks=False`` (default): one streamed
      WAV at ``<stem>_<stamp>.wav`` in ``output_dir``.
      The file record has a top-level ``out_path``;
      chunks carry metrics only.
    * ``emit_chunks=True``: N separate WAVs named
      ``<stem>_<stamp>_chunk_<NNN>.wav``. The file
      record has no top-level ``out_path``; each chunk
      dict carries its own ``out_path``. Use this when
      feeding chunks to a downstream classifier (e.g.,
      guardian) or for testing/iteration.

    Use ``emit_chunks`` when the user says "chunk this"
    or asks for per-chunk files; default otherwise.

    Args:
        input_file: absolute path to the input WAV.
        output_dir: directory for denoised output.
        species: species name from the config DB
            (e.g. 'bottlenose_dolphin').
        profile: signal profile under species
            (e.g. 'whistle'). Required when the species
            has multiple profiles.
        freq_range: [low_hz, high_hz] bandpass range.
            Overrides species/profile defaults.
        noise_sources: list of noise-source names from
            the catalog (e.g. ['ship_engine',
            'snapping_shrimp']). Informational in v0.1.
        chunk_length: chunk size in seconds
            (default 60.0). <= 0 disables chunking.
        emit_chunks: write one WAV per chunk instead of
            a single concatenated output.

    Returns:
        The full agentic JSON envelope. Per-file record
        includes ``chunks[]`` with idx, start_s, end_s,
        pre/post RMS, pre/post sub/signal/super band
        energies, and (when emit_chunks) ``out_path``.
    """
    args = _denoise_args(
        input_file, output_dir, species, profile,
        freq_range, noise_sources,
        chunk_length, emit_chunks,
    )
    return _run_lethe(args)


def main():
    """Entry point for the `lethe-mcp` console script."""
    logger.info("starting lethe MCP server (stdio)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
