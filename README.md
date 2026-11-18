# Word Hunt

A daily word-guessing game where the only clue is meaning. Every day at midnight UTC there's a new secret noun, the same for everyone. You guess words, and each guess is ranked by how close it is in meaning to the answer, out of about 31,000 words, using GloVe word embeddings. You feel your way from "Freezing" to "Boiling" until you land on it.

**Play it:** [sagnik31.github.io/word-hunt](https://sagnik31.github.io/word-hunt/)

The backend runs on a free tier and sleeps when idle, so the first visit after a quiet period can take up to a minute while it wakes up.

## How to play

- Press **Play** to start the clock, then guess any common English word. Each guess shows its rank (the answer is #1) and a temperature, from Boiling (#2–10) down to Freezing (worse than #1,000).
- Plurals and verb forms count as their base word, and repeats don't count as new guesses. Proper nouns (names, places, brands, days, months) are never accepted.
- Stuck? Unlock up to three written **Clues**, from a broad category to close to a definition, then two **Hints**, which reveal a real word near the answer. The first help unlocks after 10 guesses, and each one after that needs 5 guesses in a row without a new best.
- **Quit** at any time to reveal the answer for partial credit.
- Solve each day's puzzle on its day to build a **streak**, and play earlier days from **Past puzzles**.
- When you finish, you see how you did against the day's other players.

**Scoring.** A solve is worth 100 points, minus a time penalty (none for the first 2 minutes, at most 30), 5, 10 and 15 points for the three clues, 20 and 25 points for the two hints, and a little for using many guesses. A solve never scores below 25, and a quit at most 20, so **a player who quits never beats one who solved**. The exact rules are at the top of [`backend/scoring.py`](backend/scoring.py).

**Privacy.** Your progress is saved only in your browser. For the day's comparison, the server stores one result per browser per puzzle, identified by a random ID your browser makes up. There are no accounts, and nothing personal is stored.

## How it's built

```
Offline:  concreteness ratings + GloVe + WordNet ──► word lists, embeddings, hashed schedule, clues (data/)
Runtime:  data/ ──► FastAPI backend (Render) ◄── REST ──► static frontend (GitHub Pages)
                          └──► results (Neon Postgres, optional)
```

| Layer    | Technology |
| -------- | ---------- |
| Backend  | Python, FastAPI, NumPy, psycopg |
| Frontend | HTML, CSS, vanilla JavaScript (ES modules), no build step |
| Data     | GloVe 6B 300d, Brysbaert et al. concreteness ratings, WordNet (offline only), local Ollama models for clues |
| Hosting  | Render (API), GitHub Pages (frontend), Neon Postgres (results) |

## Quick start

Requires Python 3.10+ (pinned on 3.13). The generated data is committed, so no large downloads are needed.

```bash
git clone https://github.com/sagnik31/word-hunt.git
cd word-hunt
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# The real schedule needs the project's secret key, so make your own:
export WORDHUNT_SCHEDULE_PATH=data/my_schedule.txt   # PowerShell: $env:WORDHUNT_SCHEDULE_PATH = "data/my_schedule.txt"
python backend/scripts/build_schedule.py --new-key

uvicorn backend.api:app --reload --port 8000   # API docs at http://localhost:8000/docs
python -m pytest                               # tests
```

To play locally, serve a copy of `docs/` pointed at your backend; see [Development and deployment](design/development.md).

## Documentation

- [Architecture](design/architecture.md): how the pieces fit together, and the project structure
- [API reference](design/api.md): endpoints, request fields and errors
- [Data pipeline](design/data-pipeline.md): rebuilding the word lists, embeddings, schedule and clues
- [Development and deployment](design/development.md): running everything locally, the checks, and deploying
- [CLAUDE.md](CLAUDE.md): working notes for coding agents and contributors

**Design decisions** (why it's built this way, and the trade-offs):

1. [Static GloVe embeddings, ranked on the fly](design/adr/0001-glove-embeddings-ranked-on-the-fly.md)
2. [Every word list from one concreteness dataset, with no proper nouns](design/adr/0002-word-lists-from-concreteness-ratings.md)
3. [A secret schedule in a public repository, with HMAC codes](design/adr/0003-hmac-hashed-schedule-in-a-public-repo.md)
4. [A stateless server, with progress in the browser](design/adr/0004-stateless-server-progress-in-the-browser.md)
5. [One scoring module, where a quit never beats a solve](design/adr/0005-scoring-a-quit-never-beats-a-solve.md)
6. [Clues from small local models, grounded in WordNet](design/adr/0006-clues-from-local-models-grounded-in-wordnet.md)
7. [An optional, lazily connected results database](design/adr/0007-optional-lazily-connected-results-store.md)
8. [A no-build static frontend and free-tier hosting](design/adr/0008-static-frontend-and-free-tier-hosting.md)

## Limitations

- Progress lives in the browser, so it doesn't sync between devices, and clearing site data resets the streak.
- Scores use the stats the browser reports, so a determined player could fake them. That skews only the "you beat X%" comparison.
- A play counts towards its day only if it finishes before midnight UTC.
- Clues come from small local models and need a human skim. Some answers have none.
- Under consideration: leaderboards, timed and category-based modes, and UI polish.

## Data sources

- **GloVe:** Pennington, Socher & Manning (2014), *GloVe: Global Vectors for Word Representation*. The 6B 300d vectors.
- **Concreteness ratings:** Brysbaert, Warriner & Kuperman (2014), *Concreteness ratings for 40 thousand generally known English word lemmas*, Behavior Research Methods 46(3), 904–911, doi:10.3758/s13428-013-0403-5. Original data at [osf.io/kj76e](https://osf.io/kj76e/); the game uses the [Hugging Face mirror](https://huggingface.co/datasets/StephanAkkerman/concreteness-ratings).
- **WordNet:** Princeton University, via NLTK. Used to detect proper nouns and to give the clue writer each word's meaning.

## License

Released under the MIT License. See [LICENSE](LICENSE).
