"""CLI:  python -m tradegate check orders/example_buy.json [--broker ...] [--quotes fixture|api|mcp]
        python -m tradegate overseer [scripted|hallucinating|claude]"""
import argparse
import json
import os
import pathlib
import sys

from .gates import check_order

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load(p):
    return json.loads(pathlib.Path(p).read_text())


def main():
    ap = argparse.ArgumentParser(prog="tradegate")
    sub = ap.add_subparsers(dest="cmd", required=True)
    cp = sub.add_parser("check")
    cp.add_argument("order")
    cp.add_argument("--config", default=ROOT / "config.json")
    cp.add_argument("--book", default=ROOT / "data" / "book.json")
    cp.add_argument("--broker", default=ROOT / "data" / "broker_snapshot.json")
    cp.add_argument("--state", default=ROOT / "data" / "state.json")
    cp.add_argument("--quotes", default="fixture")
    op = sub.add_parser("overseer")
    op.add_argument("backend", nargs="?", default="scripted")
    args = ap.parse_args()

    if args.cmd == "overseer":
        from .overseer import run_overseer, report_gate, get_model
        report, cited = run_overseer(get_model(args.backend))
        print(report)
        sys.exit(report_gate(report, cited))

    from .quotes import get_source
    os.environ.setdefault("QUOTES_MODE", args.quotes)
    order = load(args.order)
    connectors = json.loads((ROOT / "connectors.json").read_text())
    config = {**load(args.config), "quote_band_pct": connectors.get("quote_band_pct", 0.05)}
    quotes = get_source(connectors).get([order["symbol"]])
    ok, results = check_order(order, config, load(args.book), load(args.broker),
                              load(args.state), quotes=quotes,
                              log_path=ROOT / "log" / "decisions.jsonl")
    print(f"order: {order['side']} {order['quantity']} {order['symbol']} @ {order['limit_price']}")
    for name, passed, why in results:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}" + (f": {why}" if why else ""))
    print("ORDER: CLEARED for execution." if ok else "ORDER: REFUSED - do not execute.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
