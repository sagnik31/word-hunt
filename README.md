# Word Hunt

A word-guessing game where the only clue is meaning. The server picks a secret noun; you guess words and are told how semantically close each guess is, measured by cosine similarity between GloVe word embeddings. Each guess is ranked against the full vocabulary, so you can feel your way from "Freezing" to "Boiling" until you land on the answer.

**Play it:** [sagnik31.github.io/word-hunt](https://sagnik31.github.io/word-hunt/)

The backend runs on Render's free tier and sleeps when idle, so the first request after a quiet period can take up to a minute.

## How to play

1. Guess any common noun. The game shows its rank among all ~2,300 words in the vocabulary (the answer is rank 1), its similarity score, and a temperature label.
2. Use the ranks to steer toward the answer. A guess of `ocean` that ranks #4 means you are very close; one that ranks #1,800 means you should change direction.
3. If you get stuck, **Hint** or **Similar Word** reveals a word ranked closer than your best guess so far. Each use costs points.
4. **Quit** at any time to reveal the answer and receive partial credit.

Temperature labels are based on the guess's percentile rank:

| Label    | Percentile |
| -------- | ---------- |
| Boiling  | top 1%     |
| Very hot | top 5%     |
| Hot      | top 10%    |
| Warm     | top 25%    |
| Cool     | top 50%    |
| Cold     | top 75%    |
| Freezing | the rest   |

### Scoring

A correct guess is worth 100 points, minus:

- **Time:** nothing for the first 10 seconds, then a penalty that grows gently, steepens between 30 and 120 seconds, and is capped at 60 points. The clock starts on your first action, not when the word is picked.
- **Help:** 10 points for each Hint or Similar Word.

Quitting scores half of the best percentile you reached, minus the same help penalty. Scores never go below zero. The rules live in [`backend/scoring.py`](backend/scoring.py).

## How it works

The project is split into an offline data pipeline, a small API, and a static frontend.

```
Offline:  common_nouns.txt + GloVe 300d  ──►  embeddings.npz  ──►  similarity.txt

Runtime:  similarity.txt  ──►  FastAPI backend (Render)  ◄── REST ──►  Browser frontend (GitHub Pages)
```

**Offline pipeline.** Scripts in [`backend/scripts/`](backend/scripts/) look up a 300-dimensional GloVe vector for each word in the vocabulary, then compute the cosine similarity of every word against every other word and write the fully sorted neighbour list for each word to `data/similarity.txt`.

**Backend.** At startup, the game engine scans `similarity.txt` once and records the byte offset of each line. When a round starts, it seeks to the target word's line and loads only that ranking. A guess is then a dictionary lookup, so the server needs no NumPy, no model, no GPU, and no database. It fits comfortably on a free hosting tier.

**Frontend.** Plain HTML, CSS and JavaScript ES modules with no build step, served from [`docs/`](docs/) by GitHub Pages. It talks to the backend over a small REST API.

### Tech stack

| Layer    | Technology                                         |
| -------- | -------------------------------------------------- |
| Backend  | Python, FastAPI, Uvicorn, Pydantic                 |
| Frontend | HTML, CSS, vanilla JavaScript (ES modules)         |
| Data     | GloVe 6B 300d embeddings, NumPy (offline only)     |
| Testing  | pytest, HTTPX (via FastAPI's `TestClient`)         |
| Hosting  | Render (API), GitHub Pages (frontend)              |

## Running locally

### Prerequisites

- Python 3.10 or newer (developed on 3.13)
- Git

The precomputed data files are committed to the repository, so you do not need the GloVe embeddings to run the game. Note that `data/similarity.txt` is about 90 MB, which makes the clone fairly large.

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

### 2. Start the backend

From the repository root:

```bash
uvicorn backend.api:app --reload --port 8000
```

The API is now at `http://localhost:8000`, with interactive documentation at `http://localhost:8000/docs`. On Windows, `run_backend.bat` does the same thing using the `.venv` environment.

### 3. Point the frontend at your local backend

[`docs/js/config.js`](docs/js/config.js) points at the deployed backend by default. Change it to your local server:

```js
export const CONFIG = {
    API_BASE_URL: "http://localhost:8000"
};
```

### 4. Serve the frontend

ES modules cannot be loaded from `file://` URLs, so serve the `docs/` folder over HTTP. In a second terminal:

```bash
python -m http.server 8080 -d docs
```

Open [http://localhost:8080](http://localhost:8080) and start guessing.

If you serve the frontend from a different port, add its origin to `CORS_ORIGINS` in [`backend/config.py`](backend/config.py). Ports 8000, 8080 and 5500 (VS Code Live Server) are already allowed.

### Running the tests

From the repository root:

```bash
python -m pytest
```

Use `python -m pytest` rather than plain `pytest`; the former puts the repository root on the import path so the `backend` package can be found.

## API

| Method | Endpoint        | Description                                                         |
| ------ | --------------- | ------------------------------------------------------------------- |
| GET    | `/health`       | Reports whether the game engine loaded successfully.                |
| POST   | `/guess`        | Body: `{"word": "..."}`. Returns rank, similarity, percentile and temperature label; includes the score and starts a new round on a correct guess. |
| POST   | `/hint`         | Returns a word ranked closer than the player's best so far.         |
| POST   | `/similar_word` | Same as `/hint`, tracked separately for scoring and hint strength.  |
| POST   | `/quit`         | Reveals the answer, returns the partial score, and starts a new round. |

Full request and response schemas are available at `/docs` while the server is running.

## Rebuilding the data

You only need this if you change the vocabulary. It requires the extra script dependencies and the GloVe 6B 300d vectors (about 1 GB, not committed), available from the [Stanford GloVe project](https://nlp.stanford.edu/projects/glove/).

```bash
pip install -r requirements-scripts.txt
```

Place `glove.6B.300d.txt` in `data/`, then run from the repository root:

```bash
python backend/scripts/extract_embeddings.py
python backend/scripts/build_similarity.py
```

The first script writes `data/embeddings.npz` and lists any words without a GloVe vector in `data/missing.txt`. The second writes `data/similarity.txt`.

Two further scripts support planned features and are not used by the game yet:

- `build_vocabulary.py` generates the 20,000-noun candidate list in `words_20k.txt`. It needs `python -m spacy download en_core_web_sm` first.
- `generate_big_hints.py` writes riddle-style hints to `data/big_hints.json` using a locally running Ollama model.

## Project structure

```
word-hunt/
├── backend/
│   ├── api.py            FastAPI app, startup and CORS
│   ├── game.py           WordGameEngine: target selection and round state
│   ├── scoring.py        Final score rules
│   ├── config.py         File paths and allowed CORS origins
│   ├── schemas.py        Pydantic request and response models
│   ├── routes/           One router per endpoint
│   ├── actions/          Guess and hint logic
│   ├── utils/            File loaders, percentile and temperature labels
│   ├── scripts/          Offline data pipeline
│   └── tests/            API and engine tests
├── data/
│   ├── common_nouns.txt  Vocabulary
│   ├── embeddings.npz    GloVe vectors for the vocabulary
│   └── similarity.txt    Sorted neighbour list for every word
├── docs/                 Frontend, served by GitHub Pages
├── build.sh, start.sh    Render build and start commands
└── requirements*.txt     Server, dev and script dependencies
```

## Deployment

**Backend (Render).** Create a web service from the repository with build command `bash build.sh` and start command `bash start.sh`. These install `requirements.txt` and run Uvicorn on the port Render provides.

**Frontend (GitHub Pages).** In the repository settings, under Pages, deploy from the `main` branch and the `/docs` folder. Set `API_BASE_URL` in `docs/js/config.js` to the Render service URL, and make sure the Pages origin is listed in `CORS_ORIGINS` in `backend/config.py`.

## Limitations and roadmap

- **One game per server.** The backend holds a single game in memory, so everyone connected plays the same word and shares the same counters. Per-player sessions are the next structural change.
- **Vocabulary quality.** The current list contains some proper nouns and a few split two-word entries. Separate lists are planned: a small curated set of target words and a much broader set of accepted guesses. A 20,000-noun candidate list is already in `words_20k.txt`.
- **Riddle hints.** LLM-generated riddle hints exist for 100 words but are not wired into the game yet.
- **Under consideration:** leaderboards, timed and category-based modes, and UI polish.

## License

Released under the MIT License.
