# ADR 0005: One scoring module on the server, where a quit never beats a solve

- **Status:** Accepted
- **Date:** 2026-11-15

## Context

A single number has to summarise a play: how long it took, how many guesses, and how much help was used. Players can also quit, which reveals the answer, and a quit should earn something for getting close. Two things went wrong with the first scoring rules:

- quitting near the answer could score more than a slow solve with help, which rewards giving up;
- the rules were spread across the frontend and the backend, so the numbers on the buttons could drift from the ones used to score.

## Decision

- **Solve:** 100 points, minus a time penalty (none for 2 minutes, then a curve that flattens towards a cap of 30), the cost of each clue and hint used, and a small penalty for many guesses. **A solve never scores below 25.**
- **Quit:** 20% of 100 minus the same penalties, times a closeness factor from the best rank reached (1 at rank 2, falling on a log scale to 0 at rank 1,000). **A quit can score at most 20.**
- **Invariant:** because the best quit (20) is below the worst solve (25), **a player who quits never beats one who solved**, however much help the solver used. An `assert` in the module guards the constants, and a property test checks it over tens of thousands of inputs.
- **One home for the rules:** every number is a constant at the top of `backend/scoring.py`. The server computes every score from the stats the browser sends; the browser never computes its own.
- **Display copies are tested.** The frontend shows the help costs on its buttons and in the rules text, and the README quotes them. A test fails if any copy differs from `scoring.py`.
- **Help comes in a fixed ladder**: three written clues, then two hints that reveal a real nearby word. Each hint costs more than any clue, so clues are always the cheaper way to get unstuck.

## Alternatives considered

- **Scoring by percentile only** (the old quit score was roughly "half your best percentile, minus help"). Easy to explain, but it let a close quit outscore a solve.
- **Scoring in the browser.** Simpler, but it puts the rules in two places, and the results comparison needs a score the server worked out.
- **Server-side scoring from a recorded guess history.** More trustworthy, but it needs a record of each player's guesses on the server, which the game otherwise doesn't keep. Not built.

## Consequences

- Changing a number means changing `scoring.py`, then the copies in `docs/js/ui.js`, `docs/index.html` and the README. The test points at any copy that was missed.
- The score is only as honest as the stats the browser reports.
- The rounding is half-up (not Python's banker's rounding), so the same inputs give the same score in any language that reimplements it.
