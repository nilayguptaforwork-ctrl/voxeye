from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from livekit.agents import AgentSession, JobContext
from livekit.agents.telemetry import set_tracer_provider
from livekit.agents.telemetry.traces import tracer as _lk_tracer
from opentelemetry.exporter.otlp.proto.http import Compression
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter

from voxeye._lifecycle import send_ping
from voxeye._redaction import RedactingSpanExporter, Redaction
from voxeye._resolve import resolve_agent_id
from voxeye.constants import DEFAULT_ENDPOINT

_log = logging.getLogger("voxeye")


def _introspect(component: object | None) -> dict[str, str] | None:
    """Best-effort STT/LLM/TTS/VAD provider+model identification.

    Plugins encode the provider in their module path; the model is usually in
    `_opts.model`. Both are wrapped in try/except — any failure yields None, so this
    never breaks attach().
    """
    if component is None:
        return None
    try:
        parts = type(component).__module__.split(".")
        provider = parts[-2] if len(parts) >= 2 else parts[-1]
        model: str | None = None
        if hasattr(component, "_opts") and hasattr(component._opts, "model"):
            model = component._opts.model
        elif hasattr(component, "model"):
            model = component.model
        return {"provider": provider, "model": str(model) if model else "unknown"}
    except Exception:
        return None


@dataclass(frozen=True)
class Observability:
    """Configure OTel tracing + a lifecycle ping for a LiveKit Agents job.

    Usage::

        obs = Observability(api_key="sk_...")          # module-level, pure

        async def entrypoint(ctx: JobContext):
            session = AgentSession(stt=..., llm=..., tts=...)
            obs.attach(session, ctx)                    # sync, fail-open
            await session.start(agent=MyAgent(), room=ctx.room)
    """

    api_key: str
    endpoint: str = DEFAULT_ENDPOINT
    debug: bool = False
    redact: Redaction = field(default_factory=Redaction)

    def attach(
        self,
        session: AgentSession[Any],
        ctx: JobContext,
        *,
        agent_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        try:
            endpoint = self.endpoint.rstrip("/")

            # 1. Reset any prior provider — worker subprocesses are pooled and reused,
            #    so a TracerProvider from a previous job can persist in this process.
            #    Only a real SDK TracerProvider has flush/shutdown (the default is a
            #    ProxyTracerProvider); mirror LiveKit's own isinstance gate.
            prior = getattr(_lk_tracer, "_tracer_provider", None)
            if isinstance(prior, TracerProvider):
                try:
                    prior.force_flush(timeout_millis=2000)
                    prior.shutdown()
                except Exception as exc:
                    _log.debug("prior provider shutdown failed: %s", exc)

            # 2. Resolve identifiers. call_id = job.id (room.sid isn't available until
            #    ctx.connect(), which session.start() triggers — too late for attach).
            call_id = ctx.job.id
            resolved_agent_id = resolve_agent_id(agent_id, ctx)

            # 3. Build the Resource (inherited by every span).
            resource_attrs: dict[str, str] = {
                SERVICE_NAME: resolved_agent_id,
                "agent.id": resolved_agent_id,
                "call.id": call_id,
            }
            if not self.redact.model_names:  # opt-out: don't even introspect models
                for name in ("stt", "llm", "tts", "vad"):
                    info = _introspect(getattr(session, name, None))
                    if info:
                        resource_attrs[f"{name}.provider"] = info["provider"]
                        resource_attrs[f"{name}.model"] = info["model"]

            # Filter sensitive span attributes at the export boundary (opt-out).
            exporter: SpanExporter = OTLPSpanExporter(
                endpoint=f"{endpoint}/v1/traces",
                headers={"Authorization": f"Bearer {self.api_key}"},
                compression=Compression.Gzip,
            )
            drop_keys = self.redact.span_drop_keys()
            if drop_keys:
                exporter = RedactingSpanExporter(exporter, drop_keys)

            provider = TracerProvider(resource=Resource.create(resource_attrs))
            provider.add_span_processor(BatchSpanProcessor(exporter))
            set_tracer_provider(provider)

            # 4. Flush spans on shutdown — runs before LiveKit's own telemetry shutdown.
            async def _flush_on_shutdown(_reason: str) -> None:
                try:
                    provider.force_flush(timeout_millis=5000)
                    provider.shutdown()
                except Exception as exc:
                    _log.debug("provider flush/shutdown failed: %s", exc)

            ctx.add_shutdown_callback(_flush_on_shutdown)

            # 5. Lifecycle ping (fire-and-forget, fail-open).
            send_ping(
                endpoint=endpoint,
                api_key=self.api_key,
                call_id=call_id,
                agent_id=resolved_agent_id,
                metadata=dict(metadata) if metadata else {},
            )
        except Exception as exc:  # never break the user's hot path
            _log.warning("voxeye attach failed: %s", exc, exc_info=self.debug)
