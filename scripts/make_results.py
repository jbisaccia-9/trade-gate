#!/usr/bin/env python3
"""Regenerate RESULTS.md from the actual commands — never hand-edit the output.

Run from the repo root: .venv/bin/python scripts/make_results.py
Each command's real stdout/stderr and exit code are captured verbatim; a result
that can be edited by hand is a claim, not a result.
"""
import datetime
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
PY = str(ROOT / ".venv" / "bin" / "python")

COMMANDS = [("Unit tests", ["-m", "pytest", "-q"], False), ("Clean order clears every gate", ["-m", "tradegate", "check", "orders/example_buy.json"], False), ("Stale broker snapshot refuses the same order", ["-m", "tradegate", "check", "orders/example_buy.json", "--broker", "data/broker_stale.json"], True), ("Excluded symbol refused", ["-m", "tradegate", "check", "orders/refused_excluded.json"], True), ("Overseer review: tool loop + report grounding", ["-m", "tradegate", "overseer"], False), ("Hallucinating overseer: refused", ["-m", "tradegate", "overseer", "hallucinating"], True)]

out = [f"# Results\n",
       f"Generated {datetime.date.today()} by `scripts/make_results.py` — "
       f"every block below is captured command output, not prose.\n"]
for title, cmd, expect_fail in COMMANDS:
    r = subprocess.run([PY] + cmd, cwd=ROOT, capture_output=True, text=True)
    body = (r.stdout + r.stderr).strip()
    verdict = "expected non-zero exit" if expect_fail else "exit 0"
    status = "OK" if (r.returncode != 0) == expect_fail else "UNEXPECTED"
    out.append(f"## {title}\n\n`{' '.join(['python'] + cmd)}` — {verdict}, {status}\n\n"
               f"```\n{body}\n```\n")
(ROOT / "RESULTS.md").write_text("\n".join(out))
print(f"wrote RESULTS.md ({len(COMMANDS)} sections)")
