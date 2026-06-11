"""Redaction — opt out of exporting sensitive data.

Same agent as the others, but configured to withhold the system prompt, the model
identifiers, and the tool arguments/outputs. Everything else still flows: spans,
durations, token counts, the span tree, transcripts, and tool *names*. The flagged
fields are filtered client-side and never leave the process.

Run:
    uv run python examples/05_redaction.py console

Then open the call in retina (or the viewer) and confirm it's missing: lk.instructions,
gen_ai.request.model, the resource llm.model/llm.provider, and the function-tool
arguments/output — while the transcript, tokens, and tool name are still present.
"""

from __future__ import annotations

from _demo_common import DemoAgent, build_session, make_observability, prewarm
from livekit.agents import AgentServer, JobContext, cli

from voxeye import Redaction

obs = make_observability(
    redact=Redaction(prompts=True, model_names=True, tool_io=True)  # transcripts kept
)
server = AgentServer()
server.setup_fnc = prewarm


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    session = build_session(ctx)
    obs.attach(session, ctx, agent_id="redacted_agent")
    await session.start(agent=DemoAgent(id="redacted_agent"), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
