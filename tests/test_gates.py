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
