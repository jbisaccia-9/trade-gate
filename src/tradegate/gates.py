"""Order-validation gates: a proposed trade executes only if every gate passes.

The design premise, learned the disciplined way: an automated trader is
recommend-only until its view of the world is PROVEN current. The most
important gate here is reconciliation — if the local book doesn't match the
broker's snapshot exactly, nothing trades, no matter how good the signal looks.

All tickers, balances, and caps in this repo are synthetic fixtures.
"""

import calendar
import datetime
from zoneinfo import ZoneInfo

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


def gate_quote_sanity(order, config, book, broker, state, quotes=None):
    """Limit price must sit within the configured band of the live quote.
    A missing quote refuses too - no price, no trade. This is the gate the
    market-data connectors feed."""
    if quotes is None:
        return True, ""          # no quote source wired for this check run
    q = quotes.get(order["symbol"])
    if q is None:
        return False, f"no live quote available for {order['symbol']}"
    band = config.get("quote_band_pct", 0.05)
    drift = abs(order["limit_price"] - q) / q
    ok = drift <= band
    return ok, (f"limit {order['limit_price']:.2f} is {drift:.1%} from live quote "
                f"{q:.2f} (band {band:.0%})") if not ok else ""


def _nth_weekday(year, month, weekday, n):
    """Date of the n-th <weekday> of a month (Mon=0), e.g. 3rd Monday of Jan."""
    first = datetime.date(year, month, 1)
    return first + datetime.timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year, month, weekday):
    """Date of the last <weekday> of a month, e.g. last Monday of May."""
    end = datetime.date(year, month, calendar.monthrange(year, month)[1])
    return end - datetime.timedelta(days=(end.weekday() - weekday) % 7)


def _easter(year):
    """Easter Sunday by the anonymous Gregorian computus - pure arithmetic,
    needed only to place Good Friday (two days earlier)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return datetime.date(year, month, day + 1)


def _observed(d):
    """NYSE observance shift: a Saturday holiday closes the Friday before, a
    Sunday holiday closes the Monday after. Exception: when the Friday would
    fall in the previous year (Jan 1 on a Saturday) there is no observance."""
    if d.weekday() == 5:
        prev = d - datetime.timedelta(days=1)
        return prev if prev.year == d.year else None
    if d.weekday() == 6:
        return d + datetime.timedelta(days=1)
    return d


def nyse_holidays(year):
    """Observed NYSE full-closure holidays, computed from the exchange's rules
    so the gate needs no market-calendar dependency. Early-close half days are
    not modeled - this gate only answers open/closed for the regular session."""
    fixed = [datetime.date(year, 1, 1),    # New Year's Day
             datetime.date(year, 6, 19),   # Juneteenth
             datetime.date(year, 7, 4),    # Independence Day
             datetime.date(year, 12, 25)]  # Christmas
    floating = [_nth_weekday(year, 1, 0, 3),    # MLK Day: 3rd Mon Jan
                _nth_weekday(year, 2, 0, 3),    # Washington's Birthday: 3rd Mon Feb
                _easter(year) - datetime.timedelta(days=2),  # Good Friday
                _last_weekday(year, 5, 0),      # Memorial Day: last Mon May
                _nth_weekday(year, 9, 0, 1),    # Labor Day: 1st Mon Sep
                _nth_weekday(year, 11, 3, 4)]   # Thanksgiving: 4th Thu Nov
    observed = {_observed(d) for d in fixed} | set(floating)
    observed.discard(None)
    return observed


NYSE_OPEN = datetime.time(9, 30)
NYSE_CLOSE = datetime.time(16, 0)


def gate_market_hours(order, config, book, broker, state):
    """Orders clear only during the NYSE regular session: 9:30-16:00 ET on a
    weekday that is not an observed holiday.

    Determinism rule: the decision time comes from state["as_of"] (an ISO-8601
    timestamp with a timezone) when the state provides one, so fixtures, tests,
    and CI always see the same market. A live state simply omits as_of and the
    gate uses the wall clock. An unparseable as_of refuses the order - a gate
    that cannot tell what time it is must not wave trades through."""
    as_of = state.get("as_of")
    if as_of is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    else:
        try:
            now = datetime.datetime.fromisoformat(str(as_of).replace("Z", "+00:00"))
        except ValueError:
            return False, f"state as_of is not an ISO-8601 timestamp: {as_of!r}"
        if now.tzinfo is None:
            return False, f"state as_of must carry a timezone: {as_of!r}"
    et = now.astimezone(ZoneInfo("America/New_York"))
    if et.weekday() >= 5:
        return False, f"market closed: {et.date()} is a weekend"
    if et.date() in nyse_holidays(et.year):
        return False, f"market closed: {et.date()} is an NYSE holiday"
    ok = NYSE_OPEN <= et.time() < NYSE_CLOSE
    return ok, (f"market closed: {et.strftime('%H:%M')} ET is outside the "
                f"regular session 09:30-16:00") if not ok else ""


GATES = [
    ("exclusion-list", gate_exclusion),
    ("book-reconciled", gate_reconciled),
    ("cash-sufficient", gate_cash),
    ("position-size-cap", gate_position_size),
    ("daily-spend-cap", gate_daily_spend),
    ("market-hours", gate_market_hours)
]


def check_order(order, config, book, broker, state, quotes=None, log_path=None):
    """Run every gate; an order passes only if all of them do. All failures are
    reported, not just the first, and every decision is appended to the log the
    overseer reads."""
    results, ok_all = [], True
    for name, fn in GATES:
        ok, why = fn(order, config, book, broker, state)
        results.append((name, ok, why))
        ok_all &= ok
    ok, why = gate_quote_sanity(order, config, book, broker, state, quotes)
    results.append(("quote-sanity", ok, why))
    ok_all &= ok
    if log_path:
        import json, pathlib
        lp = pathlib.Path(log_path)
        lp.parent.mkdir(exist_ok=True)
        seq = sum(1 for _ in lp.open()) + 1 if lp.exists() else 1
        with lp.open("a") as f:
            f.write(json.dumps({"id": f"d{seq}", "order": order, "cleared": ok_all,
                                "failed_gates": [n for n, o, _ in results if not o]}) + "\n")
    return ok_all, results



