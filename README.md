# Word Hunt

A word-guessing game where the only clue is meaning. The server picks a secret noun; you guess words and are told how semantically close each guess is, measured by cosine similarity between GloVe word embeddings. Every guess is ranked against the full vocabulary of about 31,000 words, so you can feel your way from "Freezing" to "Boiling" until you land on the answer. The word lists come from the Brysbaert, Warriner & Kuperman (2014) concreteness ratings (see [How it works](#how-it-works)).

**Play it:** [sagnik31.github.io/word-hunt](https://sagnik31.github.io/word-hunt/)

The backend runs on Render's free tier and sleeps when idle, so the first request after a quiet period can take up to a minute.

## How to play

1. Guess any common English word: a noun, verb, adjective or anything else. The game shows its rank among all ~31,000 words (the answer is rank 1), its similarity score, and a temperature label.
2. Use the ranks to steer toward the answer. A guess that ranks #4 means you are very close; one that ranks #20,000 means you should change direction.
3. Plurals and verb forms count as their base word: `cats` is scored as `cat`, and `baked` as `bake`. If the answer is `dog`, guessing `dogs` wins.
4. Proper nouns are never accepted: no names, places, brands, days or months.
5. If you get stuck, **Hint** or **Similar Word** reveals a word ranked closer than your best guess so far. Each use costs points.
6. **Quit** at any time to reveal the answer and receive partial credit.

The answer is always an everyday, picturable noun such as `toothpaste`, `magnet` or `yogurt`, drawn from a curated list of about 2,700 words.

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

[`backend/scripts/build_word_lists.py`](backend/scripts/build_word_lists.py) builds three files from it:

- `data/guess_words.txt`: every single word in the dataset that has a GloVe vector and isn't a proper noun (about 31,000).
- `data/target_words.txt`: the possible answers. These are nouns known by at least 95% of people, with a concreteness rating of at least 4.0 out of 5 and a subtitle frequency of at least 50, minus plurals and the words in `data/target_blocklist.txt` (about 2,700).
- `data/word_forms.txt`: about 22,000 plurals and verb forms that aren't guess words themselves, each mapped to its base word (`cats` → `cat`). The rules live in [`backend/utils/word_forms.py`](backend/utils/word_forms.py).

A word counts as a proper noun when the WordNet dictionary only knows it with a capital letter (`Monday`, `Kleenex`), or when it's listed in `data/proper_nouns.txt`.

**Embeddings.** [`backend/scripts/extract_embeddings.py`](backend/scripts/extract_embeddings.py) looks up a 300-dimensional GloVe vector for every guess word, scales each to unit length, and saves them as float16 in `data/embeddings.npz` (about 18 MB).

**Backend.** At startup, the game engine loads the embeddings and word lists once (about 115 MB of memory). When a round starts, it picks an answer from the target list and ranks every guess word by cosine similarity to it, which takes a few milliseconds. A guess is then a dictionary lookup.

**Frontend.** Plain HTML, CSS and JavaScript ES modules with no build step, served from [`docs/`](docs/) by GitHub Pages. It talks to the backend over a small REST API.

### Tech stack

| Layer    | Technology                                                     |
| -------- | -------------------------------------------------------------- |
| Backend  | Python, FastAPI, Uvicorn, Pydantic, NumPy                      |
| Frontend | HTML, CSS, vanilla JavaScript (ES modules)                     |
| Data     | GloVe 6B 300d embeddings, Brysbaert et al. concreteness ratings, NLTK WordNet (offline only) |
| Testing  | pytest, HTTPX (via FastAPI's `TestClient`)                     |
| Hosting  | Render (API), GitHub Pages (frontend)                          |

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

### 2. Start the backend

From the repository root:

```bash
uvicorn backend.api:app --reload --port 8000
```

The API is now at `http://localhost:8000`, with interactive documentation at `http://localhost:8000/docs`. On Windows, `run_backend.bat` does the same thing using the `.venv` environment. The server prints the current answer at startup (`[startup] Target word set to: ...`), which is handy for testing.

### 3. Point the frontend at your local backend

[`docs/js/config.js`](docs/js/config.js) points at the deployed backend. Don't commit a localhost URL there. Instead, copy `docs/` to a scratch folder and change `API_BASE_URL` in the copy:

```js
export const CONFIG = {
    API_BASE_URL: "http://localhost:8000"
};
```

### 4. Serve the frontend

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
| GET    | `/health`       | Reports whether the game engine loaded successfully.                |
| POST   | `/guess`        | Body: `{"word": "..."}`. Returns rank, similarity, percentile and temperature label. `matched` holds the base word when a plural or verb form was scored as it (`cats` → `cat`). Includes the score and starts a new round on a correct guess. |
| POST   | `/hint`         | Returns a word ranked closer than the player's best so far.         |
| POST   | `/similar_word` | Same as `/hint`, tracked separately for scoring and hint strength.  |
| POST   | `/quit`         | Reveals the answer, returns the partial score, and starts a new round. |

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

To change which words can be the answer, edit `data/target_blocklist.txt` (one word per line) and rerun the first script. To ban a proper noun that slipped through, add it to `data/proper_nouns.txt`. The filter thresholds are constants at the top of `build_word_lists.py`.

`generate_big_hints.py` writes riddle-style hints for the first 100 target words to `data/big_hints.json`, using a locally running Ollama model. The game doesn't use these hints yet.

## Project structure

```
word-hunt/
├── backend/
│   ├── api.py            FastAPI app, startup and CORS
│   ├── game.py           WordGameEngine: loads data, picks answers, ranks words
│   ├── scoring.py        Final score rules
│   ├── config.py         File paths and allowed CORS origins
│   ├── schemas.py        Pydantic request and response models
│   ├── routes/           One router per endpoint
│   ├── actions/          Guess and hint logic
│   ├── utils/            File loaders, plural and verb-form rules, percentile labels
│   ├── scripts/          Offline data pipeline
│   └── tests/            API, engine and word-list tests
├── data/
│   ├── guess_words.txt      Words you can guess
│   ├── target_words.txt     Possible answers
│   ├── word_forms.txt       Plurals and verb forms, mapped to base words
│   ├── embeddings.npz       GloVe vectors for every guess word
│   ├── target_blocklist.txt Words that are never the answer (hand-edited)
│   ├── proper_nouns.txt     Extra proper nouns to exclude (hand-edited)
│   └── big_hints.json       Riddle hints (not used yet)
├── docs/                 Frontend, served by GitHub Pages
├── build.sh, start.sh    Render build and start commands
└── requirements*.txt     Server, dev and script dependencies
```

## Deployment

**Backend (Render).** Create a web service from the repository with build command `bash build.sh` and start command `bash start.sh`. These install `requirements.txt` and run Uvicorn on the port Render provides.

**Frontend (GitHub Pages).** In the repository settings, under Pages, deploy from the `main` branch and the `/docs` folder. Set `API_BASE_URL` in `docs/js/config.js` to the Render service URL, and make sure the Pages origin is listed in `CORS_ORIGINS` in `backend/config.py`.

## Data sources

- **GloVe:** Pennington, Socher & Manning (2014), *GloVe: Global Vectors for Word Representation*. The 6B 300d vectors.
- **Concreteness ratings:** Brysbaert, Warriner & Kuperman (2014), *Concreteness ratings for 40 thousand generally known English word lemmas*, Behavior Research Methods 46(3), 904–911, doi:10.3758/s13428-013-0403-5. The original data is at [osf.io/kj76e](https://osf.io/kj76e/); the game uses the [Hugging Face mirror](https://huggingface.co/datasets/StephanAkkerman/concreteness-ratings).
- **WordNet:** Princeton University, via NLTK. Used to detect proper nouns.

## Limitations and roadmap

- **One game per server.** The backend holds a single game in memory, so everyone connected plays the same word and shares the same counters. Per-player sessions are the next structural change.
- **Generous temperature labels.** With ~31,000 words, the top 5% ("Very hot") covers about 1,500 words, so a guess can be labelled "Very hot" while still far from the answer.
- **Riddle hints.** LLM-generated riddle hints exist for 100 words but are not wired into the game yet.
- **Under consideration:** leaderboards, timed and category-based modes, and UI polish.

## License

Released under the MIT License.
