"""Centralised rate-limiter wired in :func:`src.main` and consumed by the
feature routers as a decorator.

Strategy:
  • Per-remote-IP counters held in-process (acceptable for a single-Cloud
    Run instance; if we scale horizontally we can swap to a Redis-backed
    storage with one config flip).
  • Module-level singleton — feature routers import ``limiter`` directly
    so the decorator stays declarative at the route level.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Default policy is "no limit" so existing endpoints aren't accidentally
# throttled when the limiter is mounted. Sensitive endpoints opt in
# explicitly via ``@limiter.limit("...")``.
limiter = Limiter(key_func=get_remote_address, default_limits=[])
