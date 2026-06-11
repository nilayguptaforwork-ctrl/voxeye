"""Shared bits for the demo agents.

Each demo file differs only in how the agent's name is resolved; everything else
(session, model stack, a sample tool) lives here so the examples stay focused.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession, JobContext, JobProcess, RunContext
from livekit.agents.llm import function_tool
from livekit.plugins import cartesia, deepgram, google, silero

from voxeye import Observability, Redaction

# Load examples/.env regardless of the working directory you launch from.
load_dotenv(Path(__file__).with_name(".env"))


def make_observability(redact: Redaction | None = None) -> Observability:
    """Build the SDK from env. VOXEYE_ENDPOINT defaults to local retina."""
    return Observability(
        api_key=os.environ["VOXEYE_API_KEY"],
        endpoint=os.environ.get("VOXEYE_ENDPOINT", "http://localhost:8000"),
        debug=True,  # logs attach failures so the demo is easy to troubleshoot
        redact=redact or Redaction(),
    )


class DemoAgent(Agent):
    """A minimal voice agent with one tool (so you get function_tool spans).

    `id` becomes the agent's label — the authoritative name retina reconciles the
    call to once the agent_session span arrives.
    """

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(
            instructions=(
                "You are a friendly voice demo assistant. Keep replies to one short sentence."
            ),
            id=id,
        )

    async def on_enter(self) -> None:
        self.session.generate_reply(instructions="Briefly greet the user and say what you do.")

    @function_tool
    async def get_office_hours(self, context: RunContext) -> str:
        """Called when the user asks when the office is open."""
        return "The office is open weekdays from 9am to 5pm."


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


def build_session(ctx: JobContext) -> AgentSession:
    # Gemini LLM + Deepgram STT + Cartesia TTS + Silero VAD — all key-based.
    return AgentSession(
        stt=deepgram.STT(),
        llm=google.LLM(model="gemini-2.0-flash"),
        tts=cartesia.TTS(),
        vad=ctx.proc.userdata["vad"],
    )
