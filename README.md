# Word Hunt

A daily word-guessing game where the only clue is meaning. Every day at midnight UTC there's a new secret noun, the same for everyone; you guess words and are told how semantically close each guess is, measured by cosine similarity between GloVe word embeddings. Every guess is ranked against the full vocabulary of about 31,000 words, so you can feel your way from "Freezing" to "Boiling" until you land on the answer. The word lists come from the Brysbaert, Warriner & Kuperman (2014) concreteness ratings (see [How it works](#how-it-works)).

**Play it:** [sagnik31.github.io/word-hunt](https://sagnik31.github.io/word-hunt/)

The backend runs on Render's free tier and sleeps when idle, so the first request after a quiet period can take up to a minute.

## How to play

1. Press **Play** to start. The clock starts then and keeps running until you solve or quit, even if you close the page.
2. Guess any common English word: a noun, verb, adjective or anything else. The game shows its rank among all ~31,000 words (the answer is rank 1), its similarity score, and a temperature label.
3. Use the ranks to steer toward the answer. A guess that ranks #4 means you are very close; one that ranks #20,000 means you should change direction.
4. Plurals and verb forms count as their base word: `cats` is scored as `cat`, and `baked` as `bake`. If the answer is `dog`, guessing `dogs` wins.
5. Proper nouns are never accepted: no names, places, brands, days or months.
6. Stuck? Help comes in two kinds, and unlocks in this order: Clue 1, 2 and 3, then Hint 1 and 2.
   - **Clues** are written clues, from a broad category ("A kind of home appliance") to close to a definition.
   - **Hints** reveal a real word near the answer: Hint 1 a word ranked #6–10, Hint 2 one ranked #2–5. The word is always closer than your best guess, so with a best of #2 there's no hint left to give. Hints only reveal everyday words, not rare or inflected ones.
   - The first help unlocks after 10 guesses, and each one needs 5 guesses in a row, since the last help, without a new best rank. The buttons show how many more guesses that takes. A puzzle without clues goes straight to Hints, with the same gates.
7. **Quit** at any time to reveal the answer and receive partial credit.
8. Solve each day's puzzle on its day to build a **streak**. **Past puzzles** lists every earlier day; you can play any of them, but they don't count towards your streak.
9. When you finish, you see how you did against the day's other players: "You beat 62% of today's players" (by score, ties counting half), the day's solve rate, and a chart of how many guesses solvers took, with your bar highlighted. Only plays finished on the puzzle's own day count. A past puzzle shows how you'd have done against that day's players but isn't added to them. Until about 10 people have played, it says "Only N players so far" instead of a percentage.

Your progress (guesses, help used, results and streak) is saved in your browser, so you can close the tab and pick up where you left off. It doesn't follow you to another browser or device.

For the day's comparison, the server stores one result per browser per puzzle: solved or quit, score, guesses, time, and clues and hints used. Your browser is identified only by a random ID it makes up and keeps in `localStorage`. There are no accounts, and nothing personal is stored.

The answer is always an everyday, picturable noun such as `toothpaste`, `magnet` or `yogurt`, drawn from a curated list of about 2,500 words.

Temperature labels are based on the guess's rank (the answer is rank 1):

| Label    | Rank       |
| -------- | ---------- |
| Boiling  | 2–10       |
| Very hot | 11–30      |
| Hot      | 31–100     |
| Warm     | 101–300    |
| Cool     | 301–600    |
| Cold     | 601–1,000  |
| Freezing | the rest   |

### Scoring

A solve is worth 100 points, minus:

- **Time:** nothing for the first 2 minutes, then `30 × (1 − e^(−(t − 2) / 12))` for `t` minutes: about 2 points at 3 minutes, 7 at 5, 15 at 10, 23 at 20 and 30 at the most. The clock starts when you press Play.
- **Clues:** 5, 10 and 15 points for the first, second and third.
- **Hints:** 20 and 25 points for the first and second, so each hint costs more than any clue.
- **Guesses:** 1 point for every 3 guesses beyond 15, up to 15 points (5 at 30 guesses, 10 at 45).

A solve never scores below 25.

**Quitting** reveals the answer. Its score is `0.2 × (100 − time − help − guesses) × closeness`, rounded, where closeness is 1 for a best guess ranked #2, 0.89 for #4, 0.74 for #10, 0.37 for #100 and 0 for #1,000 or worse (`1 − ln(best / 2) / ln(500)`). With no guesses it's 0. For example, quitting after 10 minutes with a best of #4 and one clue scores 0.2 × 80.4 × 0.89 ≈ 14.

A quit can score at most 20 and a solve at least 25, so **a player who quits never beats one who solved**, however much help the solver used. The rules and their numbers live at the top of [`backend/scoring.py`](backend/scoring.py).

## How it works

The project is split into an offline data pipeline, a small API, and a static frontend.

```
Offline:  concreteness ratings ──► build_word_lists.py ──► guess_words.txt, target_words.txt, word_forms.txt
          guess_words.txt + GloVe 300d ──► extract_embeddings.py ──► embeddings.npz

Runtime:  embeddings.npz + word lists ──► FastAPI backend (Render) ◄── REST ──► Browser frontend (GitHub Pages)
```

**Word lists.** Both the guess list and the answer list are built from one source: **Brysbaert, Warriner & Kuperman (2014), *Concreteness ratings for 40 thousand generally known English word lemmas*** ([original data on OSF](https://osf.io/kj76e/), [CSV mirror on Hugging Face](https://huggingface.co/datasets/StephanAkkerman/concreteness-ratings)). It lists about 40,000 English words, each with:

- **`Conc.M`:** how concrete people rated it, from 1 (abstract) to 5 (concrete).
- **`Percent_known`:** the share of raters who knew the word.
- **`SUBTLEX`:** how often it appears in film and TV subtitles.
- **`Dom_Pos`:** its usual part of speech.

The CSV isn't committed. To rebuild the lists, download it to `data/raw/concreteness_ratings.csv` (see [Rebuilding the data](#rebuilding-the-data)).

[`backend/scripts/build_word_lists.py`](backend/scripts/build_word_lists.py) builds four files from it:

- `data/guess_words.txt`: every single word in the dataset that has a GloVe vector and isn't a proper noun (about 31,000).
- `data/target_words.txt`: the possible answers. These are nouns known by at least 95% of people, with a concreteness rating of at least 4.0 out of 5 and a subtitle frequency of at least 50, minus plurals and the words in `data/target_blocklist.txt` (about 2,500).
- `data/hint_words.txt`: the guess words a Hint may reveal (about 16,700): known by at least 95% of people, with a subtitle frequency of at least 10, and not an inflected form of another word. That keeps out neighbours such as `skidded` or `marshy`.
- `data/word_forms.txt`: about 22,000 plurals and verb forms that aren't guess words themselves, each mapped to its base word (`cats` → `cat`). The rules live in [`backend/utils/word_forms.py`](backend/utils/word_forms.py).

A word counts as a proper noun when the WordNet dictionary only knows it with a capital letter (`Monday`, `Kleenex`), or when it's listed in `data/proper_nouns.txt`.

**Embeddings.** [`backend/scripts/extract_embeddings.py`](backend/scripts/extract_embeddings.py) looks up a 300-dimensional GloVe vector for every guess word, scales each to unit length, and saves them as float16 in `data/embeddings.npz` (about 18 MB).

**Daily schedule.** [`backend/scripts/build_schedule.py`](backend/scripts/build_schedule.py) shuffles the answers into `data/daily_schedule.txt`, where line N is puzzle #N and puzzle #1 is `LAUNCH_DATE` in [`backend/config.py`](backend/config.py). Each line is a keyed hash (HMAC) of the answer rather than the word, because the repository is public: without the schedule key, nobody can tell which word a line stands for. Rerunning the script never changes today's or earlier puzzles; it drops future words that are no longer answers and appends new ones, so no word repeats.

**Backend.** At startup, the game engine loads the embeddings and word forms once, and decodes the schedule with the key (about 115 MB of memory). The server keeps no player state: every request names a puzzle number, and the server refuses puzzles that haven't been released yet. Ranking every guess word against an answer takes a few milliseconds and is cached for recent answers. Scores are computed from the stats the browser sends (time since Play, guesses, clues and hints used, best rank).

**Results.** When `DATABASE_URL` is set, a winning guess or a quit that arrives on the puzzle's own UTC day is stored in Postgres ([Neon](https://neon.tech)'s free plan in production): one row per device ID per puzzle, and the first result wins. The score stored is the one the server computed. `GET /results/{n}` compares a finished play with that day's rows. The code is in [`backend/results.py`](backend/results.py). The tests use SQLite in memory with the same SQL, so they need no database. Without `DATABASE_URL`, the game works as before, `/results` returns 503 and the browser just doesn't show the comparison. The server never connects at startup, and `/health` never touches the database, so a paused or unreachable database can't stop it starting or keep Neon awake. Neon pauses after about 5 idle minutes and drops the connection; the next query reconnects, which makes the first request after a pause about a second slower.

**Frontend.** Plain HTML, CSS and JavaScript ES modules with no build step, served from [`docs/`](docs/) by GitHub Pages. It talks to the backend over a small REST API and keeps each player's progress in `localStorage`.

### Tech stack

| Layer    | Technology                                                     |
| -------- | -------------------------------------------------------------- |
| Backend  | Python, FastAPI, Uvicorn, Pydantic, NumPy, psycopg             |
| Frontend | HTML, CSS, vanilla JavaScript (ES modules)                     |
| Data     | GloVe 6B 300d embeddings, Brysbaert et al. concreteness ratings, NLTK WordNet (offline only) |
| Testing  | pytest, HTTPX (via FastAPI's `TestClient`)                     |
| Hosting  | Render (API), GitHub Pages (frontend), Neon Postgres (results) |

## Running locally

### Prerequisites

- Python 3.10 or newer (developed on 3.13)
- Git

The generated data files are committed to the repository, so you do not need GloVe or the ratings dataset to run the game. The git history still contains an old 90 MB data file (`data/similarity.txt`), which makes the clone fairly large.

### 1. Clone and install

```bash
git clone https://github.com/sagnik31/word-hunt.git
cd word-hunt
python -m venv .venv
```

Activate the virtual environment. On macOS or Linux:

```bash
source .venv/bin/activate
```

On Windows (PowerShell):

```powershell
.venv\Scripts\Activate.ps1
```

Then install the dependencies. `requirements-dev.txt` includes the server dependencies plus the test tools:

```bash
pip install -r requirements-dev.txt
```

### 2. Get a schedule key

The server needs the schedule key to read `data/daily_schedule.txt`. It reads the `WORDHUNT_SCHEDULE_KEY` environment variable, or a `schedule.key` file at the repository root (git-ignored).

Without the project's key, build your own schedule with a new key in a separate file:

```bash
WORDHUNT_SCHEDULE_PATH=data/my_schedule.txt python backend/scripts/build_schedule.py --new-key
```

Then start the server with the same `WORDHUNT_SCHEDULE_PATH` set.

### 3. Start the backend

From the repository root:

```bash
uvicorn backend.api:app --reload --port 8000
```

The API is now at `http://localhost:8000`, with interactive documentation at `http://localhost:8000/docs`. On Windows, `run_backend.bat` does the same thing using the `.venv` environment.

The results comparison is off unless `DATABASE_URL` is set. To try it locally without Postgres, point it at a SQLite file outside the repository, such as `DATABASE_URL=sqlite:///../results.db`. A Postgres URL (`postgresql://...`) works too, for example a separate Neon branch for testing.

### 4. Point the frontend at your local backend

[`docs/js/config.js`](docs/js/config.js) points at the deployed backend. Don't commit a localhost URL there. Instead, copy `docs/` to a scratch folder and change `API_BASE_URL` in the copy:

```js
export const CONFIG = {
    API_BASE_URL: "http://localhost:8000"
};
```

### 5. Serve the frontend

ES modules cannot be loaded from `file://` URLs, so serve the folder over HTTP. In a second terminal:

```bash
python -m http.server 8080 -d path/to/your/docs-copy
```

Open [http://localhost:8080](http://localhost:8080) and start guessing.

If you serve the frontend from a different port, add its origin to `CORS_ORIGINS` in [`backend/config.py`](backend/config.py). Ports 8000, 8080 and 5500 (VS Code Live Server) are already allowed.

### Running the tests

From the repository root:

```bash
python -m pytest
```

Use `python -m pytest` rather than plain `pytest`; the former puts the repository root on the import path so the `backend` package can be found. The tests also check the generated word lists, for example that no proper noun appears in them.

## API

| Method | Endpoint        | Description                                                         |
| ------ | --------------- | ------------------------------------------------------------------- |
| GET    | `/health`       | Reports whether the engine and the schedule loaded, and whether a results database is configured (`results`; not checked, so Neon can stay asleep). |
| GET    | `/today`        | Today's puzzle number, the UTC date, the launch date and the seconds until the next puzzle. Every puzzle from 1 to today's is playable. |
| POST   | `/guess`        | Body: `{"puzzle": 7, "word": "...", "stats": {...}, "device_id": "..."}`. Returns rank, similarity, percentile and temperature label. `matched` holds the base word when a plural or verb form was scored as it (`cats` → `cat`). Includes the score on a correct guess, computed from `stats`; a correct guess on the puzzle's own day is stored as this device's result. |
| GET    | `/puzzle/{n}`   | `{"puzzle", "clue_total"}`: how many written clues puzzle `n` has (0 when none). |
| POST   | `/hint`         | Body: `{"puzzle": 7, "best_rank": 120, "hints_used": 0}`. Returns an everyday word ranked #6–10 (first hint) or #2–5 (second), always better than `best_rank`. 409 when no hint is left to give. |
| POST   | `/clue`         | Body: `{"puzzle": 7, "clues_used": 0}`. Returns the next written clue, `{"clue", "number", "total"}`. 404 if the puzzle has no clues, 409 when they're used up. |
| POST   | `/quit`         | Body: `{"puzzle": 7, "stats": {...}, "device_id": "..."}`. Reveals the answer and returns the partial score; a quit on the puzzle's own day is stored. |
| GET    | `/results/{n}`  | Query: `device_id`, `score`. How a finished play compares with puzzle `n`'s on-the-day players: `players`, `solvers`, `solve_rate` (%), `beat_percent` (ties count half; `null` below `min_players`, 10), `counted` (this device's result is one of them, and is then used instead of `score`) and `buckets`, the guess-count chart for solvers. 503 when results are off. |

`stats` is the player's progress on that puzzle: `elapsed_seconds` since Play was pressed, `guess_count` (valid guesses before this request), `clue_count`, `hint_count` and `best_rank`. A puzzle that hasn't been released yet returns 404. `device_id` is optional: the browser's random ID, so results count once per device. One that doesn't look like an ID (8-64 letters, digits and dashes) is ignored, never refused.

Full request and response schemas are available at `/docs` while the server is running.

## Rebuilding the data

You only need this if you change the word lists, the filters or the blocklists. Install the script dependencies and WordNet:

```bash
pip install -r requirements-scripts.txt
```

```bash
python -m nltk.downloader wordnet
```

You also need two inputs that are not committed:

- `data/glove.6B.300d.txt`: GloVe 6B 300d vectors (about 1 GB), from the [Stanford GloVe project](https://nlp.stanford.edu/projects/glove/).
- `data/raw/concreteness_ratings.csv`: the concreteness ratings (1.6 MB), from the [Hugging Face mirror](https://huggingface.co/datasets/StephanAkkerman/concreteness-ratings).

Then run, from the repository root:

```bash
python backend/scripts/build_word_lists.py
```

```bash
python backend/scripts/extract_embeddings.py
```

The first script writes the three word-list files and prints how many words each filter removed. The second writes `data/embeddings.npz`.

To change which words can be the answer, edit `data/target_blocklist.txt` (one word per line), rerun the first script, then run `python backend/scripts/build_schedule.py` to update the future puzzles. To ban a proper noun that slipped through, add it to `data/proper_nouns.txt`. The filter thresholds are constants at the top of `build_word_lists.py`.

### Clues

`generate_clues.py` writes three clues per answer with a local [Ollama](https://ollama.com) model (`qwen3.5:4b`) and checks them with a second one (`gemma4:e2b`). Both need to be pulled first (`ollama pull qwen3.5:4b`, `ollama pull gemma4:e2b`).

```bash
python backend/scripts/generate_clues.py
```

The writer isn't asked to recall facts from memory. It gets one dictionary meaning from WordNet: of the word's senses, the one closest to the word's 25 nearest neighbours in the game's embeddings. That way the clues describe the same meaning the hot-and-cold ranks are built on (`washer` the machine, not the person or the seal). The most common sense wins unless another is clearly closer, and senses that are names, or whose definitions contain one, are skipped.

The vague clue comes straight from WordNet rather than the model: it's the meaning's broader category, such as "A kind of home appliance." That's always true and always broad. Categories that cover too few things, are too abstract ("A kind of object"), or aren't everyday words (checked against the concreteness ratings, so `data/raw/concreteness_ratings.csv` is needed) are skipped. About 97% of the answers get one; for the rest the model writes the vague clue too. The writer fills in the meaning in its own words and the strong clue first, then the medium clue, which should restate a detail the dictionary meaning gives rather than add new facts.

Each clue set has to pass three checks:

- **Rules:** no answer word or a word built from it, nothing about letters, spelling or sounds, no names.
- **Facts:** the second model, also given the meaning, checks the model-written clues for errors, the medium one against the meaning itself. It catches only some of the subtly wrong clues, so some get through.
- **Solver:** the second model guesses the word from the clues, one more clue at a time, and its guesses are ranked like a player's. The strongest clue has to bring it into the top 10, and none of its three guesses from the vague clue alone may be the answer. If a WordNet category gives the word away, the next broader one is tried.

When a set fails, the writer is told exactly what went wrong (which rule, which clue was judged wrong and why, what the solver guessed) and asked to fix it, up to 4 tries in all (`--attempts`).

In a 30-word pilot, 26 words passed, all about the right meaning. About a quarter of the passing sets still had a doubtful detail, mostly in the medium clue (half did before the medium clue was tied to the dictionary meaning). Skim the report before using the clues.

On a CPU it takes about 50 seconds per word, so the full list takes about a day and a half. Progress goes to `data/raw/clue_report.json` after every word (git-ignored, since it names the words), so you can stop and rerun it; `--redo-failed` retries the words that failed. At the end, the passing clues go to `data/clues.json`, keyed by the schedule codes so the public file doesn't say which clues belong to which word. That step needs the schedule key; `--export-only` redoes just that step. Puzzles without clues still work: the Clue button just says there are none.

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
│   ├── routes/           One router per endpoint
│   ├── actions/          Guess and hint logic
│   ├── utils/            File loaders, plural and verb-form rules, percentile labels
│   ├── scripts/          Offline data pipeline
│   └── tests/            API, engine and word-list tests
├── data/
│   ├── guess_words.txt      Words you can guess
│   ├── target_words.txt     Possible answers
│   ├── daily_schedule.txt   Which answer on which day (hashed)
│   ├── word_forms.txt       Plurals and verb forms, mapped to base words
│   ├── hint_words.txt       Everyday words a Hint may reveal
│   ├── embeddings.npz       GloVe vectors for every guess word
│   ├── target_blocklist.txt Words that are never the answer (hand-edited)
│   ├── proper_nouns.txt     Extra proper nouns to exclude (hand-edited)
│   └── clues.json           Written clues per answer (keyed by schedule code)
├── docs/                 Frontend, served by GitHub Pages
├── build.sh, start.sh    Render build and start commands
└── requirements*.txt     Server, dev and script dependencies
```

## Deployment

**Backend (Render).** Create a web service from the repository with build command `bash build.sh` and start command `bash start.sh`. These install `requirements.txt` and run Uvicorn on the port Render provides. Set the `WORDHUNT_SCHEDULE_KEY` environment variable to the schedule key; without it the server starts but `/health` reports `degraded`.

For the results comparison, create a Neon project (the free plan is enough) and set `DATABASE_URL` on Render to its **pooled** connection string (`postgresql://...-pooler.../...?sslmode=require`). Never commit it. The `results` table is created on the first query. Without `DATABASE_URL`, everything else works and the comparison isn't shown.

**Frontend (GitHub Pages).** In the repository settings, under Pages, deploy from the `main` branch and the `/docs` folder. Set `API_BASE_URL` in `docs/js/config.js` to the Render service URL, and make sure the Pages origin is listed in `CORS_ORIGINS` in `backend/config.py`.

## Data sources

- **GloVe:** Pennington, Socher & Manning (2014), *GloVe: Global Vectors for Word Representation*. The 6B 300d vectors.
- **Concreteness ratings:** Brysbaert, Warriner & Kuperman (2014), *Concreteness ratings for 40 thousand generally known English word lemmas*, Behavior Research Methods 46(3), 904–911, doi:10.3758/s13428-013-0403-5. The original data is at [osf.io/kj76e](https://osf.io/kj76e/); the game uses the [Hugging Face mirror](https://huggingface.co/datasets/StephanAkkerman/concreteness-ratings).
- **WordNet:** Princeton University, via NLTK. Used to detect proper nouns and to give the clue writer each word's meaning.

## Limitations and roadmap

- **Progress lives in the browser.** Clearing site data resets streaks, and progress doesn't sync between devices.
- **Scores trust the browser.** The score uses the time, guess and help counts the browser reports, so a determined player could fake them, and anyone who knows the day's answer could post results under made-up device IDs. That skews "you beat X%" but nothing else. It would matter more for a leaderboard.
- **Midnight edge:** a play counts only if its solve or quit reaches the server on the puzzle's own UTC day, so one finished just after midnight isn't counted.
- **Clues come from small local models.** The automatic checks catch too-easy and off-meaning clues, but only about half of the subtly wrong ones, so the clues need a human skim. Some answers have no clues.
- **Under consideration:** leaderboards, timed and category-based modes, and UI polish.

## License

Released under the MIT License. See [LICENSE](LICENSE).
