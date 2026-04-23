"""Colorama-tinted console helpers for lethe.

Human-facing output. Call set_quiet(True) under --agentic
to silence everything here; the agentic JSON emitter
owns stdout in that mode.
"""
from colorama import Fore, Style, init as _colorama_init


_colorama_init()
_quiet = False


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
