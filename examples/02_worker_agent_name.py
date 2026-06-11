"""Name detection — Case 2: resolved from the worker's agent_name.

    @server.rtc_session(agent_name="survey_agent")
    obs.attach(session, ctx)        # no override

With no override, the SDK falls back to ctx.job.agent_name — the name you registered
for explicit dispatch. (This is populated when LiveKit dispatches the job, so it's most
visible under `dev`/`start`; in `console` there's no dispatch, so it may be "unknown"
and then reconciled from the agent label — see example 03.)

Run:
    uv run python examples/02_worker_agent_name.py dev
"""

from __future__ import annotations

from _demo_common import DemoAgent, build_session, make_observability, prewarm
from livekit.agents import AgentServer, JobContext, cli

obs = make_observability()
server = AgentServer()
server.setup_fnc = prewarm


@server.rtc_session(agent_name="survey_agent")  # ← name comes from dispatch config
async def entrypoint(ctx: JobContext) -> None:
    session = build_session(ctx)
    obs.attach(session, ctx)  # no override → falls back to ctx.job.agent_name
    await session.start(agent=DemoAgent(id="survey_agent"), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
