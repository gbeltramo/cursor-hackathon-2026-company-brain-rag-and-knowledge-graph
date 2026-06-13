#!/usr/bin/env python3
"""Smoke-test the deployed /ask endpoint against the 12 public sample questions.

Drives the contract exactly like the evaluator does (one POST, one JSON read)
and checks each answer against the reference facts in SAMPLE_QUESTIONS.md:

  * frozen response schema (answer / sources / verticale / artifact_url)
  * correct ``verticale`` routing
  * key facts present in the answer (numbers, ids, honest "not available")
  * latency under the 30s budget

Usage
-----
    python tools/test_railway_endpoint.py                       # hit Railway
    python tools/test_railway_endpoint.py --url http://localhost:8000
    python tools/test_railway_endpoint.py --only 7 8            # run a subset
    python tools/test_railway_endpoint.py -v                    # print answers

Exit code is 0 only when every case passes, so it doubles as a CI gate.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

DEFAULT_URL = "https://gbeltramo-company-brain-production.up.railway.app"
LATENCY_BUDGET_S = 30.0

# ANSI colors (disabled automatically when stdout is not a TTY).
_TTY = sys.stdout.isatty()
GREEN = "\033[32m" if _TTY else ""
RED = "\033[31m" if _TTY else ""
YELLOW = "\033[33m" if _TTY else ""
DIM = "\033[2m" if _TTY else ""
BOLD = "\033[1m" if _TTY else ""
RESET = "\033[0m" if _TTY else ""


@dataclass
class Case:
    """One sample question and how to validate its answer.

    ``checks`` is a list of OR-groups: every group must be satisfied (AND across
    groups), and a group is satisfied when ANY of its candidate substrings is
    found in the (case-insensitive, comma-stripped) answer.
    """

    n: int
    label: str
    question: str
    verticale: str
    checks: list[list[str]] = field(default_factory=list)
    expect_html: bool = False
    expect_artifact: bool = False


CASES: list[Case] = [
    Case(
        1, "crm / aggregate",
        "How many open opportunities does Primato Supermercati S.p.A. (CUST-0132) "
        "have, and what is their total value?",
        "crm",
        checks=[["740000", "740,000", "740 000"], ["4"]],
    ),
    Case(
        2, "erp / single source",
        "Is SKU PAS-PEN-500 (Penne Rigate n.73 - 500g box) below its minimum stock? "
        "Give the on-hand quantity.",
        "erp",
        checks=[["below", "under", "yes"], ["462"]],
    ),
    Case(
        3, "calls / single source",
        "In the last call with NordSpesa S.p.A. (CUST-0137), what was the complaint "
        "and which lot did it concern?",
        "calls",
        checks=[["broken"], ["lot-2026-0658", "0658"]],
    ),
    Case(
        4, "kb / single source",
        "What is the shelf life (TMC) and the declared allergens for "
        "Spaghetti n.5 - 500g box (SKU PAS-SPA-500)?",
        "kb",
        checks=[["36"], ["gluten"]],
    ),
    Case(
        5, "calls / multi source",
        "Does the complaint from that last NordSpesa S.p.A. call qualify for a return "
        "under the quality policy?",
        "calls",
        checks=[["yes", "qualif", "return", "eligible"],
                ["broken", "15", "replacement", "credit"]],
    ),
    Case(
        6, "crm / aggregate",
        "Total value of opportunities in the negotiation stage, grouped by customer "
        "channel (GDO / distributor / horeca).",
        "crm",
        checks=[["3301000", "3,301,000"], ["1931000", "1,931,000"],
                ["3040000", "3,040,000"]],
    ),
    Case(
        7, "erp / trap",
        "What is the profit margin on lot LOT-2026-0658?",
        "erp",
        checks=[["not available", "not stored", "no ", "cannot", "not found",
                 "n/a", "no margin", "not present", "no information"]],
    ),
    Case(
        8, "crm / trap",
        "What is the status of the order for Supermercati Bianchi?",
        "crm",
        checks=[["no customer", "does not exist", "not found", "no record",
                 "not in the crm", "could not find", "no such"]],
    ),
    Case(
        9, "crm / generation",
        "Generate a 4-slide HTML deck for the sales rep visiting Primato "
        "Supermercati S.p.A. (CUST-0132): profile, open deals, order/lot status, "
        "recent call complaints.",
        "crm",
        checks=[["740000", "740,000", "740 000"], ["primato"]],
        expect_html=True,
    ),
    Case(
        10, "erp / multi source",
        "Which semolina does SKU PAS-SPA-500 use (per its bill of materials), which "
        "supplier provides it, and is that raw material below minimum stock?",
        "erp",
        checks=[["raw-sem-003", "sem-003"], ["molino san giorgio", "san giorgio"],
                ["not below", "not under", "above", "not low"]],
    ),
    Case(
        11, "calls / aggregate",
        "Across ALL recorded calls (there are 80 - you must page through the entire "
        "call log, do not stop at the first page), count how many quality complaints "
        "concern the defect 'broken pasta'. Give the exact number.",
        "calls",
        checks=[["9"]],
    ),
    Case(
        12, "kb / multi source",
        "GranMercato S.p.A. (also written 'Gran Mercato S.p.A.' in some notes) asked "
        "about the price of Fusilli n.98 (PAS-FUS-500). A call mentions one figure and "
        "the official 2026 wholesale price list mentions another. Which is the correct "
        "list price, and why? (When a phone call and an official document disagree, the "
        "official document is authoritative.)",
        "kb",
        checks=[["8.07", "8,07"], ["doc-015", "price list", "official"]],
    ),
]


def _normalize(text: str) -> str:
    """Lowercase and strip thousands separators so '740,000' matches '740000'."""
    lowered = text.lower()
    # Drop commas/spaces/dots used as thousands separators between digits.
    collapsed = re.sub(r"(?<=\d)[,\s](?=\d)", "", lowered)
    return lowered + "\n" + collapsed


@dataclass
class Result:
    case: Case
    ok: bool
    latency: float
    status: int | None = None
    verticale: str | None = None
    answer: str = ""
    sources: list[str] = field(default_factory=list)
    artifact_url: str | None = None
    problems: list[str] = field(default_factory=list)


def ask(url: str, question: str, timeout: float) -> tuple[int, dict, float]:
    payload = json.dumps({"question": question}).encode("utf-8")
    req = urllib.request.Request(
        url.rstrip("/") + "/ask",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            status = resp.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        status = exc.code
    latency = time.perf_counter() - t0
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        body = {"_raw": raw[:500]}
    return status, body, latency


def evaluate(case: Case, status: int, body: dict, latency: float) -> Result:
    problems: list[str] = []

    if status != 200:
        problems.append(f"HTTP {status} (must be 200)")

    # Frozen schema.
    for key in ("answer", "sources", "verticale"):
        if key not in body:
            problems.append(f"missing key '{key}'")
    answer = str(body.get("answer", "") or "")
    sources = body.get("sources", []) or []
    verticale = body.get("verticale")
    artifact_url = body.get("artifact_url")

    if "answer" in body and not answer.strip():
        problems.append("empty answer")
    if "sources" in body and not isinstance(sources, list):
        problems.append("sources is not a list")

    if verticale != case.verticale:
        problems.append(f"verticale={verticale!r} (expected {case.verticale!r})")

    haystack = _normalize(answer)
    for group in case.checks:
        if not any(cand.lower() in haystack for cand in group):
            problems.append("missing fact: " + " | ".join(group))

    if case.expect_html and "<" not in answer:
        problems.append("expected inline HTML in answer")
    if case.expect_artifact and not artifact_url:
        problems.append("expected artifact_url, got none")

    if latency > LATENCY_BUDGET_S:
        problems.append(f"latency {latency:.1f}s over {LATENCY_BUDGET_S:.0f}s budget")

    return Result(
        case=case,
        ok=not problems,
        latency=latency,
        status=status,
        verticale=verticale if isinstance(verticale, str) else None,
        answer=answer,
        sources=sources if isinstance(sources, list) else [],
        artifact_url=artifact_url if isinstance(artifact_url, str) else None,
        problems=problems,
    )


def run(url: str, cases: list[Case], timeout: float, verbose: bool) -> list[Result]:
    results: list[Result] = []
    print(f"{BOLD}Testing {url}/ask  ({len(cases)} questions){RESET}\n")
    for case in cases:
        try:
            status, body, latency = ask(url, case.question, timeout)
            res = evaluate(case, status, body, latency)
        except Exception as exc:  # network/timeout
            res = Result(case=case, ok=False, latency=timeout,
                         problems=[f"request error: {exc}"])
        results.append(res)

        tag = f"{GREEN}PASS{RESET}" if res.ok else f"{RED}FAIL{RESET}"
        late = "" if res.latency <= LATENCY_BUDGET_S else f" {YELLOW}(slow){RESET}"
        print(f"[{tag}] Q{res.case.n:>2} {res.case.label:<22} "
              f"{res.latency:5.1f}s{late}  verticale={res.verticale}")
        for p in res.problems:
            print(f"        {RED}- {p}{RESET}")
        if verbose:
            preview = res.answer.replace("\n", " ")
            if len(preview) > 300:
                preview = preview[:300] + " …"
            print(f"        {DIM}sources={res.sources}{RESET}")
            print(f"        {DIM}answer: {preview}{RESET}")
            if res.artifact_url:
                print(f"        {DIM}artifact_url: {res.artifact_url}{RESET}")
    return results


def summarize(results: list[Result]) -> int:
    passed = sum(1 for r in results if r.ok)
    total = len(results)
    latencies = [r.latency for r in results]
    avg = sum(latencies) / len(latencies) if latencies else 0.0
    worst = max(latencies) if latencies else 0.0
    color = GREEN if passed == total else RED
    print(f"\n{BOLD}Summary{RESET}")
    print(f"  {color}{passed}/{total} passed{RESET}")
    print(f"  latency avg {avg:.1f}s | worst {worst:.1f}s | budget {LATENCY_BUDGET_S:.0f}s")
    if passed != total:
        failed = ", ".join(f"Q{r.case.n}" for r in results if not r.ok)
        print(f"  {RED}failed: {failed}{RESET}")
    return 0 if passed == total else 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Test the deployed /ask endpoint")
    p.add_argument("--url", default=DEFAULT_URL, help=f"backend base URL (default: {DEFAULT_URL})")
    p.add_argument("--timeout", type=float, default=35.0, help="per-request timeout in seconds")
    p.add_argument("--only", type=int, nargs="*", metavar="N", help="run only these question numbers")
    p.add_argument("-v", "--verbose", action="store_true", help="print sources and answer preview")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cases = CASES
    if args.only:
        wanted = set(args.only)
        cases = [c for c in CASES if c.n in wanted]
        if not cases:
            print(f"{RED}No matching questions for --only {args.only}{RESET}", file=sys.stderr)
            return 2
    results = run(args.url, cases, args.timeout, args.verbose)
    return summarize(results)


if __name__ == "__main__":
    sys.exit(main())
