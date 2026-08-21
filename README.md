# trade-gate

**Order-validation gates for an automated trader. Every trade must pass all of
them — and a stale book refuses everything.**

The premise, learned by running a real automated trading loop with real
discipline requirements: the dangerous moment isn't a bad signal, it's a bot
acting on a view of the world that's no longer true. So the load-bearing gate
here is **reconciliation** — if the local book doesn't match the broker's
snapshot position-for-position at the same sync sequence, no order executes,
no matter how good the trade looks. Everything in this repo is synthetic:
fictional tickers, invented balances, example caps.

Part of the *-gate* family:
[kappa-gate](https://github.com/jbisaccia-9/kappa-gate) ·
[roi-gate](https://github.com/jbisaccia-9/roi-gate) ·
[phi-gate](https://github.com/jbisaccia-9/phi-gate).
One thesis throughout: nothing ships until it passes a gate.

## The gates

| gate | refuses when |
|---|---|
| exclusion-list | the symbol is on the hard denylist — unconditional |
| **book-reconciled** | local positions ≠ broker snapshot, or sync sequences differ |
| cash-sufficient | order cost exceeds settled cash |
| position-size-cap | position would exceed a fixed fraction of portfolio value |
| daily-spend-cap | today's cumulative spend would exceed the cap |

All failures are reported, not just the first — a refused order should teach
something. CI runs the demo both ways: the clean order must clear, and the
excluded order must be refused (`! python -m tradegate check ...`) — the
unguarded path is a failing test.

```
$ python -m tradegate check orders/example_buy.json --broker data/broker_stale.json
order: buy 3 CCCC @ 42.5
  PASS  exclusion-list
  FAIL  book-reconciled: book at sequence 118 but broker snapshot is 121 - reconcile before trading
  PASS  cash-sufficient
  PASS  position-size-cap
  PASS  daily-spend-cap
ORDER: REFUSED - do not execute.
```

## Quickstart

```
python -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
.venv/bin/python -m tradegate check orders/example_buy.json
```

Educational code about guardrail design. Not a trading system, not financial
advice; the fixtures are fiction.

MIT license.
