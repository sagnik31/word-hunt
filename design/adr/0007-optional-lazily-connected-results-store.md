# ADR 0007: Store results in an optional, lazily connected Postgres database

- **Status:** Accepted
- **Date:** 2026-11-15

## Context

After finishing, a player should see how they did against the day's other players ("You beat 62% of today's players", the solve rate and a chart of guess counts). That needs results shared across players, which the otherwise stateless game doesn't have. Constraints:

- the backend's free host wipes its disk on every restart, so a local SQLite file would lose the data;
- the free managed database (Neon Postgres) pauses after a few idle minutes and drops connections;
- the game itself must keep working if the database is missing, paused or broken;
- there are no accounts, and nothing personal may be stored.

## Decision

- **Postgres on Neon's free plan,** reached through its pooled connection string in `DATABASE_URL`. The driver is psycopg 3, imported only when a Postgres URL is used. Server-side prepared statements are off, as the pooler requires.
- **Optional:** with no `DATABASE_URL`, results are off. Play is unaffected, `/results` returns 503 and the frontend hides the panel.
- **Lazy:** the server never connects at startup, and `/health` never queries the database, so health checks don't keep Neon awake and a paused database can't stop a deploy. The first query connects and creates the table. A failed query reconnects and retries once. Each Postgres query, creating the table included, runs in its own short transaction with `SET LOCAL statement_timeout` (`QUERY_TIMEOUT_MS`, 5 s), so a stuck query can't hold the shared connection; `SET LOCAL` keeps the setting off pooled connections other clients use.
- **One small table:** one row per `(puzzle, device_id)`, the first result wins (`ON CONFLICT DO NOTHING`), and a finish sent again shows the first score. It holds solved or quit, the score the server computed, guesses, seconds, and clues and hints used. The device ID is a random UUID the browser makes, never anything personal.
- **Only plays on the puzzle's own UTC day are stored.** A past puzzle is compared against its day's players but isn't added to them.
- **Never fatal:** a database error during a guess or quit is logged and the play still succeeds.
- **Portable SQL:** the same statements run on SQLite, which the tests use in memory and a local run can use as a file (`sqlite:///path`). No Postgres is needed to develop or test.
- **The maths is in Python:** the day's rows are fetched and summarised (ties count half; no percentage below 10 players).

## Alternatives considered

- **SQLite on the backend's disk.** Not durable on the free host.
- **Counting in SQL.** Faster for large days, but summarising in Python keeps the SQL portable and is fine for thousands of rows a day. Worth moving into SQL if the table grows.

## Consequences

- The first request after Neon has paused is about a second slower.
- Results are only as honest as the stats the browser reports, and anyone who knows the day's answer could post results under made-up device IDs. The comparison is a fun statistic, not a leaderboard.
- A play finished just after midnight UTC isn't counted for its day.
- Adding a real leaderboard later would need trustworthy scores and probably accounts, which this design deliberately avoids.
