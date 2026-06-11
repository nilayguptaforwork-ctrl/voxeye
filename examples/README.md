# voxeye examples

Five tiny, runnable LiveKit voice agents — each one wired to voxeye and demonstrating a
different way the agent's **name** is resolved. Drop in a `.env`, point it at a running
[retina](../../retina), and make a call.

| File | Resolution case | What you'll see in retina |
|---|---|---|
| `01_explicit_name.py` | `attach(agent_id="billing_assistant")` | call under **billing_assistant** |
| `02_worker_agent_name.py` | `@rtc_session(agent_name="survey_agent")`, no override | call under **survey_agent** |
| `03_unknown_reconciled.py` | nothing set → `"unknown"`, reconciled from agent label (`id=`) | call flips **unknown → reception_agent** |
| `04_name_from_class.py` | subclass name, **no** id/override/worker name | call flips **unknown → concierge_agent** (label from the class name) |
| `05_redaction.py` | `Redaction(prompts, model_names, tool_io)` | call has **no** prompt / model names / tool I/O — transcript + tokens + tool names kept |

(`end_to_end_smoke.py` is a different beast — a no-mic, no-LiveKit script that posts a
synthetic trace straight to retina. Good for a zero-dependency sanity check.)

## How naming actually works (read this once)

- The SDK resolves a name for the **lifecycle ping** via: `agent_id=` override →
  `ctx.job.agent_name` → `"unknown"`.
- The **final** name on the call is the agent's **label** (`Agent.id`), promoted from the
  `agent_session` span server-side — *span label wins*. So for completed calls, the agent's
  `id` is authoritative; the ping value matters for the early/crash window and for case 3's
  visible reconciliation. The examples align `Agent(id=...)` with the intended name.

## Setup

```bash
# 1. retina running, then provision a tenant via its admin endpoint (see ../../retina/README.md)
cd ../../retina
export RETINA_ADMIN_TOKEN=$(openssl rand -hex 16)
uv run uvicorn retina.main:app --port 8000 &
uv run python -m retina.create_tenant "Demo"      # copy the api_key

# 2. install example deps
cd ../voxeye && uv sync --extra examples

# 3. configure
cp examples/.env.example examples/.env    # edit: VOXEYE_API_KEY, GOOGLE_API_KEY, DEEPGRAM_API_KEY, CARTESIA_API_KEY, (LiveKit for dev)
```

## Run

```bash
# console = local mic, no LiveKit account needed — easiest demo:
uv run python examples/01_explicit_name.py console
uv run python examples/03_unknown_reconciled.py console

# dev = connect to LiveKit (needed to see case 2's agent_name dispatch):
uv run python examples/02_worker_agent_name.py dev
```

Talk to it, then hang up. Watch the call land:

```bash
KEY=sk_...   # your seeded key
curl -s localhost:8000/v1/agents -H "Authorization: Bearer $KEY" | jq
curl -s localhost:8000/v1/calls  -H "Authorization: Bearer $KEY" | jq '.data[].call_id'
curl -s localhost:8000/v1/calls/<call_id> -H "Authorization: Bearer $KEY" | jq
```

Everything fails open: if `VOXEYE_ENDPOINT` is wrong or retina is down, the agent still
runs — you just won't see data. Run with `debug=True` (already set) to log attach issues.
If the agent runs somewhere retina can't reach (e.g. LiveKit Cloud), expose retina with a
tunnel (`ngrok http 8000`) and set `VOXEYE_ENDPOINT` to that URL.
"""
