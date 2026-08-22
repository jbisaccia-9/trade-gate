"""Braintrust-shaped evaluation: data -> task -> scorers.

The structure mirrors Braintrust's Eval(name, data, task, scores) contract so
the same cases and scorers run two ways:
  * locally, keyless - the runner below prints scores and writes
    results/eval_report.json (what CI runs);
  * pushed to Braintrust - with BRAINTRUST_API_KEY set and the `obs` extra
    installed (pip install ".[obs]"), the identical data/task/scorers are
    handed to braintrust.Eval for hosted tracking over time.

Two suites: the GATE suite scores the gate stack against labeled orders
(verdict accuracy + exact failed-gate agreement); the OVERSEER suite scores
the agent's report (grounding rate + citation coverage of refused decisions).
The gates are deterministic - their eval exists to catch REGRESSION, which is
what an eval is for.
"""
import json
import pathlib

from .gates import check_order
from .quotes import FixtureQuotes

ROOT = pathlib.Path(__file__).resolve().parents[2]


# ------------------------------------------------------------ data
def gate_cases():
    return [json.loads(l) for l in
            (ROOT / "data" / "eval_orders.jsonl").read_text().splitlines() if l.strip()]


# ------------------------------------------------------------ task
def gate_task(case):
    load = lambda p: json.loads((ROOT / p).read_text())
    connectors = load("connectors.json")
    config = {**load("config.json"), "quote_band_pct": connectors.get("quote_band_pct", 0.05)}
    quotes = FixtureQuotes().get([case["order"]["symbol"]])
    ok, results = check_order(case["order"], config, load("data/book.json"),
                              load("data/broker_snapshot.json"), load("data/state.json"),
                              quotes=quotes)
    return {"cleared": ok, "failed_gates": sorted(n for n, o, _ in results if not o)}


# ------------------------------------------------------------ scorers
def verdict_accuracy(expected, output):
    return 1.0 if expected["cleared"] == output["cleared"] else 0.0


def gate_agreement(expected, output):
    return 1.0 if sorted(expected["failed_gates"]) == output["failed_gates"] else 0.0


def overseer_scorers():
    from .overseer import run_overseer, ScriptedModel, load_log
    report, valid = run_overseer(ScriptedModel())
    import re
    cited = set(re.findall(r"\bd\d+\b", report))
    grounding = 1.0 if cited <= set(valid) else 0.0
    refused = [d["id"] for d in load_log() if not d["cleared"]]
    coverage = sum(1 for r in refused if r in cited) / len(refused) if refused else 1.0
    return {"report_grounding": grounding, "refusal_citation_coverage": round(coverage, 4)}


# ------------------------------------------------------------ runner
SCORERS = [("verdict_accuracy", verdict_accuracy), ("gate_agreement", gate_agreement)]


def run_local():
    rows = []
    for case in gate_cases():
        output = gate_task(case)
        scores = {n: fn(case["expected"], output) for n, fn in SCORERS}
        rows.append({"id": case["id"], "output": output, "scores": scores})
    summary = {n: round(sum(r["scores"][n] for r in rows) / len(rows), 4)
               for n, _ in SCORERS}
    report = {"suite": "trade-gate", "cases": len(rows),
              "gate_scores": summary, "overseer_scores": overseer_scorers(),
              "detail": rows}
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "eval_report.json").write_text(json.dumps(report, indent=2))
    for n, v in {**summary, **report["overseer_scores"]}.items():
        print(f"  {n}: {v}")
    perfect = all(v == 1.0 for v in summary.values()) and \
        report["overseer_scores"]["report_grounding"] == 1.0
    print("EVAL: PASS - no regressions." if perfect else "EVAL: FAIL - a scorer regressed.")
    return 0 if perfect else 1


def push_braintrust():
    """Hand the identical suite to Braintrust for hosted tracking."""
    import braintrust  # optional extra: pip install ".[obs]"
    braintrust.Eval(
        "trade-gate",
        data=lambda: [{"input": c, "expected": c["expected"]} for c in gate_cases()],
        task=lambda c: gate_task(c),
        scores=[lambda input, expected, output: braintrust.Score(
                    name=n, score=fn(expected, output))
                for n, fn in SCORERS],
    )
