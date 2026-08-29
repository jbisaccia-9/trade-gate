import json
import pathlib
from tradegate.gates import check_order

ROOT = pathlib.Path(__file__).resolve().parents[1]


def fixtures(broker="broker_snapshot.json"):
    load = lambda p: json.loads((ROOT / p).read_text())
    return (load("config.json"), load("data/book.json"),
            load(f"data/{broker}"), load("data/state.json"))


def order(**kw):
    base = {"symbol": "CCCC", "side": "buy", "quantity": 3, "limit_price": 42.5}
    base.update(kw)
    return base


def test_good_order_clears_every_gate():
    ok, results = check_order(order(), *fixtures())
    assert ok and all(passed for _, passed, _ in results)


def test_excluded_symbol_refused():
    ok, results = check_order(order(symbol="EXCL1"), *fixtures())
    assert not ok
    assert dict((n, p) for n, p, _ in results)["exclusion-list"] is False


def test_stale_book_refuses_everything():
    # Broker moved to sequence 121 and holds 12 AAAA; the local book says 10.
    ok, results = check_order(order(), *fixtures("broker_stale.json"))
    assert not ok
    assert dict((n, p) for n, p, _ in results)["book-reconciled"] is False


def test_insufficient_cash_refused():
    ok, results = check_order(order(quantity=200, limit_price=42.5), *fixtures())
    assert dict((n, p) for n, p, _ in results)["cash-sufficient"] is False


def test_position_cap_refused():
    # Portfolio value: 4200 cash + 850 + 512 = 5562; 10% cap = 556.20.
    # AAAA already holds 850 - ANY additional AAAA purchase must be refused.
    ok, results = check_order(order(symbol="AAAA", quantity=1, limit_price=10.0), *fixtures())
    assert dict((n, p) for n, p, _ in results)["position-size-cap"] is False


def test_daily_spend_cap_refused():
    # 180 spent today + 8*42.5=340 -> 520 > 500 cap.
    ok, results = check_order(order(quantity=8), *fixtures())
    assert dict((n, p) for n, p, _ in results)["daily-spend-cap"] is False


def test_all_failures_reported_not_just_first():
    ok, results = check_order(order(symbol="EXCL1", quantity=500), *fixtures("broker_stale.json"))
    failed = [n for n, p, _ in results if not p]
    assert set(failed) >= {"exclusion-list", "book-reconciled", "cash-sufficient"}


def test_quote_sanity_refuses_drifted_limit():
    from tradegate.gates import gate_quote_sanity
    cfg = {"quote_band_pct": 0.05}
    ok, _ = gate_quote_sanity({"symbol": "CCCC", "limit_price": 42.5}, cfg, None, None, None,
                              quotes={"CCCC": 42.6})
    assert ok
    ok, why = gate_quote_sanity({"symbol": "CCCC", "limit_price": 30.0}, cfg, None, None, None,
                                quotes={"CCCC": 42.6})
    assert not ok and "band" in why
    ok, why = gate_quote_sanity({"symbol": "ZZZZ", "limit_price": 10.0}, cfg, None, None, None,
                                quotes={"ZZZZ": None})
    assert not ok and "no live quote" in why


def test_mcp_connector_end_to_end():
    import sys
    from tradegate.quotes import MCPQuotes
    q = MCPQuotes([sys.executable, str(ROOT / "tests" / "toy_mcp_server.py")],
                  "get_equity_quotes")
    got = q.get(["CCCC", "AAAA", "ZZZZ"])
    assert got["CCCC"] == 42.6 and got["AAAA"] == 85.0 and got["ZZZZ"] is None


def test_bad_mcp_quote_data_refuses_order(monkeypatch):
    import sys
    from tradegate.quotes import MCPQuotes
    monkeypatch.setenv("TOY_MCP_BAD_QUOTES", "1")
    q = MCPQuotes([sys.executable, str(ROOT / "tests" / "toy_mcp_server.py")],
                  "get_equity_quotes")
    ok, results = check_order(order(), *fixtures(), quotes=q.get(["CCCC"]))
    by_gate = {n: (p, why) for n, p, why in results}
    assert not ok
    assert by_gate["quote-sanity"][0] is False
    assert "no live quote" in by_gate["quote-sanity"][1]


def test_overseer_reviews_and_grounds():
    from tradegate.overseer import run_overseer, report_gate, ScriptedModel
    report, valid = run_overseer(ScriptedModel())
    assert "daily-spend-cap" in report and "[d3, d4]" in report
    assert "no configuration was changed" in report.lower()
    assert report_gate(report, valid) == 0


def test_hallucinating_overseer_refused():
    from tradegate.overseer import run_overseer, report_gate, HallucinatingModel
    report, valid = run_overseer(HallucinatingModel())
    assert report_gate(report, valid) == 1


def test_overseer_has_no_mutating_tools():
    from tradegate.overseer import make_tools
    registry, _, _ = make_tools()
    assert set(registry) == {"get_decision_log", "get_gate_stats", "get_quotes"}
    # Authority is structural: every tool is a read. Nothing writes, nothing trades.


def test_eval_suite_all_perfect():
    from tradegate.evals import run_local
    assert run_local() == 0


def test_eval_catches_regression():
    from tradegate.evals import gate_task, verdict_accuracy, gate_agreement
    case = {"order": {"symbol": "EXCL1", "side": "buy", "quantity": 1, "limit_price": 10.0},
            "expected": {"cleared": False, "failed_gates": ["exclusion-list"]}}
    out = gate_task(case)
    assert verdict_accuracy(case["expected"], out) == 1.0
    # A regressed expectation must score 0 - the scorer is not a rubber stamp.
    assert gate_agreement({"cleared": False, "failed_gates": ["daily-spend-cap"]}, out) == 0.0
