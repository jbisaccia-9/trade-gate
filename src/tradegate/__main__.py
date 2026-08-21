"""CLI:  python -m tradegate check orders/example_buy.json [--broker data/broker_stale.json]"""
import argparse
import json
import pathlib
import sys

from .gates import check_order

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load(p):
    return json.loads(pathlib.Path(p).read_text())


def main():
    ap = argparse.ArgumentParser(prog="tradegate")
    sub = ap.add_subparsers(dest="cmd", required=True)
    cp = sub.add_parser("check", help="validate a proposed order against every gate")
    cp.add_argument("order")
    cp.add_argument("--config", default=ROOT / "config.json")
    cp.add_argument("--book", default=ROOT / "data" / "book.json")
    cp.add_argument("--broker", default=ROOT / "data" / "broker_snapshot.json")
    cp.add_argument("--state", default=ROOT / "data" / "state.json")
    args = ap.parse_args()
    order = load(args.order)
    ok, results = check_order(order, load(args.config), load(args.book),
                              load(args.broker), load(args.state))
    print(f"order: {order['side']} {order['quantity']} {order['symbol']} @ {order['limit_price']}")
    for name, passed, why in results:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}" + (f": {why}" if why else ""))
    print("ORDER: CLEARED for execution." if ok else "ORDER: REFUSED - do not execute.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
