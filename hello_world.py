"""Phase 1 — hello-world scenario.

The docs example shape: a scenario that asks the agent how many times a
given letter appears in a given word, then rewards full marks for an
exact-integer match. The point is to put one full round-trip through hud
(prompt → agent response → submit → evaluate → reward) so the next phase
can build on the same skeleton.
"""

from __future__ import annotations

import asyncio

import hud
from hud.agents import create_agent

MODEL = "deepseek-v3.1-terminus"

env = hud.Environment(name="hello-world")


@env.scenario(description="Count letter occurrences in a word.")
async def count_letters(word: str = "strawberry", letter: str = "r"):
    """Two-yield scenario: prompt, then reward.

    Step B (after agent runs) needs the submitted answer; the platform
    routes it through ``env.submit`` and surfaces it on the eval context.
    The scenario function reads it back when it resumes for the reward
    half — that's why this is shaped as an async generator.
    """
    yield (
        f"How many times does the letter {letter!r} appear in the word "
        f"{word!r}? Reply with just the integer, nothing else."
    )

    ctx = hud.EvalContext.current()
    answer = (ctx.answer or "").strip()
    truth = word.count(letter)
    try:
        guess = int(answer)
    except ValueError:
        yield 0.0
        return

    yield 1.0 if guess == truth else 0.0


async def main() -> None:
    agent = create_agent(MODEL)
    task = count_letters.task(word="strawberry", letter="r")
    result = await agent.run(task)
    print("trace:", getattr(result, "trace_url", "(no trace URL)"))
    print("reward:", getattr(result, "reward", "(no reward field)"))
    print("answer:", getattr(result, "answer", "(no answer)"))


if __name__ == "__main__":
    asyncio.run(main())
