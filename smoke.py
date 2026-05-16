"""Phase 0 smoke test.

Calls `inference.hud.ai` (OpenAI-compatible gateway) with `deepseek-v4-flash`
and asks it to reply with the literal string `pong`. Confirms (a) the gateway
URL is reachable, (b) the HUD API key works for inference, (c) the model id is
correct, before any scenario plumbing is built on top.
"""

from __future__ import annotations

from hud.settings import settings
from openai import OpenAI

MODEL = "deepseek-v3.1-terminus"


def main() -> None:
    if not settings.api_key:
        raise SystemExit(
            "HUD api_key not set. Put HUD_API_KEY in .env or `hud configure`."
        )

    client = OpenAI(
        base_url=f"{settings.hud_gateway_url}/v1",
        api_key=settings.api_key,
    )

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "Reply with exactly the word: pong"},
            {"role": "user", "content": "ping"},
        ],
        temperature=0,
    )

    text = (resp.choices[0].message.content or "").strip()
    print(f"model:   {MODEL}")
    print(f"reply:   {text!r}")
    print(f"usage:   {resp.usage}")
    print("status:  OK" if "pong" in text.lower() else "status:  UNEXPECTED REPLY")


if __name__ == "__main__":
    main()
