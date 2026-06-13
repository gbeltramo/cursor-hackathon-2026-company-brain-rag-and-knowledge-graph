"""check_thinking.py — probe whether Qwen3.5-9b on Regolo runs a <think> block.

Sends the same prompt twice:
  • round A: enable_thinking=True  (force thinking on)
  • round B: enable_thinking=False (request thinking off)

Prints latency, token counts, whether a <think> block was detected, and the
raw content so you can see exactly what the model returned.

Usage:
    REGOLO_API_KEY=<your_key> python check_thinking.py
"""

from __future__ import annotations

import os
import re
import time

from openai import OpenAI

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REGOLO_API_KEY = os.environ["REGOLO_API_KEY"]
MODEL = os.environ.get("MODEL", "qwen3.5-9b")
BASE_URL = "https://api.regolo.ai/v1"

SYSTEM = "You are a helpful assistant."
QUESTION = "What is the capital of Italy?"

_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

client = OpenAI(api_key=REGOLO_API_KEY, base_url=BASE_URL)


def _call(enable_thinking: bool) -> dict:
    """Single completion call; returns a result dict."""
    extra = {"chat_template_kwargs": {"enable_thinking": enable_thinking}}

    t0 = time.perf_counter()
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user",   "content": QUESTION},
        ],
        extra_body=extra,
    )
    elapsed = time.perf_counter() - t0

    raw: str = response.choices[0].message.content or ""

    think_match = _THINK_RE.search(raw)
    think_text  = think_match.group(1).strip() if think_match else None

    # Strip the think block to isolate the visible answer
    answer = _THINK_RE.sub("", raw).strip()

    usage = response.usage  # may be None depending on endpoint

    return {
        "enable_thinking": enable_thinking,
        "elapsed_s":       round(elapsed, 2),
        "prompt_tokens":   getattr(usage, "prompt_tokens",     "n/a"),
        "completion_tokens": getattr(usage, "completion_tokens", "n/a"),
        "has_think_block": think_match is not None,
        "think_chars":     len(think_text) if think_text else 0,
        "think_snippet":   (think_text[:120] + "…") if think_text and len(think_text) > 120 else think_text,
        "answer":          answer,
        "raw_content":     raw,
    }


def _report(r: dict) -> None:
    flag = "ON " if r["enable_thinking"] else "OFF"
    sep  = "─" * 60
    print(f"\n{sep}")
    print(f"  enable_thinking = {flag}")
    print(sep)
    print(f"  Latency        : {r['elapsed_s']}s")
    print(f"  Tokens (p/c)   : {r['prompt_tokens']} / {r['completion_tokens']}")
    print(f"  <think> block  : {'YES ✗' if r['has_think_block'] else 'no  ✓'}")
    if r["has_think_block"]:
        print(f"  Think chars    : {r['think_chars']}")
        print(f"  Think snippet  : {r['think_snippet']}")
    print(f"  Answer         : {r['answer']}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"Model : {MODEL}")
    print(f"URL   : {BASE_URL}")
    print(f"Q     : {QUESTION!r}")

    results = []
    for thinking in (True, False):
        label = "ON " if thinking else "OFF"
        print(f"\n⏳  Calling with enable_thinking={label} …", flush=True)
        try:
            r = _call(thinking)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            continue
        results.append(r)
        _report(r)

    # --- Summary ---------------------------------------------------------
    if len(results) == 2:
        on, off = results
        speedup = round(on["elapsed_s"] / off["elapsed_s"], 1) if off["elapsed_s"] else "n/a"
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"  thinking=ON   → {on['elapsed_s']}s  | <think>: {'yes' if on['has_think_block'] else 'no'}")
        print(f"  thinking=OFF  → {off['elapsed_s']}s  | <think>: {'yes' if off['has_think_block'] else 'no'}")
        print(f"  Speedup       : {speedup}×")

        if not on["has_think_block"] and not off["has_think_block"]:
            print("\n⚠  Neither call produced a <think> block.")
            print("   Either Regolo strips thinking server-side for this model,")
            print("   or the chat_template_kwargs flag is being ignored.")
            print("   Check additional_kwargs on the raw response for reasoning_content.")
        elif off["has_think_block"]:
            print("\n✗  enable_thinking=False did NOT suppress the think block.")
            print("   Regolo may not honour chat_template_kwargs for this model.")
            print("   Add client-side stripping in message_text() as a safety net.")
        else:
            print("\n✓  enable_thinking=False correctly suppressed the think block.")

        print()


if __name__ == "__main__":
    main()