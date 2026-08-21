"""Order-validation gates: a proposed trade executes only if every gate passes.

The design premise, learned the disciplined way: an automated trader is
recommend-only until its view of the world is PROVEN current. The most
important gate here is reconciliation — if the local book doesn't match the
broker's snapshot exactly, nothing trades, no matter how good the signal looks.

All tickers, balances, and caps in this repo are synthetic fixtures.
"""

def gate_exclusion(order, config, *_):
    """Hard denylist. An excluded ticker is refused unconditionally."""
    ok = order["symbol"] not in config["excluded_symbols"]
    return ok, f"symbol {order['symbol']} is on the exclusion list" if not ok else ""


def gate_reconciled(order, config, book, broker, _):
    """The book must match the broker snapshot, position for position, and be
    from the same sync sequence. Stale book -> no trade. This is the gate that
    turns 'the bot thinks it has $5,000' into 'the broker agrees'."""
    if book["last_reconciled_sequence"] != broker["sequence"]:
        return False, (f"book at sequence {book['last_reconciled_sequence']} but broker "
                       f"snapshot is {broker['sequence']} - reconcile before trading")
    if book["positions"] != broker["positions"]:
        return False, "local positions do not match broker positions - reconcile before trading"
    return True, ""


def gate_cash(order, config, book, *_):
    cost = order["quantity"] * order["limit_price"]
    ok = cost <= book["cash"]
    return ok, f"order costs {cost:.2f} but book cash is {book['cash']:.2f}" if not ok else ""


def gate_position_size(order, config, book, *_):
    """No single position may exceed a fixed fraction of portfolio value."""
    cost = order["quantity"] * order["limit_price"]
    existing = book["positions"].get(order["symbol"], {}).get("value", 0.0)
    total = book["cash"] + sum(p["value"] for p in book["positions"].values())
    cap = total * config["max_position_fraction"]
    ok = existing + cost <= cap
    return ok, (f"position would be {existing + cost:.2f}, cap is {cap:.2f} "
                f"({config['max_position_fraction']:.0%} of {total:.2f})") if not ok else ""


def gate_daily_spend(order, config, book, broker, state):
    """Spend cap per day, counting orders already placed today."""
    cost = order["quantity"] * order["limit_price"]
    ok = state["spent_today"] + cost <= config["daily_spend_cap"]
    return ok, (f"spent {state['spent_today']:.2f} today; this order adds {cost:.2f}, "
                f"cap is {config['daily_spend_cap']:.2f}") if not ok else ""


GATES = [
    ("exclusion-list", gate_exclusion),
    ("book-reconciled", gate_reconciled),
    ("cash-sufficient", gate_cash),
    ("position-size-cap", gate_position_size),
    ("daily-spend-cap", gate_daily_spend),
]


def check_order(order, config, book, broker, state):
    """Run every gate; an order passes only if all of them do. All failures are
    reported, not just the first - a refused order should teach something."""
    results, ok_all = [], True
    for name, fn in GATES:
        ok, why = fn(order, config, book, broker, state)
        results.append((name, ok, why))
        ok_all &= ok
    return ok_all, results
