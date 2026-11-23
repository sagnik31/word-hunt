# ADR 0004: A stateless game server, with each player's progress in the browser

- **Status:** Accepted
- **Date:** 2026-11-08

## Context

Early versions kept one "current game" in server memory, which meant every player shared the same round, and a restart lost it. The backend runs on a free tier that sleeps when idle and has no persistent disk. The game has no accounts and should store nothing personal.

## Decision

- **No game state on the server.** Every request names its puzzle number. The server works out the answer from the schedule and ranks the guess, and nothing about the player is remembered between requests.
- **Progress lives in `localStorage`.** Guesses, help used, the start time, results, the streak and the past-puzzles list are kept in the browser under one versioned key. Old saves are migrated when the format changes. A save records the launch date it belongs to (saves without one date from the first launch, 2026-11-08). When the server reports a different launch date, the old games move to a backup key (`wordhunt:old:<date>`) and play starts afresh, because puzzle numbers restart at a relaunch.
- **The browser reports its stats.** Guesses and quits send the player's stats: seconds since Play, distinct guesses, clues and hints used, and best rank. The server validates their shape and range, then computes the score from them.
- **A random device ID** (a UUID in `localStorage`) is the only identifier. It's used only to count one result per browser per puzzle in the optional results store. There are no accounts.

## Alternatives considered

- **Server-side sessions** (a game record per player, updated on every guess). This would make scores trustworthy, but it needs a database on the hot path of every guess, sign-in or session cookies, and cleanup. It's the natural next step if leaderboards ever matter.
- **A signed start token** (the server signs the puzzle number and start time when Play is pressed, then derives the elapsed time from it). This was suggested to make the clock harder to fake, but it hasn't been built.

## Consequences

- The server can restart, scale or sleep at any time without losing anything a player cares about. It needs no database to run the game itself.
- Progress doesn't follow a player to another browser or device, and clearing site data resets the streak.
- **Scores trust the browser.** A determined player can fake their time or counts, and anyone who knows the day's answer could post results under made-up device IDs. That skews only the "you beat X%" comparison.
- The frontend owns the help-unlock rules (how many guesses before the next clue or hint), so those rules live in `docs/js/ui.js`, not in the backend.
