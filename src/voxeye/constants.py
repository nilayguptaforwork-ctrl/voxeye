"""Tunable constants for the voxeye SDK.

Update ``DEFAULT_ENDPOINT`` to your retina host before publishing for production use.
Callers can always override per-instance: ``Observability(api_key=..., endpoint=...)``.
"""

from __future__ import annotations

# Base URL of the retina ingest service. The SDK appends ``/v1/traces`` and ``/v1/calls``.
DEFAULT_ENDPOINT = "http://localhost:8000"
