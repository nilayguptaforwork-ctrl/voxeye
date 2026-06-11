from __future__ import annotations

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from tests.conftest import fake_ctx, fake_session
from voxeye import Observability, Redaction
from voxeye._redaction import RedactingSpanExporter


def test_span_drop_keys_maps_groups():
    keys = Redaction(prompts=True, model_names=True, attributes=("custom.key",)).span_drop_keys()
    assert "lk.instructions" in keys  # prompts
    assert "gen_ai.request.model" in keys  # model_names
    assert "custom.key" in keys  # escape hatch
    assert "lk.response.text" not in keys  # transcripts not selected
    assert Redaction().span_drop_keys() == frozenset()  # default exports everything


def _emit_and_collect(drop_keys, attrs):
    mem = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(RedactingSpanExporter(mem, drop_keys)))
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("llm_node") as span:
        for k, v in attrs.items():
            span.set_attribute(k, v)
    provider.force_flush()
    return dict(mem.get_finished_spans()[0].attributes)


def test_redacting_exporter_drops_only_configured_keys():
    out = _emit_and_collect(
        frozenset({"lk.instructions", "gen_ai.request.model"}),
        {
            "lk.instructions": "secret system prompt",
            "gen_ai.request.model": "gpt-4o",
            "lk.response.text": "hello there",  # kept
            "gen_ai.usage.input_tokens": 42,  # kept
        },
    )
    assert "lk.instructions" not in out
    assert "gen_ai.request.model" not in out
    assert out["lk.response.text"] == "hello there"
    assert out["gen_ai.usage.input_tokens"] == 42


def test_empty_redaction_passes_everything_through():
    out = _emit_and_collect(frozenset(), {"lk.instructions": "kept", "gen_ai.request.model": "m"})
    assert out["lk.instructions"] == "kept"
    assert out["gen_ai.request.model"] == "m"


def _resource_attrs():
    from livekit.agents.telemetry.traces import tracer

    return tracer._tracer_provider.resource.attributes


def test_redact_model_names_omits_resource_model_attrs():
    class _Opts:
        model = "gpt-4o"

    class _FakeLLM:
        _opts = _Opts()

    _FakeLLM.__module__ = "livekit.plugins.openai.llm"

    Observability(api_key="sk", redact=Redaction(model_names=True)).attach(
        fake_session(llm=_FakeLLM()), fake_ctx()
    )
    attrs = _resource_attrs()
    assert "llm.model" not in attrs and "llm.provider" not in attrs
    assert attrs["call.id"]  # non-sensitive resource attrs still present


def test_default_exports_model_resource_attrs():
    class _Opts:
        model = "gpt-4o"

    class _FakeLLM:
        _opts = _Opts()

    _FakeLLM.__module__ = "livekit.plugins.openai.llm"

    Observability(api_key="sk").attach(fake_session(llm=_FakeLLM()), fake_ctx())
    attrs = _resource_attrs()
    assert attrs["llm.provider"] == "openai" and attrs["llm.model"] == "gpt-4o"
