# ADR 0008: A no-build static frontend on GitHub Pages, and a small API on a free tier

- **Status:** Accepted
- **Date:** 2025-11-30 (frontend moved to `docs/`); data artifacts committed since 2026-11-08

## Context

Word Hunt is a hobby project with one maintainer and no budget. It needs a public page anyone can open, and an API that holds the secret schedule and the embeddings. Deploys should be simple enough to do by hand, and the repository should run for anyone who clones it, without heavyweight downloads.

## Decision

- **Frontend:** plain HTML, CSS and JavaScript ES modules in `docs/`, with no framework, bundler or build step. GitHub Pages serves the folder straight from `main`, so a push publishes it. The backend's URL is the one setting, in `docs/js/config.js`.
- **Backend:** a FastAPI app on Render's free web-service tier, started with `bash build.sh` and `bash start.sh`. The schedule key and the optional database URL are environment variables there. A `/health` endpoint returns 503 when startup failed, so the host keeps the previous deploy running.
- **Cross-origin calls:** the page and the API are on different origins, so the API allows the Pages origin (and a few localhost ports) through CORS. It doesn't allow credentials, because the game uses no cookies.
- **Committed data artifacts:** the word lists, the hashed schedule, the clues file (once generated) and the float16 embeddings (about 18 MB) are committed. Neither a deploy nor a local run needs GloVe, the ratings dataset or WordNet. Those are only needed to rebuild the data.
- **Pinned dependencies** in `requirements.txt` for the server, with separate files for development and for the offline scripts.
- **CI** on GitHub Actions runs the tests, `ruff` and a syntax check of each frontend file on every push.

## Alternatives considered

- **A frontend framework with a build step.** The UI is a single page with a few panels, so a framework would add tooling and a build to deploy without much benefit.
- **Serving the frontend from the API.** One deploy instead of two, but every page load would wait for the free API to wake up, and the static page would no longer be free and always on.
- **Paid or always-on hosting.** It would remove cold starts, but it isn't worth the cost for a pet project.
- **Downloading data at deploy time.** It keeps the repo smaller, but deploys would depend on outside servers and take longer.

## Consequences

- The free API sleeps when idle, so the first request after a quiet period can take up to a minute. The page says it's waking the server and retries.
- GitHub Pages only serves the repository root or `docs/`, so `docs/` is reserved for the site. Project documentation lives elsewhere (`design/`).
- A localhost URL must never be committed in `docs/js/config.js`. Local runs use a copy of `docs/`.
- Values the frontend copies from the backend, such as the help costs, have to be kept in sync by hand, and a test checks them.
- The clone is fairly large, because an old 90 MB data file is still in git history.
