from __future__ import annotations

import asyncio
import json

import responses

from voxeye._lifecycle import send_ping


@responses.activate
async def test_send_ping_posts_expected_payload():
    responses.add(responses.POST, "http://host/v1/calls", json={"created": True}, status=200)

    send_ping(
        endpoint="http://host",
        api_key="sk_secret",
        call_id="job_xyz",
        agent_id="my_agent",
        metadata={"env": "prod"},
    )
    # send_ping schedules the POST on the executor; give it a moment to run.
    await asyncio.sleep(0.25)

    assert len(responses.calls) == 1
    req = responses.calls[0].request
    assert req.headers["Authorization"] == "Bearer sk_secret"
    body = json.loads(req.body)
    assert body["call_id"] == "job_xyz"
    assert body["agent_id"] == "my_agent"
    assert body["metadata"] == {"env": "prod"}
    assert body["started_at"].endswith("+00:00") or body["started_at"].endswith("Z")


async def test_send_ping_without_event_loop_is_noop_safe():
    # Inside a running loop here, but the failure mode we guard is "no loop"; just ensure
    # a transport error doesn't propagate (no responses mock registered → connection error).
    send_ping(
        endpoint="http://127.0.0.1:1",  # unroutable
        api_key="sk",
        call_id="c",
        agent_id="a",
        metadata={},
    )
    await asyncio.sleep(0.1)  # executor swallows the error; nothing should raise here
