"""End-to-end smoke: voxeye SDK → retina, over real OTLP (gzip + protobuf + bearer).

Emits the spans a LiveKit AgentSession would (without needing a LiveKit server), then
queries retina to prove the full pipeline — lifecycle ping, OTLP export, agent_session
reconciliation, chat_ctx stripping, query — works against the live service.

Usage:
    # 1. start retina (see ../retina/README.md) and seed an api key
    # 2. run from the voxeye/ dir:
    uv run python examples/end_to_end_smoke.py <api_key> [endpoint]
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import types

import requests
from livekit.agents.telemetry.traces import tracer

from voxeye import Observability


def _fake_ctx(job_id: str, agent_name: str | None = None) -> types.SimpleNamespace:
    ctx = types.SimpleNamespace(job=types.SimpleNamespace(id=job_id, agent_name=agent_name))
    ctx.shutdown_callbacks = []  # type: ignore[attr-defined]
    ctx.add_shutdown_callback = ctx.shutdown_callbacks.append  # type: ignore[attr-defined]
    return ctx


def _fake_session() -> types.SimpleNamespace:
    return types.SimpleNamespace(stt=None, llm=None, tts=None, vad=None)


def main() -> int:
    api_key = sys.argv[1]
    endpoint = (sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000").rstrip("/")
    call_id = f"e2e_{int(time.time())}"

    obs = Observability(api_key=api_key, endpoint=endpoint)
    ctx = _fake_ctx(call_id, agent_name="unknown")  # real label comes from the span
    obs.attach(_fake_session(), ctx)  # installs provider + fires lifecycle ping

    # Emit spans exactly as LiveKit Agents would.
    with tracer.start_as_current_span("agent_session") as session_span:
        session_span.set_attribute("lk.agent_label", "smoke_agent")
        session_span.set_attribute("lk.instructions", "you are a smoke test agent")
        session_span.set_attribute("lk.function_tools", ["noop"])
        session_span.set_attribute("lk.chat_ctx", "x" * 4000)  # should be stripped at ingest
        with tracer.start_as_current_span("llm_node") as llm_span:
            llm_span.set_attribute("gen_ai.request.model", "gpt-4o")
            llm_span.set_attribute("gen_ai.usage.input_tokens", 42)
            llm_span.set_attribute("gen_ai.usage.output_tokens", 7)
            llm_span.set_attribute("lk.response.text", "hi from the smoke test")

    # Fire the registered shutdown flush (force_flush + shutdown), as LiveKit would.
    for cb in ctx.shutdown_callbacks:
        asyncio.run(cb("smoke"))

    time.sleep(1.0)  # let the lifecycle ping land
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(f"{endpoint}/v1/calls/{call_id}", headers=headers, timeout=10)
    print(f"GET /v1/calls/{call_id} -> {resp.status_code}")
    if resp.status_code != 200:
        print(resp.text)
        return 1

    body = resp.json()
    checks = {
        "agent reconciled to span label": body["agent_id"] == "smoke_agent",
        "call completed": body["status"] == "completed",
        "two spans persisted": body["totals"]["spans"] == 2,
        "tokens aggregated": body["totals"]["llm_tokens"] == {"input": 42, "output": 7},
        "definition captured": body["agent_definition"]
        == {"instructions": "you are a smoke test agent", "tools": ["noop"]},
        "chat_ctx stripped": all("lk.chat_ctx" not in s["attributes"] for s in body["spans"]),
    }
    print(json.dumps(checks, indent=2))
    ok = all(checks.values())
    print("\nRESULT:", "PASS ✅" if ok else "FAIL ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
