"""Phase 2 — hud Environment + classifier scenarios.

One scenario per PRD case. Each scenario sends a "Today is YYYY-MM-DD." +
user-input prompt to the agent, gets its JSON response, and scores it via
the compositional reward in ``reward.py``.

The agent is constructed via ``hud.agents.create_agent("deepseek-v4-flash")``
so traffic is routed through ``inference.hud.ai`` and traces land in the hud
UI.
"""

from __future__ import annotations

import hud
from openai import OpenAI

from cases import CASES, Case
from prompts.classifier import INSTRUCTIONS
from reward import compute_reward
from hud.settings import settings

env = hud.Environment(name="oak-classifier", instructions=INSTRUCTIONS)


def build_user_prompt(case: Case) -> str:
    """The exact preamble shape used by the live capture pipeline."""
    return f"Today is {case.today}.\n\n{case.raw_input}"


def _judge_client() -> OpenAI:
    """OpenAI client pointed at the hud gateway — used by the LLM-judge for titles."""
    return OpenAI(
        base_url=f"{settings.hud_gateway_url}/v1",
        api_key=settings.api_key,
    )


def _register_case(case: Case) -> None:
    """Register one scenario per case, keyed by ``case.case_id``."""

    @env.scenario(name=case.case_id.lower(), description=case.notes)
    async def _scenario():
        # First yield — what we hand the agent. The system prompt comes
        # from ``env.instructions``; only the user-turn lives in the yield.
        yield build_user_prompt(case)

        # Second yield — score the answer.
        ctx = hud.EvalContext.current()
        raw_answer = ctx.answer or ""
        breakdown = compute_reward(raw_answer, case, _judge_client())
        # Stash the per-case breakdown on the eval context so the trace
        # UI can show it. Falls back gracefully when not supported.
        try:
            ctx.metadata["breakdown"] = breakdown.__dict__  # type: ignore[index]
        except Exception:
            pass
        yield breakdown.total


for _c in CASES:
    _register_case(_c)
