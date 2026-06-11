"""Name detection — Case 4: inferred from the Agent subclass name (no id at all).

    class ConciergeAgent(DemoAgent): ...      # no id passed
    obs.attach(session, ctx)                  # no override, no worker agent_name

If you just subclass Agent and never pass `id`, LiveKit derives the label from the class
name: `ConciergeAgent` → `concierge_agent` (camelCase → snake_case). That label rides on
the agent_session span as lk.agent_label, so retina reconciles the call to it.

Behaviour is the same shape as example 03 (the SDK still can't see the agent at attach
time, so the lifecycle ping is "unknown" → reconciled to "concierge_agent" on hangup) —
the difference is *where the name comes from*: the class name, not an explicit id=.

Run:
    uv run python examples/04_name_from_class.py console
"""

from __future__ import annotations

from _demo_common import DemoAgent, build_session, make_observability, prewarm
from livekit.agents import AgentServer, JobContext, cli


class ConciergeAgent(DemoAgent):
    """No id → label is derived from this class name: 'concierge_agent'."""


obs = make_observability()
server = AgentServer()
server.setup_fnc = prewarm


@server.rtc_session()  # no agent_name
async def entrypoint(ctx: JobContext) -> None:
    session = build_session(ctx)
    obs.attach(session, ctx)  # no override, no agent_name → "unknown" on the ping
    # No id passed → the class name becomes the label retina reconciles to.
    await session.start(agent=ConciergeAgent(), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
