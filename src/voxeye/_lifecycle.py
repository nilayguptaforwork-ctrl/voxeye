from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import requests  # transitive via opentelemetry-exporter-otlp-proto-http

_log = logging.getLogger("voxeye")


def send_ping(
    *,
    endpoint: str,
    api_key: str,
    call_id: str,
    agent_id: str,
    metadata: Mapping[str, Any],
) -> None:
    """Fire-and-forget POST to /v1/calls, off the event loop. Failures are non-fatal:
    spans still flow via OTLP, so the lifecycle ping is a 'nice to have'."""
    payload = {
        "call_id": call_id,
        "agent_id": agent_id,
        "started_at": datetime.now(UTC).isoformat(),
        "metadata": dict(metadata),
    }
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        _log.debug("no running event loop; skipping lifecycle ping")
        return
    loop.run_in_executor(None, _post, f"{endpoint}/v1/calls", api_key, payload)


def _post(url: str, api_key: str, payload: dict[str, Any]) -> None:
    try:
        requests.post(
            url,
            json=payload,
            timeout=5.0,
            headers={"Authorization": f"Bearer {api_key}"},
        )
    except Exception as exc:  # fail-open by design
        _log.debug("lifecycle ping failed: %s", exc)
