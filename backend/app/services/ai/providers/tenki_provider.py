"""Run an agent inside a Tenki.cloud sandbox microVM.

Why this shape: Tenki sells disposable Linux VMs, CI runners and PR review — it
does not host model inference. So "the agent runs on Tenki" means the agent
*process* is executed in a Tenki sandbox, isolated from the API server, while
inference is still served by a model provider from inside that sandbox.

What that buys you: the agent runs in a disposable VM with no network path to
the application database, so a prompt-injection or a bad agent script cannot
reach user records. The model key is passed as sandbox process environment and
never reaches the browser.

Requires TENKI_API_KEY (workspace key, `tk_...`) and ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import json

from app.core.config import settings
from app.services.ai.prompts import PLANNING_AGENTS
from app.services.ai.providers.base import AgentError, ProviderOutput
from app.services.ai.schemas import AGENT_JSON_SCHEMA

WORKDIR = "/tmp/bearly-agent"

# The script executed inside the sandbox. It reads its inputs from files, calls
# the model, and writes one JSON object to stdout. It never sees the database.
AGENT_RUNNER = '''
import json, os, sys

import anthropic

with open("/tmp/bearly-agent/job.json") as fh:
    job = json.load(fh)

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

response = client.messages.create(
    model=job["model"],
    max_tokens=job["max_tokens"],
    system=[{"type": "text", "text": job["system"], "cache_control": {"type": "ephemeral"}}],
    messages=[{"role": "user", "content": job["user"]}],
    output_config={
        "effort": job["effort"],
        "format": {"type": "json_schema", "schema": job["schema"]},
    },
    thinking={"type": "adaptive"},
)

if getattr(response, "stop_reason", None) == "refusal":
    print(json.dumps({"error": "refusal"}))
    sys.exit(0)

text = next((b.text for b in response.content if b.type == "text"), "")
print(json.dumps({
    "payload": json.loads(text),
    "input_tokens": response.usage.input_tokens,
    "output_tokens": response.usage.output_tokens,
}))
'''


class TenkiProvider:
    name = "tenki"

    def __init__(self) -> None:
        try:
            from tenki import Sandbox  # noqa: F401
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise AgentError(
                "The `tenki` package is not installed. Run: pip install tenki"
            ) from exc
        if not settings.tenki_api_key:
            raise AgentError("TENKI_API_KEY is not set.")
        if not settings.anthropic_api_key:
            raise AgentError(
                "ANTHROPIC_API_KEY is not set. Tenki hosts the agent process; it does not "
                "provide model inference, so a model key is still required."
            )

    def run(self, agent: str, system_prompt: str, context: dict, model: str) -> ProviderOutput:
        from tenki import Sandbox

        from app.services.ai.prompts import user_message

        job = {
            "model": model,
            "max_tokens": settings.ai_max_output_tokens,
            "effort": "high" if agent in PLANNING_AGENTS else "low",
            "system": system_prompt,
            "user": user_message(agent, context),
            "schema": AGENT_JSON_SCHEMA,
        }

        try:
            with Sandbox.create(name=f"bearly-{agent}") as sb:
                sb.fs.mkdir(WORKDIR)
                sb.fs.write_text(f"{WORKDIR}/runner.py", AGENT_RUNNER)
                sb.fs.write_text(f"{WORKDIR}/job.json", json.dumps(job))

                install = sb.exec(
                    "bash", "-lc", "pip install --quiet anthropic", timeout=120
                )
                if install.exit_code != 0:
                    raise AgentError("Sandbox could not install the model SDK.")

                result = sb.exec(
                    "python3",
                    f"{WORKDIR}/runner.py",
                    env={"ANTHROPIC_API_KEY": settings.anthropic_api_key},
                    timeout=settings.tenki_sandbox_timeout,
                )
        except AgentError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise AgentError(f"Tenki sandbox failed: {type(exc).__name__}") from exc

        if result.exit_code != 0:
            # stderr may echo the prompt; keep it out of application logs.
            raise AgentError(f"Agent exited with status {result.exit_code}.")

        try:
            out = json.loads(result.stdout_text.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError) as exc:
            raise AgentError("Agent produced no parseable output.") from exc

        if "error" in out:
            raise AgentError("The model declined to answer this request.")

        return ProviderOutput(
            payload=out["payload"],
            model=model,
            input_tokens=out.get("input_tokens", 0),
            output_tokens=out.get("output_tokens", 0),
        )
