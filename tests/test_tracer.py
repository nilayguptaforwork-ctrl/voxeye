from __future__ import annotations

from opentelemetry.sdk.resources import SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider

from tests.conftest import fake_ctx, fake_session
from voxeye import Observability
from voxeye._tracer import _introspect


def _current_provider():
    from livekit.agents.telemetry.traces import tracer

    return tracer._tracer_provider


def test_attach_installs_provider_with_resource_attrs():
    obs = Observability(api_key="sk_test", endpoint="http://localhost:9999/")
    ctx = fake_ctx(job_id="job_abc", agent_name="my_agent")
    obs.attach(fake_session(), ctx)

    provider = _current_provider()
    assert isinstance(provider, TracerProvider)
    attrs = provider.resource.attributes
    assert attrs["call.id"] == "job_abc"
    assert attrs["agent.id"] == "my_agent"
    assert attrs[SERVICE_NAME] == "my_agent"
    # async shutdown flush registered
    assert len(ctx.shutdown_callbacks) == 1


def test_attach_introspects_components_into_resource():
    class _Opts:
        model = "gpt-4o"

    class _FakeLLM:
        _opts = _Opts()

    _FakeLLM.__module__ = "livekit.plugins.openai.llm"

    obs = Observability(api_key="sk_test")
    obs.attach(fake_session(llm=_FakeLLM()), fake_ctx())

    attrs = _current_provider().resource.attributes
    assert attrs["llm.provider"] == "openai"
    assert attrs["llm.model"] == "gpt-4o"


def test_attach_resets_prior_provider_on_pooled_reuse():
    from livekit.agents.telemetry import set_tracer_provider

    prior = TracerProvider()
    seen = {"flush": 0, "shutdown": 0}

    def _flush(timeout_millis: int | None = None) -> bool:
        seen["flush"] += 1
        return True

    def _shutdown() -> None:
        seen["shutdown"] += 1

    prior.force_flush = _flush  # type: ignore[method-assign]
    prior.shutdown = _shutdown  # type: ignore[method-assign]
    set_tracer_provider(prior)

    Observability(api_key="sk").attach(fake_session(), fake_ctx())

    assert seen == {"flush": 1, "shutdown": 1}
    assert _current_provider() is not prior


def test_attach_is_fail_open():
    class _BadCtx:
        @property
        def job(self):
            raise RuntimeError("boom")

    # Must not raise into the user's entrypoint.
    Observability(api_key="sk").attach(fake_session(), _BadCtx())


def test_introspect_handles_missing_and_present():
    assert _introspect(None) is None

    class _Plain:
        pass

    _Plain.__module__ = "livekit.plugins.silero.vad"
    info = _introspect(_Plain())
    assert info == {"provider": "silero", "model": "unknown"}
