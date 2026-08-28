# Contributing

Thanks for considering a contribution. This repo is part of a small family of "-gate" projects that each enforce one measured bar before letting something ship — please keep contributions in that spirit.

## Ground rules

- **The gate must still pass.** Every PR needs to pass the existing gate/eval suite (CI on this repo). Making the gate stricter or changing what it measures is welcome — but the gate itself has to still run and produce a real pass/fail.
- **Threshold changes go in config, with a reason.** If you're proposing a change to a pass/fail threshold (a recall bar, a kappa minimum, a spend cap, etc.), change it in the config file where it lives, not by hardcoding a new number inline — and explain *why* in the PR description.
- **Data stays synthetic.** All fixtures, golden sets, and example data in this repo are synthetic or public-domain. Don't add real PII, real credentials, real account data, or anything proprietary.

## Getting started

1. Fork the repo and clone your fork.
2. Follow the Quickstart in the README to get a working local environment (no API key required for the base path).
3. Run the test suite and the gate locally before opening a PR — both should be green (or, for a deliberately-failing example, fail for the expected reason).
4. Open a PR against `main`. Small, focused PRs are easier to review than large ones.

## Good first issues

Issues labeled `good first issue` are scoped to be approachable without deep context on the rest of the repo. `help wanted` issues are open to anyone.

## Code of conduct

This project follows the [Code of Conduct](CODE_OF_CONDUCT.md).
