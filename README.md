# voxeye

OpenTelemetry observability for [LiveKit Agents](https://github.com/livekit/agents). One
`pip install`, three lines of code, and every transcript, tool call, system prompt, span, and
per-component model identifier flows to a self-hosted [retina](../retina) ingest service.

No event listeners, no content buffering, no proprietary SDK lock-in — just OTel done right for
voice agents.

## Install

```bash
pip install voxeye
```

## Use

```python
from voxeye import Observability
from livekit.agents import AgentSession, JobContext

obs = Observability(api_key="sk_...", endpoint="https://your-retina-host")  # module-level, pure

async def entrypoint(ctx: JobContext):
    session = AgentSession(stt=..., llm=..., tts=...)
    obs.attach(session, ctx)                              # sync, fail-open
    await session.start(agent=MyAgent(), room=ctx.room)   # your existing line
```

That's it. `attach()`:

1. **Resets any prior `TracerProvider`** — LiveKit worker subprocesses are pooled and reused, so
   a provider from a previous job can leak into the next one.
2. **Resolves `call_id = ctx.job.id`** (`room.sid` isn't available until `ctx.connect()`).
3. **Resolves `agent_id`** via `agent_id=` override → `ctx.job.agent_name` → `"unknown"` (the real
   label is reconciled server-side from the `agent_session` span).
4. **Introspects** `session.stt/.llm/.tts/.vad` for `{component}.provider` / `.model`, set as
   resource attributes on every span — closing gaps LiveKit's plugin instrumentation leaves.
5. **Installs an OTLP exporter** (gzip, bearer auth) and an async shutdown flush.
6. **Fires a lifecycle ping** to `/v1/calls` for instant call existence + crash detection.

Every step is wrapped fail-open: `attach()` never raises into your entrypoint.

## Redaction (opt out of exporting sensitive data)

By default everything is exported. Pass a `Redaction` to stop specific data from ever
leaving the process — it's filtered client-side (sensitive resource attrs aren't set, and
span attributes are dropped at the export boundary; live spans are never mutated):

```python
from voxeye import Observability, Redaction

obs = Observability(
    api_key="sk_...",
    redact=Redaction(
        prompts=True,       # drop the system prompt / instructions
        model_names=True,   # drop stt/llm/tts/vad provider+model (resource AND gen_ai.* attrs)
        transcripts=True,   # drop user transcripts + agent response text
        tool_io=True,       # drop function-tool arguments + outputs
        attributes=("my.custom.attr",),  # escape hatch: extra exact keys to drop
    ),
)
```

Spans, durations, token counts, span tree, and tool *names* still flow — only the fields
you flag are withheld. Each flag defaults to `False` (export).

## Notes

- `endpoint` defaults to `http://localhost:8000` (local retina). Point it at your host in prod.
- Call `attach()` **once** per entrypoint. Calling it twice replaces the provider mid-call.
- Requires `livekit-agents >= 1.0`.

## Develop

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src tests && uv run mypy src
```

## Build & publish

`voxeye` is **published on PyPI** (`pip install voxeye`). Releases are automated via GitHub
Actions **trusted publishing** (OIDC, no API tokens) in `.github/workflows/publish.yml`,
which runs on a published GitHub Release — the PyPI trusted publisher and `pypi` environment
are already configured. To cut a new version (bump `pyproject.toml` first — the version comes
from there, not the tag) and the full runbook, see [`PUBLISHING.md`](./PUBLISHING.md). To
build/validate locally:

```bash
uv build                       # → dist/voxeye-<version>-py3-none-any.whl + .tar.gz
uvx twine check dist/*         # validate metadata + README rendering
pip install dist/voxeye-*.whl  # try it in a clean env
```
