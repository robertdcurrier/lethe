"""Command-line interface for lethe."""
import argparse
import os
import sys

from tqdm import tqdm

from lethe import __version__, agent, db, ui
from lethe.io import list_wavs
from lethe.pipeline import (
    output_path_for, process_file, run_stamp,
)


def parse_freq_range(text):
    """Parse 'LOW,HIGH' into (int, int) with validation."""
    parts = text.split(",")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(
            f"--freq-range expects 'LOW,HIGH'; got {text!r}"
        )
    try:
        low = int(parts[0])
        high = int(parts[1])
    except ValueError:
        raise argparse.ArgumentTypeError(
            "--freq-range values must be integers; "
            f"got {text!r}"
        )
    if low <= 0 or high <= low:
        raise argparse.ArgumentTypeError(
            "--freq-range: need 0 < LOW < HIGH; "
            f"got {low},{high}"
        )
    return (low, high)


def parse_noise_sources(text):
    """Parse a comma-list into a clean list of strings."""
    return [s.strip() for s in text.split(",") if s.strip()]


def build_parser():
    """Construct the argparse parser."""
    p = argparse.ArgumentParser(
        prog="lethe",
        description="Surgical audio noise removal.",
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument("--input-file", type=str,
                     help="single WAV to process")
    src.add_argument("--input-dir", type=str,
                     help="directory of WAVs to batch")
    p.add_argument("--output-dir", type=str,
                   help="directory for denoised output")
    p.add_argument("--freq-range", type=parse_freq_range,
                   metavar="LOW,HIGH",
                   help="bandpass range Hz, e.g. 4000,20000")
    p.add_argument("--species", type=str, metavar="NAME",
                   help="pull freq_range from species DB")
    p.add_argument("--profile", type=str, metavar="NAME",
                   help="named signal profile under --species")
    p.add_argument("--noise-source",
                   type=parse_noise_sources, default=[],
                   metavar="A,B,C",
                   help="noise sources to target (informational)")
    p.add_argument("--agentic", action="store_true",
                   help="emit JSON on stdout; silence UI")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="print per-file metrics")
    p.add_argument("--version", action="version",
                   version=f"%(prog)s {__version__}")
    p.add_argument("--init-db", action="store_true",
                   help="recreate the config DB from seeds")
    p.add_argument("--list-species", action="store_true",
                   help="list available species and exit")
    p.add_argument("--list-profiles", type=str,
                   metavar="SPECIES",
                   help="list profiles for a species")
    p.add_argument("--list-noise-sources",
                   action="store_true",
                   help="list noise sources and exit")
    return p


def handle_init_db(args):
    """Recreate the DB from schema + seeds."""
    db.init_db(reseed=True)
    conn = db.connect()
    n_sp = len(db.list_species(conn))
    n_ns = len(db.list_noise_sources(conn))
    if args.agentic:
        agent.emit({
            "lethe_version": __version__,
            "action": "init_db",
            "db_path": db.DB_PATH,
            "species_count": n_sp,
            "noise_source_count": n_ns,
        })
    else:
        ui.info(f"db initialized: {db.DB_PATH}")
        ui.info(f"  species       : {n_sp}")
        ui.info(f"  noise sources : {n_ns}")
    return agent.EXIT_OK


def handle_list_species(args, conn):
    """--list-species handler."""
    items = db.list_species(conn)
    if args.agentic:
        agent.emit(agent.list_doc("species", items))
        return agent.EXIT_OK
    ui.title("species")
    for s in items:
        ui.kv(s["common_name"], s["scientific_name"])
    return agent.EXIT_OK


def handle_list_profiles(args, conn):
    """--list-profiles SPECIES handler."""
    try:
        sp = db.get_species(conn, args.list_profiles)
    except KeyError as exc:
        if args.agentic:
            agent.emit({
                "lethe_version": __version__,
                "kind": "profiles",
                "error": str(exc),
            })
        else:
            ui.error(str(exc))
        return agent.EXIT_DB
    items = db.list_profiles(conn, sp["id"])
    if args.agentic:
        agent.emit({
            "lethe_version": __version__,
            "kind": "profiles",
            "count": len(items),
            "species": sp,
            "profiles": items,
        })
        return agent.EXIT_OK
    ui.title(f"profiles for {sp['common_name']}")
    for p in items:
        ui.kv(p["name"], f"{p['freq_lo']}-{p['freq_hi']} Hz")
    return agent.EXIT_OK


def handle_list_noise_sources(args, conn):
    """--list-noise-sources handler."""
    items = db.list_noise_sources(conn)
    if args.agentic:
        agent.emit(agent.list_doc("noise_sources", items))
        return agent.EXIT_OK
    ui.title("noise sources")
    for ns in items:
        desc = (
            f"{ns['category']}  "
            f"{ns['freq_lo']}-{ns['freq_hi']} Hz  "
            f"[{ns['temporal_character']}]"
        )
        ui.kv(ns["name"], desc)
    return agent.EXIT_OK


def validate_processing(args):
    """Return exit code if processing args invalid."""
    if not (args.input_file or args.input_dir):
        ui.error(
            "one of --input-file or --input-dir is required"
        )
        return agent.EXIT_USAGE
    if not args.output_dir:
        ui.error("--output-dir is required")
        return agent.EXIT_USAGE
    if not (args.species or args.freq_range):
        ui.error(
            "one of --species or --freq-range is required"
        )
        return agent.EXIT_USAGE
    if args.profile and not args.species:
        ui.error(
            "--profile requires --species"
        )
        return agent.EXIT_USAGE
    return None


def resolve_cfg(args, conn):
    """Build the processing config dict from CLI + DB."""
    species = None
    profile = None
    if args.species:
        species = db.get_species(conn, args.species)
        profile = db.get_profile(
            conn, species["id"], args.profile,
        )
    if args.freq_range:
        freq_range = list(args.freq_range)
    else:
        freq_range = [profile["freq_lo"], profile["freq_hi"]]
    noise = []
    if args.noise_source:
        noise = db.get_noise_sources(conn, args.noise_source)
    return {
        "species": species,
        "profile": profile,
        "freq_range": freq_range,
        "noise_sources": noise,
    }


def resolve_inputs(args):
    """Return list of input WAV paths, or exit on error."""
    if args.input_file:
        if not os.path.isfile(args.input_file):
            ui.error(
                f"--input-file not found: {args.input_file}"
            )
            sys.exit(agent.EXIT_IO)
        return [args.input_file]
    if not os.path.isdir(args.input_dir):
        ui.error(
            f"--input-dir not a directory: {args.input_dir}"
        )
        sys.exit(agent.EXIT_IO)
    paths = list_wavs(args.input_dir)
    if not paths:
        ui.error(f"no .wav files in: {args.input_dir}")
        sys.exit(agent.EXIT_IO)
    return paths


def print_metrics(m):
    """Verbose per-file metrics dump (human-facing)."""
    ui.kv("path", m["in_path"])
    ui.kv("sr", f"{m['sr']} Hz")
    ui.kv("channels", m["channels"])
    ui.kv("duration", f"{m['duration_s']:.2f} s")
    ui.kv("subtype", m["subtype"])
    ui.kv("pre rms", f"{m['pre_rms_dbfs']:.2f} dBFS")
    ui.kv("post rms", f"{m['post_rms_dbfs']:.2f} dBFS")
    ui.kv("delta", f"{m['delta_db']:+.2f} dB")
    pre_b = m["pre_band_db"]
    post_b = m["post_band_db"]
    ui.kv(
        "sub band",
        f"pre={pre_b['sub_band_db']:.2f}  "
        f"post={post_b['sub_band_db']:.2f}",
    )
    ui.kv(
        "signal band",
        f"pre={pre_b['signal_band_db']:.2f}  "
        f"post={post_b['signal_band_db']:.2f}",
    )
    ui.kv(
        "super band",
        f"pre={pre_b['super_band_db']:.2f}  "
        f"post={post_b['super_band_db']:.2f}",
    )
    ui.kv("elapsed", f"{m['elapsed_s']:.2f} s")


def print_header(cfg, stamp, inputs, output_dir):
    """Render human-facing run header."""
    ui.title(f"lethe v{__version__}")
    if cfg["species"]:
        ui.info(
            "species    = "
            f"{cfg['species']['common_name']}  "
            f"({cfg['species']['scientific_name']})"
        )
        if cfg["profile"]:
            ui.info(f"profile    = {cfg['profile']['name']}")
    lo, hi = cfg["freq_range"]
    ui.info(f"freq range = {lo}-{hi} Hz")
    if cfg["noise_sources"]:
        names = ", ".join(
            n["name"] for n in cfg["noise_sources"]
        )
        ui.info(f"noise      = {names}")
    ui.info(f"run stamp  = {stamp}")
    ui.info(f"{len(inputs)} file(s) -> {output_dir}")


def run_processing(args, conn):
    """Process inputs and emit output (human or agentic)."""
    cfg = resolve_cfg(args, conn)
    inputs = resolve_inputs(args)
    os.makedirs(args.output_dir, exist_ok=True)
    stamp = run_stamp()
    if not args.agentic:
        print_header(cfg, stamp, inputs, args.output_dir)
    metrics, errors = process_all(inputs, cfg, stamp, args)
    exit_code = (
        agent.EXIT_OK if not errors else agent.EXIT_PROCESSING
    )
    if args.agentic:
        agent.emit(agent.build_envelope(
            stamp, cfg, inputs, args.output_dir,
            metrics, errors, exit_code,
        ))
    else:
        ui.info("done.")
    return exit_code


def process_all(inputs, cfg, stamp, args):
    """Iterate inputs, collect metrics + structured errors."""
    metrics, errors = [], []
    iter_files = inputs
    if not args.agentic:
        iter_files = tqdm(
            inputs, unit="file",
            disable=len(inputs) == 1,
        )
    for in_path in iter_files:
        out_path = output_path_for(
            in_path, args.output_dir, stamp,
        )
        try:
            m = process_file(in_path, out_path, cfg)
        except Exception as exc:
            errors.append(agent.error_record(
                "process_file", exc, in_path,
            ))
            continue
        metrics.append(m)
        if args.verbose and not args.agentic:
            print_metrics(m)
    return metrics, errors


def dispatch(args):
    """Route to init / list / process handlers."""
    if args.agentic:
        ui.set_quiet(True)
    if args.init_db:
        return handle_init_db(args)
    conn = db.connect()
    if args.list_species:
        return handle_list_species(args, conn)
    if args.list_profiles is not None:
        return handle_list_profiles(args, conn)
    if args.list_noise_sources:
        return handle_list_noise_sources(args, conn)
    bad = validate_processing(args)
    if bad is not None:
        return bad
    try:
        return run_processing(args, conn)
    except KeyError as exc:
        ui.error(str(exc))
        if args.agentic:
            agent.emit({
                "lethe_version": __version__,
                "exit_code": agent.EXIT_DB,
                "errors": [agent.error_record(
                    "resolve_cfg", exc,
                )],
            })
        return agent.EXIT_DB


def main(argv=None):
    """CLI entry point; returns shell exit status."""
    return dispatch(build_parser().parse_args(argv))
