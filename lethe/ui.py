"""Colorama-tinted console helpers for lethe.

Human-facing output. Call set_quiet(True) under --agentic
to silence everything here; the agentic JSON emitter
owns stdout in that mode.

Also provides box-drawing primitives and a system probe
used by the startup summary screen.
"""
import os
import platform
import re
import subprocess

from colorama import Fore, Style, init as _colorama_init

from lethe import __version__


_colorama_init()
_quiet = False

BOX_W = 60
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def set_quiet(flag):
    """Globally enable/disable console output."""
    global _quiet
    _quiet = bool(flag)


def title(msg):
    """Cyan bright-bold header line."""
    if _quiet:
        return
    print(
        f"{Fore.CYAN}{Style.BRIGHT}{msg}"
        f"{Style.RESET_ALL}"
    )


def info(msg):
    """Green [INFO] line."""
    if _quiet:
        return
    print(
        f"{Fore.GREEN}[INFO]{Style.RESET_ALL} {msg}"
    )


def warn(msg):
    """Yellow [WARN] line."""
    if _quiet:
        return
    print(
        f"{Fore.YELLOW}[WARN]{Style.RESET_ALL} {msg}"
    )


def error(msg):
    """Red [ERROR] line."""
    if _quiet:
        return
    print(
        f"{Fore.RED}[ERROR]{Style.RESET_ALL} {msg}"
    )


def kv(key, value):
    """Dim key : bright value pair (for verbose dumps)."""
    if _quiet:
        return
    print(
        f"  {Style.DIM}{key:14s}{Style.RESET_ALL} "
        f"{Style.BRIGHT}{value}{Style.RESET_ALL}"
    )


def _vlen(s):
    """Visible length (strips ANSI escapes)."""
    return len(_ANSI.sub("", s))


def _box_top(caption=None, width=BOX_W):
    """Top border; caption (if any) is centered on the rule."""
    if not caption:
        return (
            f"{Fore.CYAN}╔{'═' * width}╗{Style.RESET_ALL}"
        )
    tag = f" {caption} "
    pad = max(width - len(tag), 2)
    left = pad // 2
    right = pad - left
    return (
        f"{Fore.CYAN}╔{'═' * left}{Fore.YELLOW}{tag}"
        f"{Fore.CYAN}{'═' * right}╗{Style.RESET_ALL}"
    )


def _box_bottom(width=BOX_W):
    """Bottom border."""
    return f"{Fore.CYAN}╚{'═' * width}╝{Style.RESET_ALL}"


def _box_row(label, value, width=BOX_W):
    """Label/value row inside a box; truncates long values."""
    label = str(label)[:14]
    value = str(value)
    prefix = 2 + 14 + 2
    avail = width - prefix
    if len(value) > avail:
        value = value[: max(avail - 1, 0)] + "…"
    content = (
        f"  {Fore.GREEN}{label:<14}{Style.RESET_ALL}: {value}"
    )
    pad = width - _vlen(content)
    return (
        f"{Fore.CYAN}║{Style.RESET_ALL}{content}"
        f"{' ' * max(pad, 0)}{Fore.CYAN}║{Style.RESET_ALL}"
    )


def _box_center(text, width=BOX_W, color=None):
    """Centered single-line row (text may contain ANSI)."""
    vl = _vlen(text)
    pad = max(width - vl, 0)
    left = pad // 2
    right = pad - left
    body = f"{color}{text}{Style.RESET_ALL}" if color else text
    return (
        f"{Fore.CYAN}║{Style.RESET_ALL}{' ' * left}{body}"
        f"{' ' * right}{Fore.CYAN}║{Style.RESET_ALL}"
    )


def _cpu_name():
    """Human-readable CPU model string, best effort."""
    name = platform.processor() or ""
    if name and name not in ("arm", "arm64", "i386", "x86_64"):
        return name
    if platform.system() == "Darwin":
        try:
            out = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, check=False,
            )
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except Exception:
            pass
    if platform.system() == "Linux":
        try:
            with open("/proc/cpuinfo") as fh:
                for line in fh:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
        except Exception:
            pass
    return name or platform.machine() or "unknown"


def system_info():
    """Snapshot of CPU / cores / memory for the summary box."""
    import psutil
    try:
        freq = psutil.cpu_freq()
    except Exception:
        freq = None
    mem = psutil.virtual_memory()
    cores_phys = (
        psutil.cpu_count(logical=False) or os.cpu_count() or 0
    )
    return {
        "cpu": _cpu_name(),
        "freq_ghz": (freq.current / 1000.0) if freq else None,
        "cores_phys": cores_phys,
        "cores_logical": psutil.cpu_count(logical=True) or 0,
        "mem_total_gb": mem.total / (1024 ** 3),
        "mem_avail_gb": mem.available / (1024 ** 3),
    }


def print_banner():
    """Welcome banner: version and tagline."""
    if _quiet:
        return
    print(_box_top(width=BOX_W))
    print(_box_center(
        f"LETHE v{__version__}", color=Fore.YELLOW,
    ))
    print(_box_center(
        "Surgical AI noise reduction for PAM",
    ))
    print(_box_bottom(width=BOX_W))
    print()


def print_system_box(sysinfo, workers):
    """System info + worker count."""
    if _quiet:
        return
    freq = sysinfo.get("freq_ghz")
    cpu = sysinfo["cpu"]
    cpu_line = (
        f"{cpu} @ {freq:.2f} GHz" if freq else cpu
    )
    mem_line = (
        f"{sysinfo['mem_total_gb']:.1f} GB total, "
        f"{sysinfo['mem_avail_gb']:.1f} GB available"
    )
    print(_box_top(caption="SYSTEM", width=BOX_W))
    print(_box_row("CPU", cpu_line))
    print(_box_row(
        "Cores",
        f"{sysinfo['cores_phys']} physical / "
        f"{sysinfo['cores_logical']} logical",
    ))
    print(_box_row("Memory", mem_line))
    print(_box_row("Workers", str(workers)))
    print(_box_bottom(width=BOX_W))
    print()


def _fmt_mb(n_bytes):
    """Human-readable size in MB / GB."""
    mb = n_bytes / (1024 ** 2)
    if mb >= 1024:
        return f"{mb / 1024:.2f} GB"
    return f"{mb:.1f} MB"


def _fmt_duration(seconds):
    """Human-readable duration in s / min / h."""
    if seconds < 60:
        return f"{seconds:.1f} s"
    if seconds < 3600:
        return f"{seconds / 60:.1f} min"
    return f"{seconds / 3600:.2f} h"


def print_run_box(cfg, stamp, inputs, output_dir,
                  total_bytes, total_duration_s):
    """Run-config summary: species, files, sizes, paths."""
    if _quiet:
        return
    lo, hi = cfg["freq_range"]
    sp = cfg.get("species")
    prof = cfg.get("profile")
    print(_box_top(caption="RUN", width=BOX_W))
    if sp:
        print(_box_row(
            "Species",
            f"{sp['common_name']} ({sp['scientific_name']})",
        ))
    if prof:
        print(_box_row(
            "Profile",
            f"{prof['name']} ({lo}-{hi} Hz)",
        ))
    else:
        print(_box_row("Freq range", f"{lo}-{hi} Hz"))
    cl = cfg.get("chunk_length_s") or 0
    mode = "emit" if cfg.get("emit_chunks") else "single"
    chunk_s = f"{cl:g} s ({mode})" if cl > 0 else "disabled"
    print(_box_row("Chunk length", chunk_s))
    print(_box_row("Files", str(len(inputs))))
    print(_box_row("Total audio", _fmt_duration(total_duration_s)))
    print(_box_row("Total size", _fmt_mb(total_bytes)))
    print(_box_row("Run stamp", stamp))
    print(_box_row("Output dir", output_dir))
    print(_box_bottom(width=BOX_W))
    print()
