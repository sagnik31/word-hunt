# API reference

The backend is a FastAPI app. While it's running, full request and response schemas are at `/docs` (for example `http://localhost:8000/docs`).

## Endpoints

| Method | Endpoint        | Description |
| ------ | --------------- | ----------- |
| GET    | `/health`       | Reports whether the engine and the schedule loaded, and whether a results database is configured (`results`; not checked, so Neon can stay asleep). Returns 503 with `"status": "degraded"` when they didn't load, so Render's health check fails a broken deploy. |
| GET    | `/today`        | Today's puzzle number, the UTC date, the launch date and the seconds until the next puzzle. Every puzzle from 1 to today's is playable. |
| POST   | `/guess`        | Body: `{"puzzle": 7, "word": "...", "stats": {...}, "device_id": "..."}`. Returns rank, similarity, percentile and temperature label. `matched` holds the base word when a plural or verb form was scored as it (`mittens` → `mitten`). Includes the score on a correct guess, computed from `stats`; a correct guess on the puzzle's own day is stored as this device's result. |
| GET    | `/puzzle/{n}`   | `{"puzzle", "clue_total"}`: how many written clues puzzle `n` has (0 when none). |
| POST   | `/hint`         | Body: `{"puzzle": 7, "best_rank": 120, "hints_used": 0}`. Returns an everyday word ranked #6–10 (first hint) or #2–5 (second), always better than `best_rank`. 409 when no hint is left to give. |
| POST   | `/clue`         | Body: `{"puzzle": 7, "clues_used": 0}`. Returns the next written clue, `{"clue", "number", "total"}`. 404 if the puzzle has no clues, 409 when they're used up. |
| POST   | `/quit`         | Body: `{"puzzle": 7, "stats": {...}, "device_id": "..."}`. Reveals the answer and returns the partial score; a quit on the puzzle's own day is stored. |
| GET    | `/results/{n}`  | Query: `device_id`, `score`. How a finished play compares with puzzle `n`'s on-the-day players: `players`, `solvers`, `solve_rate` (%), `beat_percent` (ties count half; `null` below `min_players`, 10), `counted` (this device's result is one of them, and is then used instead of `score`) and `buckets`, the guess-count chart for solvers. 503 when results are off. |

## Common fields and errors

- **`stats`** is the player's progress on that puzzle:
  - `elapsed_seconds`: since Play was pressed;
  - `guess_count`: different words validly guessed before this request (a repeat doesn't count);
  - `clue_count` and `hint_count`;
  - `best_rank`.
- **`device_id`** is optional: the browser's random ID, so results count once per device. One that doesn't look like an ID (8–64 letters, digits and dashes) is ignored, never refused.
- **404:** a puzzle that hasn't been released yet.
- **422:** values a browser can't send: a non-finite clock or one over ten years, counts over 100,000, a word over 100 characters. The error doesn't echo the input.
