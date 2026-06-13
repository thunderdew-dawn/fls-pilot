"""Shared runtime configuration defaults."""

from __future__ import annotations

import contextlib
import socket

DEFAULT_SSE_HOST = "127.0.0.1"
DEFAULT_SSE_PORT = 8080
DEFAULT_CONTROL_CENTER_HOST = "127.0.0.1"
DEFAULT_CONTROL_CENTER_PORT = 8766


def can_bind_tcp(host: str, port: int) -> bool:
    """Return whether a local TCP server can bind to host/port."""
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, int(port)))
        except OSError:
            return False
        return True


def find_available_tcp_port(host: str, start_port: int, *, limit: int = 25) -> int:
    """Find the first bindable TCP port at or above start_port."""
    current = int(start_port)
    for _ in range(limit):
        if current == 0 or can_bind_tcp(host, current):
            return current
        current += 1
    raise OSError(f"Could not find a free TCP port near {host}:{start_port}")


def tcp_port_status(host: str, preferred_port: int, *, limit: int = 25) -> dict:
    """Return preferred/fallback port status for UI and CLI diagnostics."""
    preferred = int(preferred_port)
    available = can_bind_tcp(host, preferred)
    fallback = preferred if available else find_available_tcp_port(host, preferred + 1, limit=limit)
    return {
        "host": host,
        "preferred_port": preferred,
        "available": available,
        "selected_port": fallback,
        "fallback_port": None if available else fallback,
    }
