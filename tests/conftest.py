from __future__ import annotations

import types
from typing import Any


def fake_ctx(job_id: str = "job_1", agent_name: str | None = None) -> Any:
    """Duck-typed JobContext: .job.id, .job.agent_name, .add_shutdown_callback."""
    ctx = types.SimpleNamespace(
        job=types.SimpleNamespace(id=job_id, agent_name=agent_name),
        shutdown_callbacks=[],
    )
    ctx.add_shutdown_callback = ctx.shutdown_callbacks.append
    return ctx


def fake_session(stt=None, llm=None, tts=None, vad=None) -> Any:
    return types.SimpleNamespace(stt=stt, llm=llm, tts=tts, vad=vad)
