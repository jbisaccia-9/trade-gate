# Results

Generated 2026-08-21 by `scripts/make_results.py` — every block below is captured command output, not prose.

## Unit tests

`python -m pytest -q` — exit 0, OK

```
.......                                                                  [100%]
7 passed in 0.01s
```

## Clean order clears every gate

`python -m tradegate check orders/example_buy.json` — exit 0, OK

```
order: buy 3 CCCC @ 42.5
  PASS  exclusion-list
  PASS  book-reconciled
  PASS  cash-sufficient
  PASS  position-size-cap
  PASS  daily-spend-cap
ORDER: CLEARED for execution.
```

## Stale broker snapshot refuses the same order

`python -m tradegate check orders/example_buy.json --broker data/broker_stale.json` — expected non-zero exit, OK

```
order: buy 3 CCCC @ 42.5
  PASS  exclusion-list
  FAIL  book-reconciled: book at sequence 118 but broker snapshot is 121 - reconcile before trading
  PASS  cash-sufficient
  PASS  position-size-cap
  PASS  daily-spend-cap
ORDER: REFUSED - do not execute.
```

## Excluded symbol refused

`python -m tradegate check orders/refused_excluded.json` — expected non-zero exit, OK

```
order: buy 1 EXCL1 @ 10.0
  FAIL  exclusion-list: symbol EXCL1 is on the exclusion list
  PASS  book-reconciled
  PASS  cash-sufficient
  PASS  position-size-cap
  PASS  daily-spend-cap
ORDER: REFUSED - do not execute.
```
