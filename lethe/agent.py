"""Agentic JSON output assembly for lethe.

When --agentic is set, human UI is suppressed and a
single JSON document describing the run is written to
stdout. Intended for consumption by supervising agents
performing capability discovery and self-tuning.
"""
import json
import os
import sys

from lethe import __version__


EXIT_OK = 0
EXIT_USAGE = 2
EXIT_DB = 3
EXIT_IO = 4
EXIT_PROCESSING = 5


def build_envelope(stamp, cfg, inputs, output_dir,
                   file_metrics, errors, exit_code):
    """Compose the top-level agentic JSON envelope."""
    return {
        "lethe_version": __version__,
        "stamp": stamp,
        "exit_code": exit_code,
        "config": cfg,
        "input_count": len(inputs),
        "output_dir": os.path.abspath(output_dir),
        "files": file_metrics,
        "errors": errors,
    }


def emit(doc):
    """Write a JSON document to stdout as one line."""
    sys.stdout.write(json.dumps(doc, default=str))
    sys.stdout.write("\n")
    sys.stdout.flush()


def list_doc(kind, items):
    """Envelope for --list-* output: {kind, count, items}."""
    return {
        "lethe_version": __version__,
        "kind": kind,
        "count": len(items),
        "items": items,
    }


def error_record(stage, message, path=None):
    """Structured error entry for the errors[] array."""
    e = {"stage": stage, "message": str(message)}
    if path is not None:
        e["path"] = path
    return e
