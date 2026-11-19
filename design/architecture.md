# Architecture

How Word Hunt fits together today. For *why* it's built this way, see the [decision records](adr/).

## Overview

The project has three parts: an offline data pipeline, a small stateless API, and a static frontend.

```
Offline:  concreteness ratings ──► build_word_lists.py ──► guess_words.txt, target_words.txt,
                                                            hint_words.txt, word_forms.txt,
                                                            irregular_plurals.txt
          guess_words.txt + GloVe 300d ──► extract_embeddings.py ──► embeddings.npz
          target_words.txt + key ──► build_schedule.py ──► daily_schedule.txt (hashed)
          answers + WordNet + Ollama ──► generate_clues.py ──► clues.json (keyed by hash)

Runtime:  data/ ──► FastAPI backend (Render) ◄── REST ──► browser frontend (GitHub Pages)
                          │
                          └──► results table (Neon Postgres, optional)
```

Everything the server reads at runtime is committed in `data/`. The pipeline's inputs (GloVe, the ratings CSV, WordNet, Ollama) are only needed to rebuild it; see [the data pipeline](data-pipeline.md).

## Backend

- **Startup** (`backend/api.py`): loads the embeddings, word forms and hint words into the `WordGameEngine`, decodes the schedule and the clues with the schedule key, and opens (but doesn't connect) the results store. That's about 115 MB of memory. If the key or the schedule is missing, the server still starts, and `/health` reports `degraded` with a 503.
- **Ranking** (`backend/game.py`): for an answer, one matrix product of the unit-length vectors against the answer's vector gives every guess word's similarity, and a sort gives its rank. The answer is rank 1. Rankings are cached for the last few answers, behind a lock.
- **Daily schedule** (`backend/daily.py`): puzzle #N is line N of `data/daily_schedule.txt`, and puzzle #1 is `LAUNCH_DATE` in `backend/config.py`. Each line is an HMAC of the word. Puzzles after today's are refused with 404.
- **Requests carry their own context.** Every request names a puzzle number, and scoring requests carry the player's stats. The server keeps no player state.
- **Guesses** (`backend/actions/`, `backend/utils/word_forms.py`): a guess is lowercased, a plural, verb form, comparative or British spelling is mapped to its base word, and anything not in the guess list (including every proper noun) is rejected.
- **Help** (`backend/routes/help.py`, `backend/actions/hint.py`): `/clue` returns the next written clue, and `/hint` returns an everyday word ranked #6–10 (first hint) or #2–5 (second), always better than the player's best. It never reveals a form of the answer and avoids words on its stem ("stimulate" for "stimulus") unless nothing else is in range.
- **Scoring** (`backend/scoring.py`): every rule and number is in one constants block at the top of the module.
- **Results** (`backend/results.py`): an optional store, on Postgres or SQLite, with one row per device per puzzle. It connects on first use. See [ADR 0007](adr/0007-optional-lazily-connected-results-store.md).
- **Routes:** one router per endpoint group in `backend/routes/`, with the request and response models in `backend/schemas.py`. See the [API reference](api.md).

## Frontend

Plain HTML, CSS and JavaScript ES modules in `docs/`, with no build step:

- `docs/js/config.js`: the backend's URL.
- `docs/js/api.js`: calls to the API, with a timeout long enough for the free server to wake up.
- `docs/js/storage.js`: progress, streaks and the device ID in `localStorage`, including migrations of old saves.
- `docs/js/ui.js`: rendering, startup retries, the help-unlock rules and a display copy of the help costs.
- `docs/js/main.js`: wiring and startup.

## Project structure

```
word-hunt/
├── backend/
│   ├── api.py            FastAPI app, startup and CORS
│   ├── game.py           WordGameEngine: loads data, ranks words against an answer
│   ├── daily.py          Daily schedule: puzzle numbers, dates, decoding answers
│   ├── scoring.py        Final score rules
│   ├── results.py        Results store (Postgres or SQLite) and the day's comparison
│   ├── config.py         File paths, launch date, schedule key, CORS origins
│   ├── schemas.py        Pydantic request and response models
│   ├── dependencies.py   Shared request helpers (engine, schedule, saving results)
│   ├── routes/           One router per endpoint group
│   ├── actions/          Guess and hint logic
│   ├── utils/            File loaders, plural and verb-form rules, temperature labels
│   ├── scripts/          Offline data pipeline
│   └── tests/            API, engine, scoring, results and word-list tests
├── data/
│   ├── guess_words.txt      Words you can guess
│   ├── target_words.txt     Possible answers
│   ├── hint_words.txt       Everyday words a Hint may reveal
│   ├── word_forms.txt       Plurals, verb forms, comparatives and British spellings, mapped to base words
│   ├── irregular_plurals.txt Irregular plurals ("larvae"), so they win when the singular is the answer
│   ├── embeddings.npz       GloVe vectors for every guess word
│   ├── daily_schedule.txt   Which answer on which day (hashed)
│   ├── clues.json           Written clues per answer (keyed by schedule code, once generated)
│   ├── target_blocklist.txt Words that are never the answer (hand-edited)
│   └── proper_nouns.txt     Extra proper nouns to exclude (hand-edited)
├── design/               Architecture, API and pipeline docs, and the decision records
├── docs/                 Frontend, served by GitHub Pages
├── .github/workflows/    CI: tests, ruff and node --check on every push
├── build.sh, start.sh    Render build and start commands
└── requirements*.txt     Server, dev and script dependencies
```
