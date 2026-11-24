# Development and deployment

The README's quick start gets the backend running. This page has the rest: playing the full game locally, results, tests and deploying.

## Prerequisites

- Python 3.11 or newer (developed and pinned on 3.13)
- Git, and Node.js 22 or newer for the frontend tests and syntax check

The generated data files are committed, so you don't need GloVe or the ratings dataset to run the game. The git history still contains an old 90 MB data file, which makes the clone fairly large.

## Backend

```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn backend.api:app --reload --port 8000
```

The API is then at `http://localhost:8000`, with interactive docs at `/docs`. On Windows, `run_backend.bat` does the same using `.venv`.

**The schedule key.** The server needs it to read `data/daily_schedule.txt`, from the `WORDHUNT_SCHEDULE_KEY` environment variable or a git-ignored `schedule.key` at the repository root. Without the project's key, build your own schedule in a separate file and start the server with the same path:

```bash
WORDHUNT_SCHEDULE_PATH=data/my_schedule.txt python backend/scripts/build_schedule.py --new-key
WORDHUNT_SCHEDULE_PATH=data/my_schedule.txt uvicorn backend.api:app --reload --port 8000
```

`WORDHUNT_CLUES_PATH` does the same for the clues file. The committed clues are keyed with the project's key, so with your own key no puzzle has clues and the help goes straight to hints.

**Results locally.** The results comparison is off unless `DATABASE_URL` is set. To try it without Postgres, point it at a SQLite file outside the repository, such as `DATABASE_URL=sqlite:///../results.db`. A Postgres URL (`postgresql://...`) works too, for example a separate Neon branch for testing.

## Frontend

[`docs/js/config.js`](../docs/js/config.js) points at the deployed backend. **Don't commit a localhost URL there.** Instead, copy `docs/` to a scratch folder and change `API_BASE_URL` in the copy:

```js
export const CONFIG = {
    API_BASE_URL: "http://localhost:8000"
};
```

The page's content security policy (the `<meta http-equiv="Content-Security-Policy">` tag in `index.html`) only lets it call the deployed backend, so in the copy also change `connect-src` to `http://localhost:8000`. Otherwise the browser blocks every call and the console shows a CSP error. A test checks that the committed `connect-src` matches `config.js`.

ES modules can't be loaded from `file://` URLs, so serve the copy over HTTP:

```bash
python -m http.server 8080 -d path/to/your/docs-copy
```

Then open `http://localhost:8080`. Ports 8000, 8080 and 5500 (VS Code Live Server) are allowed by CORS. For another port, add its origin to `CORS_ORIGINS` in [`backend/config.py`](../backend/config.py).

## Checks

From the repository root:

```bash
python -m pytest
ruff check backend
for f in docs/js/*.js; do node --check "$f"; done
```

- Use `python -m pytest` rather than `pytest`, so the repository root is on the import path.
- The tests build their own schedule and use an in-memory SQLite results store, so they need neither the key nor a database. They also check the generated word lists (for example, that no proper noun appears, hint words included), that the shipped `data/clues.json` is complete and shares no code with the schedule (checked without the key, reporting counts only so a failure never prints a clue), and that the help costs shown in the frontend and the README match `backend/scoring.py`. The saves and the request handling in `docs/js/` are tested by running `backend/tests/frontend.test.mjs` with Node (skipped without it). The clue-generator tests cover each clue rule: all three clues, no giveaway forms, no talk of letters or sounds, no names, and the length limit.
- pytest, httpx and ruff are pinned in `requirements-dev.txt`, so CI and a local run use the same versions.
- `node --check` checks only its first argument, so run it once per file.
- GitHub Actions runs the same three checks on every push to `main` and every pull request ([`.github/workflows/checks.yml`](../.github/workflows/checks.yml)). The clue-generator tests and the word-form name check are skipped there, because they need WordNet.

## Deployment

**Backend (Render).**

1. Create a web service from the repository with build command `bash build.sh` and start command `bash start.sh`. These install `requirements.txt` and run Uvicorn on the port Render provides.
2. Set `PYTHON_VERSION=3.13`, which the pins in `requirements.txt` were tested on.
3. Set `WORDHUNT_SCHEDULE_KEY` to the schedule key. Without it, or with a key that doesn't decode every schedule line, the server starts but `/health` reports `degraded` with a 503.
4. Set the health check path to `/health`. A deploy whose startup failed then fails its health check, and Render keeps the previous deploy running.

**Results (Neon).** Create a Neon project (the free plan is enough) and set `DATABASE_URL` on Render to its **pooled** connection string (`postgresql://...-pooler.../...?sslmode=require`). Never commit it. The `results` table is created on the first query. Without `DATABASE_URL`, everything else works and the comparison isn't shown.

**Frontend (GitHub Pages).** In the repository settings, under Pages, deploy from the `main` branch and the `/docs` folder. Set `API_BASE_URL` in `docs/js/config.js` to the Render service URL (and the same URL in the CSP's `connect-src` in `docs/index.html`), and make sure the Pages origin is listed in `CORS_ORIGINS` in `backend/config.py`.
