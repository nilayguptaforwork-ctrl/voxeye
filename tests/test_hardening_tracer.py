"""Hardening tests for voxeye tracer + lifecycle edges.

Adds coverage that the existing suite (test_tracer / test_lifecycle / test_resolve)
does not exercise:
  * _introspect: _opts present but no model attr, model is None, model getter raises,
    short module path (< 2 parts).
  * attach(): endpoint trailing-slash trimming reaches the OTLP exporter URL.
  * attach(): metadata is threaded all the way through to the lifecycle ping payload.
  * attach(): a *second* attach() in the same process flushes+shuts down the prior
    SDK provider (pooled-worker reuse), driven through the real set_tracer_provider.
  * attach(): fail-open when ctx.job raises, and fail-open when send_ping runs with
    no running event loop (no-loop branch in _lifecycle.send_ping).
  * resolve_agent_id: empty-string agent_name -> "unknown"; ctx with no .job attr.
"""

from __future__ import annotations

import types

import pytest
from opentelemetry.sdk.trace import TracerProvider

from tests.conftest import fake_ctx, fake_session
from voxeye import Observability
from voxeye._lifecycle import send_ping
from voxeye._resolve import resolve_agent_id
from voxeye._tracer import _introspect


def _current_provider():
    from livekit.agents.telemetry.traces import tracer

    return tracer._tracer_provider


# --------------------------------------------------------------------------- #
# _introspect edge cases
# --------------------------------------------------------------------------- #
def test_introspect_opts_without_model_falls_back_to_model_attr():
    """_opts exists but has no `model`; component.model is used instead."""

    class _Opts:
        pass  # no .model

    class _Comp:
        _opts = _Opts()
        model = "fallback-model"

    _Comp.__module__ = "livekit.plugins.deepgram.stt"
    info = _introspect(_Comp())
    assert info == {"provider": "deepgram", "model": "fallback-model"}


def test_introspect_opts_model_none_is_unknown():
    """_opts.model is None -> stringified to 'unknown', not the literal 'None'."""

    class _Opts:
        model = None

    class _Comp:
        _opts = _Opts()

    _Comp.__module__ = "livekit.plugins.cartesia.tts"
    info = _introspect(_Comp())
    assert info == {"provider": "cartesia", "model": "unknown"}


def test_introspect_model_getter_raises_returns_none():
    """If reading _opts.model raises, the whole introspect is swallowed -> None."""

    class _Opts:
        @property
        def model(self):
            raise RuntimeError("boom reading model")

    class _Comp:
        _opts = _Opts()

    _Comp.__module__ = "livekit.plugins.openai.llm"
    assert _introspect(_Comp()) is None


def test_introspect_short_module_path_uses_last_part():
    """Module path with a single segment falls back to parts[-1] for provider."""

    class _Comp:
        pass

    _Comp.__module__ = "topmod"  # len(parts) == 1
    info = _introspect(_Comp())
    assert info == {"provider": "topmod", "model": "unknown"}


def test_introspect_no_opts_no_model_is_unknown():
    """No _opts and no model attribute at all -> model 'unknown'."""

    class _Comp:
        pass

    _Comp.__module__ = "livekit.plugins.silero.vad"
    assert _introspect(_Comp()) == {"provider": "silero", "model": "unknown"}


# --------------------------------------------------------------------------- #
# attach(): endpoint trimming + metadata threading
# --------------------------------------------------------------------------- #
def test_attach_trims_trailing_slash_in_exporter_endpoint():
    """A trailing slash on the configured endpoint must not produce a // in the
    OTLP traces URL."""
    obs = Observability(api_key="sk_test", endpoint="http://example.test:8000///")
    obs.attach(fake_session(), fake_ctx(job_id="job_slash"))

    provider = _current_provider()
    assert isinstance(provider, TracerProvider)
    # Dig the exporter out of the registered span processor and check its endpoint.
    sp = provider._active_span_processor._span_processors[-1]
    exporter = sp.span_exporter
    assert exporter._endpoint == "http://example.test:8000/v1/traces"


def test_attach_threads_metadata_into_ping(monkeypatch):
    """metadata passed to attach() reaches send_ping unchanged, alongside resolved ids."""
    captured: dict = {}

    def _fake_send_ping(**kwargs):
        captured.update(kwargs)

    # Patch the symbol that _tracer imported.
    monkeypatch.setattr("voxeye._tracer.send_ping", _fake_send_ping)

    obs = Observability(api_key="sk_meta", endpoint="http://host:8000/")
    ctx = fake_ctx(job_id="job_meta", agent_name="agentX")
    obs.attach(fake_session(), ctx, metadata={"env": "prod", "region": "us"})

    assert captured["call_id"] == "job_meta"
    assert captured["agent_id"] == "agentX"
    assert captured["metadata"] == {"env": "prod", "region": "us"}
    # endpoint forwarded to ping should be trimmed too.
    assert captured["endpoint"] == "http://host:8000"
    assert captured["api_key"] == "sk_meta"


def test_attach_none_metadata_becomes_empty_dict(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr("voxeye._tracer.send_ping", lambda **kw: captured.update(kw))

    Observability(api_key="sk").attach(fake_session(), fake_ctx(), metadata=None)
    assert captured["metadata"] == {}


# --------------------------------------------------------------------------- #
# attach(): pooled-worker reuse — a SECOND attach shuts the first provider down
# --------------------------------------------------------------------------- #
def test_second_attach_shuts_down_prior_provider(monkeypatch):
    """Two attach() calls in one process: the provider installed by the first call is
    flushed + shut down when the second installs its own."""
    # Don't actually fire pings during this test.
    monkeypatch.setattr("voxeye._tracer.send_ping", lambda **kw: None)

    obs = Observability(api_key="sk")
    obs.attach(fake_session(), fake_ctx(job_id="first"))
    first = _current_provider()
    assert isinstance(first, TracerProvider)

    seen = {"flush": 0, "shutdown": 0}
    orig_flush = first.force_flush
    orig_shutdown = first.shutdown

    def _flush(timeout_millis: int | None = None):
        seen["flush"] += 1
        return orig_flush(timeout_millis=timeout_millis)

    def _shutdown():
        seen["shutdown"] += 1
        return orig_shutdown()

    first.force_flush = _flush  # type: ignore[method-assign]
    first.shutdown = _shutdown  # type: ignore[method-assign]

    obs.attach(fake_session(), fake_ctx(job_id="second"))

    assert seen == {"flush": 1, "shutdown": 1}
    assert _current_provider() is not first


# --------------------------------------------------------------------------- #
# attach(): fail-open paths
# --------------------------------------------------------------------------- #
def test_attach_fail_open_when_job_raises():
    """ctx.job raising must never propagate out of attach()."""

    class _BadCtx:
        @property
        def job(self):
            raise RuntimeError("no job here")

    # Returns None, does not raise.
    assert Observability(api_key="sk").attach(fake_session(), _BadCtx()) is None


def test_attach_fail_open_when_send_ping_has_no_running_loop(monkeypatch):
    """attach() runs send_ping synchronously; with no running event loop the ping is a
    no-op and attach() still installs the provider and shutdown callback."""
    # Ensure the real send_ping is used (no patching) — there is no running loop here
    # because this is a plain sync test, so send_ping hits the RuntimeError branch.
    import asyncio

    with pytest.raises(RuntimeError):
        asyncio.get_running_loop()  # confirm: no loop in this sync test

    obs = Observability(api_key="sk", endpoint="http://host:8000")
    ctx = fake_ctx(job_id="noloop", agent_name="a")
    obs.attach(fake_session(), ctx)  # must not raise despite no loop

    assert isinstance(_current_provider(), TracerProvider)
    assert len(ctx.shutdown_callbacks) == 1


def test_send_ping_no_loop_is_noop(caplog):
    """Directly exercise the no-loop branch of send_ping: returns without scheduling."""
    import logging

    with caplog.at_level(logging.DEBUG, logger="voxeye"):
        # No exception, no return value.
        result = send_ping(
            endpoint="http://host",
            api_key="sk",
            call_id="c",
            agent_id="a",
            metadata={},
        )
    assert result is None


# --------------------------------------------------------------------------- #
# resolve_agent_id edges
# --------------------------------------------------------------------------- #
def test_resolve_empty_agent_name_is_unknown():
    ctx = types.SimpleNamespace(job=types.SimpleNamespace(agent_name=""))
    assert resolve_agent_id(None, ctx) == "unknown"


def test_resolve_ctx_without_job_attr_is_unknown():
    ctx = types.SimpleNamespace()  # no .job at all
    assert resolve_agent_id(None, ctx) == "unknown"


def test_resolve_empty_override_falls_through_to_job_name():
    """An empty override string is falsy, so the job agent_name should win."""
    ctx = types.SimpleNamespace(job=types.SimpleNamespace(agent_name="from_job"))
    assert resolve_agent_id("", ctx) == "from_job"
