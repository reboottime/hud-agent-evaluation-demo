"""Phase 2 — run all five classifier cases and print a summary.

Usage:
    uv run python run.py          # all five cases
    uv run python run.py E1 E5    # subset by case id
"""

from __future__ import annotations

import asyncio
import sys

from hud.agents import create_agent

from cases import CASES, case_by_id
from scenarios import env  # noqa: F401  — importing registers scenarios

MODEL = "deepseek-v3.1-terminus"


async def run_one(case_id: str) -> tuple[str, float, str | None]:
    """Run one case end-to-end; return (case_id, reward, trace_url)."""
    case = case_by_id(case_id)
    agent = create_agent(MODEL)
    handle = env.get_tool(f"oak-classifier:{case.case_id.lower()}")  # discovery hook
    # The platform-friendly path is to ask the env to build the task
    # for the scenario name; the lookup above is just a sanity check.
    task = env.get_tasks().get(case.case_id.lower()) if hasattr(env, "get_tasks") else None
    if task is None:
        # Fall back to going through the registered scenario handle.
        scenario_fn = getattr(env, "scenarios", {}).get(case.case_id.lower())
        if scenario_fn is None:
            raise RuntimeError(
                f"scenario {case.case_id!r} not registered — "
                "double-check scenarios.py imported correctly"
            )
        task = scenario_fn.task()
    result = await agent.run(task)
    return case.case_id, getattr(result, "reward", 0.0), getattr(result, "trace_url", None)


async def main() -> None:
    case_ids = sys.argv[1:] or [c.case_id for c in CASES]
    rows: list[tuple[str, float, str | None]] = []
    for cid in case_ids:
        try:
            rows.append(await run_one(cid))
        except Exception as exc:  # noqa: BLE001
            print(f"[{cid}] ERROR: {type(exc).__name__}: {exc}")
            rows.append((cid, 0.0, None))

    print()
    print("=" * 56)
    print(f"{'case':<6} {'reward':>7}  trace")
    print("-" * 56)
    for cid, reward, trace in rows:
        print(f"{cid:<6} {reward:>7.3f}  {trace or '-'}")
    print("-" * 56)
    if rows:
        avg = sum(r for _, r, _ in rows) / len(rows)
        print(f"{'avg':<6} {avg:>7.3f}")


if __name__ == "__main__":
    asyncio.run(main())
