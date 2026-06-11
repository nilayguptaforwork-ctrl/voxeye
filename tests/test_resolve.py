from __future__ import annotations

import types

import pytest

from voxeye._resolve import resolve_agent_id


@pytest.mark.parametrize(
    "override, agent_name, expected",
    [
        ("explicit_id", "from_job", "explicit_id"),  # override wins
        (None, "from_job", "from_job"),  # falls back to job.agent_name
        (None, None, "unknown"),  # final fallback
        (None, "", "unknown"),  # empty agent_name is not used
    ],
)
def test_resolve_agent_id(override, agent_name, expected):
    ctx = types.SimpleNamespace(job=types.SimpleNamespace(agent_name=agent_name))
    assert resolve_agent_id(override, ctx) == expected
