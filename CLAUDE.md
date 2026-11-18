# CLAUDE.md

Guidance for coding agents (and people) working on this repository. Keep it short and current: it describes how the project works and the rules it depends on, not what's planned next.

## What this is

Word Hunt is a daily semantic guessing game. Each UTC day has one secret noun. Players guess words and see each guess's rank by GloVe cosine similarity against ~31,000 words, unlock clues and hints for points, and can quit for partial credit.

- `backend/`: FastAPI app (Python 3.10+, pinned on 3.13). It's stateless apart from an optional results table.
- `docs/`: the frontend, plain HTML/CSS/JS ES modules with no build step, served by GitHub Pages. **`docs/` is the website, not documentation.**
- `data/`: generated word lists, embeddings, the hashed schedule and clues. Committed, and read at startup.
- `backend/scripts/`: the offline pipeline that builds `data/`.
- `design/`: [architecture](design/architecture.md), [API](design/api.md), [data pipeline](design/data-pipeline.md), [development and deployment](design/development.md), and the decision records in [`design/adr/`](design/adr/). Read the relevant ADR before changing a design decision.

## Commands

Run everything from the repository root.

```bash
pip install -r requirements-dev.txt               # server + test deps
uvicorn backend.api:app --reload --port 8000      # run the API (docs at /docs)
python -m pytest                                  # tests (not bare `pytest`)
ruff check backend                                # lint
for f in docs/js/*.js; do node --check "$f"; done # frontend syntax, one file per call
```

All three checks must pass before a change is done. CI (`.github/workflows/checks.yml`) runs the same on every push. The pipeline scripts need `requirements-scripts.txt`, WordNet and inputs that aren't committed; see [the data pipeline](design/data-pipeline.md).

## Rules that must not break

Each of these is relied on by players or guarded by a test. Don't change one without the maintainer's agreement, and update the docs and the ADR if you do.

- **No proper nouns, anywhere:** not as guesses, answers, word forms, hint words or clues. Detection is in `build_word_lists.py`, plus `data/proper_nouns.txt`, and `backend/tests/test_word_lists.py` checks it.
- **A quit never beats a solve.** The best quit scores 20 and the worst solve 25. `backend/scoring.py` asserts it, and a property test checks it.
- **All scoring numbers live in `backend/scoring.py`.** The help costs are copied in `docs/js/ui.js`, `docs/index.html` and `README.md`, and `test_frontend_copies.py` fails if they drift. Change them all together.
- **Ranks:** the answer is rank 1 and its nearest neighbour rank 2. Temperature labels are fixed rank bands.
- **Plurals and verb forms count as their base word,** and a plural of the answer wins. A hint never reveals a plural of the answer.
- **Repeat guesses don't count** towards the guess count or the help gates.
- **Past puzzles never change.** Don't change `LAUNCH_DATE` or delete or reorder `data/daily_schedule.txt`. `build_schedule.py` only appends and is safe to rerun.
- **The server keeps no per-player state.** Every request names its puzzle, and scoring uses the stats the browser sends. Unreleased puzzles return 404.
- **The results database is optional and never fatal.** Never connect at startup or from `/health`, and never let a database error fail a guess or quit.
- **`/hint` and `/clue` are POST.**

## Secrets and spoilers

- **Never reveal an answer** in committed files, logs, test fixtures that use the real schedule, or the README. Use example words that aren't in `data/target_words.txt`, and check with `grep -x word data/target_words.txt`.
- The schedule key (`WORDHUNT_SCHEDULE_KEY` or the git-ignored `schedule.key`) and `DATABASE_URL` are secrets. Never commit, print or log them.
- `data/raw/` is git-ignored because its reports name answers. Keep anything that names answers there.
- Never commit a localhost URL in `docs/js/config.js`. For local play, copy `docs/` elsewhere and edit the copy.

## Working locally without spoilers

- **Tests** swap in their own schedule (`DailySchedule([...], date)`) and an in-memory `SQLiteResultStore`, so they need no key or database. Follow `backend/tests/test_api.py` for new API tests.
- **Playing in a browser:** don't point a preview at the real schedule, because hints reveal neighbours of the answer. Write a throwaway schedule with `backend.daily.word_code(word, "some-test-key")` for words not in `target_words.txt`, and start the server with `WORDHUNT_SCHEDULE_KEY`, `WORDHUNT_SCHEDULE_PATH` and `WORDHUNT_CLUES_PATH` pointing at those throwaway files. Don't use `build_schedule.py --new-key` for this.
- **Results:** `DATABASE_URL=sqlite:///<path outside the repo>` turns them on without Postgres.

## Conventions

- **Python:** small modules, with tunable numbers as named constants at the top of the module (thresholds, costs, ranks). FastAPI routes go in `backend/routes/`, one router per endpoint group, and request and response models in `backend/schemas.py`. Validate request ranges in the schemas; a bad `device_id` is ignored, not refused.
- **Frontend:** no frameworks, bundlers or npm dependencies. Every module must load directly in the browser. Changes to the saved-progress format in `storage.js` need a migration for old saves.
- **Data:** never edit generated files in `data/` by hand. Edit the inputs (`target_blocklist.txt`, `proper_nouns.txt`, the script constants) and rerun the scripts. Compare word lists in Python, not with shell `sort`/`comm`, which disagree across platforms.
- **Tests:** add or update tests with every behaviour change. Prefer deleting dead code over keeping it around.
- **Docs:** update `README.md` (player-facing behaviour) or `design/` (internals) in the same change. A new major design decision gets a new numbered ADR in `design/adr/`, and a reversed one gets its status changed, not a rewrite.
- **Downloads:** large inputs (GloVe, the ratings CSV) go in `data/` or `data/raw/` and stay uncommitted.

## Personal notes

A git-ignored `CLAUDE.local.md` may hold one maintainer's own workflow preferences. It's not needed to work on the project.
