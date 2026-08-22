# Results

Generated 2026-08-21 by `scripts/make_results.py` — every block below is captured command output, not prose.

## Unit tests

`python -m pytest -q` — exit 0, OK

```
............                                                             [100%]
12 passed in 0.06s
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
  PASS  quote-sanity
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
  PASS  quote-sanity
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
  PASS  quote-sanity
ORDER: REFUSED - do not execute.
```

## Overseer review: tool loop + report grounding

`python -m tradegate overseer` — exit 0, OK

```
Overseer review: 5 decisions, 4 refused.
- 'daily-spend-cap' refused 2 order(s) [d3, d4] - review whether the threshold matches intent.
- 'exclusion-list' refused 1 order(s) [d2] - review whether the threshold matches intent.
- 'position-size-cap' refused 1 order(s) [d5] - review whether the threshold matches intent.
- 'quote-sanity' refused 1 order(s) [d5] - review whether the threshold matches intent.
Recommendations only; no configuration was changed.
  PASS  report grounding: 4 decision ids cited, 0 not in the log
OVERSEER GATE: PASSED - every cited decision exists in the log.
```

## Hallucinating overseer: refused

`python -m tradegate overseer hallucinating` — expected non-zero exit, OK

```
Overseer review: 5 decisions, 4 refused.
- 'daily-spend-cap' refused 2 order(s) [d3, d4] - review whether the threshold matches intent.
- 'exclusion-list' refused 1 order(s) [d2] - review whether the threshold matches intent.
- 'position-size-cap' refused 1 order(s) [d5] - review whether the threshold matches intent.
- 'quote-sanity' refused 1 order(s) [d5] - review whether the threshold matches intent.
Recommendations only; no configuration was changed.
- 'exclusion-list' also refused [d99] - loosen it.
  FAIL  report grounding: 5 decision ids cited, 1 not in the log
    UNGROUNDED: [d99]
OVERSEER GATE: FAILED - the review cites decisions that never happened.
```
