"""Opt-out redaction: keep spans flowing, but drop sensitive fields before export.

Two layers, neither touches LiveKit's span emission:
  - model-name resource attrs voxeye sets are simply not added (see _tracer).
  - sensitive attributes LiveKit sets on spans are filtered at the export boundary by
    RedactingSpanExporter — a thin wrapper that forwards redacted copies to the real
    OTLP exporter. Live spans are never mutated (ReadableSpan.attributes is read-only).
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

# group toggle -> span attribute keys LiveKit emits that carry that data
_GROUP_KEYS: dict[str, tuple[str, ...]] = {
    "model_names": ("gen_ai.request.model", "gen_ai.provider.name"),
    "prompts": ("lk.instructions", "lk.chat_ctx"),
    "transcripts": (
        "lk.user_input",
        "lk.user_transcript",
        "lk.response.text",
        "lk.input_text",
        "lk.tts.input_text",
    ),
    "tool_io": ("lk.function_tool.arguments", "lk.function_tool.output"),
}


@dataclass(frozen=True)
class Redaction:
    """What NOT to export. Defaults export everything; set a flag True to drop it.

    - model_names: stt/llm/tts/vad provider+model identifiers (resource attrs AND the
      gen_ai.* model attrs LiveKit sets on llm spans).
    - prompts: system prompt / instructions (and the redundant chat context).
    - transcripts: user transcripts and agent response text.
    - tool_io: function-tool arguments and outputs.
    - attributes: extra exact attribute keys to drop (escape hatch).
    """

    model_names: bool = False
    prompts: bool = False
    transcripts: bool = False
    tool_io: bool = False
    attributes: tuple[str, ...] = ()

    def span_drop_keys(self) -> frozenset[str]:
        keys: set[str] = set(self.attributes)
        for group, group_keys in _GROUP_KEYS.items():
            if getattr(self, group):
                keys.update(group_keys)
        return frozenset(keys)


class RedactingSpanExporter(SpanExporter):
    """Forwards spans to `inner`, dropping `drop_keys` from each span's attributes."""

    def __init__(self, inner: SpanExporter, drop_keys: frozenset[str]) -> None:
        self._inner = inner
        self._drop = drop_keys

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        if not self._drop:
            return self._inner.export(spans)
        return self._inner.export([self._redact(s) for s in spans])

    def _redact(self, span: ReadableSpan) -> ReadableSpan:
        attrs = span.attributes or {}
        if not any(k in attrs for k in self._drop):
            return span
        clean = {k: v for k, v in attrs.items() if k not in self._drop}
        scrubbed = copy.copy(span)  # shallow copy; only the attributes view changes
        scrubbed._attributes = clean
        return scrubbed

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return self._inner.force_flush(timeout_millis)

    def shutdown(self) -> None:
        self._inner.shutdown()
