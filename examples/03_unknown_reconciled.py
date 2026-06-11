"""Name detection — Case 3: "unknown" at attach, reconciled server-side.

    @server.rtc_session()           # no agent_name
    obs.attach(session, ctx)        # no override

With neither an override nor a worker agent_name, the SDK can't know the name at
attach time, so the lifecycle ping sends agent_id="unknown". When the agent_session
span arrives carrying lk.agent_label (the Agent's id, "reception_agent"), retina
reconciles the call to that name — span label wins.

This is the most common real-world case (most agents don't set an explicit name), and
it shows the reconciliation: the call briefly appears as "unknown", then becomes
"reception_agent" once spans land.

Run:
    uv run python examples/03_unknown_reconciled.py console
"""

from __future__ import annotations

from _demo_common import DemoAgent, build_session, make_observability, prewarm
from livekit.agents import AgentServer, JobContext, cli

obs = make_observability()
server = AgentServer()
server.setup_fnc = prewarm


@server.rtc_session()  # no agent_name
async def entrypoint(ctx: JobContext) -> None:
    session = build_session(ctx)
    obs.attach(session, ctx)  # no override, no agent_name → "unknown" on the ping
    # The agent's id is the authoritative label retina reconciles to.
    await session.start(agent=DemoAgent(id="reception_agent"), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
