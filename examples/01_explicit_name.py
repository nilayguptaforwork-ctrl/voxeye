"""Name detection — Case 1: explicit override.

    obs.attach(session, ctx, agent_id="billing_assistant")

The SDK uses the override verbatim for the lifecycle ping — no guessing from worker
or agent config. Here the Agent's id matches, so the call shows up under
"billing_assistant" end to end.

Run:
    uv run python examples/01_explicit_name.py console      # local mic, no LiveKit server
    uv run python examples/01_explicit_name.py dev          # connect to LiveKit
"""

from __future__ import annotations

from _demo_common import DemoAgent, build_session, make_observability, prewarm
from livekit.agents import AgentServer, JobContext, cli

obs = make_observability()
server = AgentServer()
server.setup_fnc = prewarm


@server.rtc_session()  # no agent_name configured on the worker
async def entrypoint(ctx: JobContext) -> None:
    session = build_session(ctx)
    obs.attach(session, ctx, agent_id="billing_assistant")  # ← explicit override
    await session.start(agent=DemoAgent(id="billing_assistant"), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
