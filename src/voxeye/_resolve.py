from __future__ import annotations

from typing import Any


def resolve_agent_id(override: str | None, ctx: Any) -> str:
    """Resolve agent_id via fallback chain: override → ctx.job.agent_name → "unknown".

    The agent instance isn't available at attach() time (it's set inside
    session.start(agent=...)), so the real label is reconciled server-side from the
    agent_session span. This is the best-effort value for the lifecycle ping.
    """
    if override:
        return override
    job_name = getattr(getattr(ctx, "job", None), "agent_name", None)
    if job_name:
        return str(job_name)
    return "unknown"
