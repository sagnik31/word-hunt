# ADR 0003: Keep the daily schedule secret in a public repository with HMAC codes

- **Status:** Accepted
- **Date:** 2026-11-08

## Context

Every player gets the same secret word each UTC day. The repository is public, and the server is deployed straight from it, so anything committed is readable by anyone. The schedule (which word on which day) and the written clues for each word both have to ship with the code, without giving away future answers. The schedule must also be stable: once a day's puzzle has been played, it must never change.

## Decision

- **Codes, not words.** `data/daily_schedule.txt` has one line per puzzle, and each line is the first 20 hex characters of `HMAC-SHA256(key, word)`. Line N is puzzle #N, and puzzle #1 is `LAUNCH_DATE` in `backend/config.py`.
- **The key is the only secret.** It comes from the `WORDHUNT_SCHEDULE_KEY` environment variable (in production) or a git-ignored `schedule.key` file (locally).
- **Decoding at startup.** The server hashes every candidate answer with the key and matches the codes, so it knows each day's word without the word ever being written to disk in the repo.
- **Clues use the same codes.** `data/clues.json` is keyed by schedule code, so the public file doesn't say which clues belong to which word.
- **Append-only schedule.** `backend/scripts/build_schedule.py` never changes today's or earlier lines. It drops future words that are no longer answers and appends new ones, and no word repeats.
- **Unreleased puzzles are refused.** Every request names a puzzle number, and the server returns 404 for one after today's.

## Alternatives considered

- **A private repository or a private data store for the schedule.** More moving parts for a hobby project, and it would make the repo harder to fork and run.
- **Picking the word with a seeded random generator.** Anyone could rerun the generator from the public code. Keeping the seed secret is equivalent to a key anyway, and an explicit list is easier to edit and freeze.
- **Encrypting the whole schedule file.** Works, but per-line keyed hashes are simpler, let each line be checked on its own, and make it easy to append without re-encrypting.

## Consequences

- Losing the key makes the schedule and the clues unreadable. It has to be backed up outside the repo.
- A fork can't read the original schedule. It builds its own with a new key (`build_schedule.py --new-key`, writing to a separate `WORDHUNT_SCHEDULE_PATH`).
- The tests and CI never see the real key. They build their own throwaway schedule.
- Changing `LAUNCH_DATE` or deleting the schedule file would change puzzles people have already played, so both are treated as one-off relaunch decisions. This has happened once: on 2026-11-23 the game started again at puzzle #1 with the hand-picked answers ([ADR 0009](0009-hand-picked-answer-list.md)), with a fresh schedule built under the same key so the clues still match.
- The hashes hide words only from people without the key. Since the vocabulary is public and small, the key must be long and random, not a guessable phrase.
- Anything that would reveal an answer (a decoded schedule, a clue report naming words, a startup log line) stays out of committed files and logs.
