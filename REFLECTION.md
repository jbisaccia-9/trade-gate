# Reflection: why I shut down the real bot

This repo is the public version of something I actually built: an agentic
trading bot with a small real-money stake, Claude as the decision-maker, a
brokerage MCP server as its hands, and a second agent overseeing it. I started
it in June 2026, let it run unattended from late July, and shut it down for
good on 2026-10-13.

As far as every audit showed, it never broke a hard rule and never fabricated a trade. I shut it down anyway.
This is why I did it, what I learned, and what I'd do differently in the future.

## How it ended

The README opens with the premise that the dangerous moment isn't a bad signal,
it's a bot acting on a view of the world that's no longer true. That's exactly
how the real one died, except it did the right thing about it.

On 2026-10-12 the broker connection's OAuth authorization expired. The bot ran
headless, and an OAuth re-authorization needs a human in a browser. From that
tick on, every run found that its broker tools wouldn't load, and the bot
refused to proceed. No reconciliation, no orders, no made-up positions. It
logged each tick as an honest `FAILED`. Every tick after that failed closed,
exactly as designed.

Failing closed was correct. But it exposed what I hadn't designed for: my
stop-losses were synthetic. They lived in the bot, not at the broker. A bot
that correctly refuses to act is also a bot that isn't watching your
positions. The gate held, and the portfolio was unprotected anyway.

**Lesson: protective orders belong at the broker. An agent can propose
risk management; it shouldn't be the only thing performing it.**

There was also a cost problem. My Claude Code CLI repeatedly logged me out of my subscription plan and switched itself over to API usage credits. This happened multiple times throughout the experiment, usually after software updates from Anthropic.

As a result, the roughly 5% return on the stock trades was far smaller than what I spent on API credits. Over the course of the experiment, API usage cost more than $250 in additional expense.

## The pattern I couldn't ignore

When I finally read back through the wrapper script that ran each tick, most
of its comments were incident reports. Every guard had a date on it:

| when | what broke | the patch |
|---|---|---|
| Jul 30 | CLI auth failed, printed "Not logged in", **exited 0**. Silent no-op. | Require positive proof a tick ran; silence must never mean healthy |
| Aug 3 | Alerting grepped the model's prose, and a healthy tick that wrote "no NEEDS JOSEPH condition" tripped the alarm on its own negation | A machine-readable final `STATUS:` line |
| Aug 5 | One tick hung holding file locks; the scheduler kept launching more; 15+ ticks failed over ~7 hours | A `mkdir` mutex so two ticks never run at once |
| Aug 6 | The insider-buying sweep had been web-searching pages that can't be indexed. "No cluster found" had really meant "no data retrieved", for weeks | Read the primary source (SEC filings) directly; report `UNCHECKED`, never a false zero |
| Aug 22 | The bot's state file grew past the model's file-read limit from append-only drift | Deterministic trimming in shell |
| Sep 4 | The daily spend guard lived in the prompt. Auditing transcripts showed the model had **never once** called it | The guard moved into shell, before any model starts |
| Sep 16 | A tick started during macOS DarkWake and crawled for 31 minutes | Hold the machine awake for the tick |
| Sep 21 | Tool loading hung for 28 and 43 minutes | A wall-clock cap |
| Sep 24 | A seconds-long broker 502 cost the only buying slot of the day | A retry latch |
| Oct 12 | Broker OAuth expired | — |

Each patch was right. Together they told me the system had stopped being a
trading strategy with some infrastructure and become infrastructure with
some trading attached. The strategy (mirroring lagged congressional and
insider filings) had a modest edge at best. The maintenance didn't.

The last row has no patch because there isn't one I trust. The broker's auth
is bound to a human session by design, and that's a reasonable security
choice on their side. "Unattended agent" and "human-gated credentials" are in
direct tension, and every workaround I could think of meant weakening a
control I'd put there on purpose.

## What I'd keep

**A guard the model has to remember to run is not a guard.** The spend guard
taught me this most clearly. Prompts are suggestions; shell runs every time.
Anything load-bearing (budgets, locks, reconciliation checks, alerting) now
goes in deterministic code around the model, not in instructions to it. That
is the thesis of this whole repo: the gates are plain Python, and the model
never gets a vote on whether they run.

**Silence must mean "verified healthy", never "nothing happened".** Exit code 0
told me nothing. Prose told me less. Only an explicit, un-negatable status
line was trustworthy, and a *missing* status line had to count as a failure.

**"No result" and "no data" are different answers.** The worst bug I found
wasn't a crash. It was weeks of confident "nothing qualifies" that really meant
"I couldn't see anything." A verified zero is a real result, and an unchecked
path has to say so.

**Graders grade what's written, not what was done.** My overseer agent scored
each tick's reasoning, and it could only score the evidence the bot actually
wrote down. "Reconciliation matched, all clear" with no numbers scored the
same as skipping the check. Overseers, and the grounding gate here, need
claims tied to evidence they can verify.

**The overseer stays recommend-only.** The real overseer had exactly one
narrow, gated, auto-reverting write path. Everything else was advice. That
boundary never caused a problem, and I'd draw it the same way again. Here it's
structural: the overseer's tool registry is read-only, and the tests assert it.

**Cost is a design input.** Routing routine watch-only ticks to a small model
and keeping the expensive model for the one daily decision cut per-tick cost
by roughly 85%. Moving mechanical bookkeeping out of model turns and into a
script saved more. Every model turn re-sends the whole conversation, so
"just let the agent do it" has a real price.

## Why stop instead of fix

The goal was never the money. I'd already retired an unrealistic growth target
in June in favor of "stay disciplined, don't blow up, learn." By that
measure it worked. The hard rules held through four months of live
operation, including when the infrastructure underneath them didn't.

But the learning curve had flattened, and the failure mode had changed. Early
on, failures taught me something new about agent design. By October they were
mostly the same lesson ("unattended plus human-gated auth plus a laptop is
fragile") showing up in different forms. And each time, real positions sat
unmonitored until I noticed. A learning project that keeps putting real money
at quiet risk for diminishing lessons is a good one to end.

So I sold the holdings, revoked every key, and archived the code. This repo is
what I'm keeping: the gates, the overseer boundary, the evals, and the habit of
treating every claim an agent makes as something that has to pass a check.

In closing, I can definitely see the potential in agent-supported asset trading. However, it's still an area with considerable risk. Until agents can operate more consistently, I wouldn't feel comfortable handing my asset management to an AI agent, nor would I recommend doing so with the expectation of beating the market. It's very rare for a human to beat the market, and it's likely even harder for an AI agent at this point.

---

*The real bot's code, logs, and account details stay private. Everything in
this repo remains synthetic. Not financial advice.*
