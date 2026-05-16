# hud-eval

A small Python side project to learn [hud.ai](https://hud.ai) hands-on. Uses
Oak's capture classifier as the eval target — five PRD cases sampled from
E1–E21 — but the goal is platform fluency, not regression coverage.

See the parent note for the full plan:
[Plan: evaluate Oak agents via hud.ai (learning sandbox)](https://oak.local/notes/01KRQ98Q2EDTN93VG3EHP3TCZW)
(note id `01KRQ98Q2EDTN93VG3EHP3TCZW` in the Oak DB).

## Setup

1. `uv sync`
2. Copy `.env.example` to `.env` and paste your `HUD_API_KEY` from the
   hud.ai dashboard. (Alternatively, `hud configure`.)
3. Smoke test: `uv run python smoke.py` — confirms gateway + key + model id.

## Layout

| File              | Phase | What it does                                              |
| ----------------- | ----- | --------------------------------------------------------- |
| `smoke.py`        | 0     | One-shot ping/pong through `inference.hud.ai`.            |
| `hello_world.py`  | 1     | Letter-count scenario (analog of the docs example).       |
| `prompts/classifier.py` | 2 | Trimmed port of Oak's capture-classifier prompt.        |
| `schemas.py`      | 2     | Pydantic mirror of `ClassifierOutputSchema`.              |
| `cases.py`        | 2     | The 5 PRD cases + expected outputs.                       |
| `reward.py`       | 2     | Compositional reward (structural / counts / fields / conf). |
| `scenarios.py`    | 2     | hud `Environment` + scenario registrations.               |
| `run.py`          | 2     | Entry point — runs the 5 cases, prints per-case rewards.  |

## Notes

- Model: `deepseek-v3.1-terminus` — the DeepSeek hud.ai routes to (via
  OpenRouter). The plan's `deepseek-v4-flash` is a DeepSeek-direct model;
  on hud.ai's catalog, v3.1-terminus is the live DeepSeek we use.
  (v3.2 is cataloged but currently has no live endpoint; v3.1 routes to
  Tinker which is billing-blocked.)
- Cases: E1, E3, E5, E14, E18. See `cases.py` for the rationale.
- No HTTP bridge to the Oak Mastra backend — the classifier prompt is
  re-implemented as a stand-alone Python call.
- Trim of the original prompt keeps sections 1–6, 10–14, 17, 21 (+23 closing
  reminder) — the slices that the five cases actually exercise.

## Status / next steps (when you're back)

1. Drop `HUD_API_KEY` into `.env`. (Alternative: `hud configure`.)
2. `uv run python smoke.py` — verifies gateway + key + model id.
3. `uv run python hello_world.py` — Phase 1 round-trip.
4. `uv run python run.py` — Phase 2 over all five cases.

Open question flagged during scaffold: the live `EvalContext.current()` /
`ctx.answer` shape is my best guess from probing `hud-python 0.5.41` — if
Phase 1 errors there, the fix is local to `hello_world.py` and
`scenarios.py`. Offline pieces (reward, schemas, prompt, cases) are
already verified with a hand-crafted "perfect" bundle scoring 1.0.
