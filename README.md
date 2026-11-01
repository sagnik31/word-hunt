# 🧠 Word Hot-Cold Game

*A semantic word-guessing game powered by word embeddings*

Try to guess the hidden word! After each guess, you’ll see whether you’re **hot** or **cold** based on semantic similarity. Stuck? Ask for a word that's closer than your best guess so far — at a cost to your score.

---

## 🚀 How It Works

| Feature                 | Description                                                                  |
| ----------------------- | ---------------------------------------------------------------------------- |
| 💡 Semantic Hot/Cold    | Each guess is ranked by GloVe cosine similarity to the target word           |
| 🎯 ~2,300 Common Nouns  | Vocabulary with a precomputed similarity ranking for every word              |
| 🔍 Hint / Similar Word  | Reveals a word ranked closer than your best guess so far                     |
| 🏆 Scoring              | 100 points for solving, minus time and help penalties; quitting scores partial credit |
| ⚡ FastAPI Backend       | Deployed on Render — no GPU or LLM needed at runtime                          |
| 🌐 Web UI Frontend      | Static HTML/CSS/JS on GitHub Pages                                            |

Gameplay loop:

1. A secret target word is selected from the vocabulary
2. You guess nouns — the UI shows your rank, similarity and a **hot/cold** label
3. Use **Hint** or **Similar Word** to reveal a closer word
4. **Quit** anytime to reveal the answer

Hotness is based on rank percentile: Boiling (top 1%), Very hot (top 5%), Hot (top 10%), Warm (top 25%), Cool (top 50%), Cold, Freezing.

---

## 🧩 Technology Stack

### Backend → Render

* **Python + FastAPI**, no database — data is read from plain files in `data/`
* Precomputed offline:

  * GloVe 300d embeddings for each vocabulary word (`embeddings.npz`)
  * A full similarity ranking of every word against every other word (`similarity.txt`)
* At startup the engine indexes `similarity.txt` by byte offset and loads only the current target's row
* One game is held in server memory, shared by all clients
* Endpoints:

  * `GET /health`
  * `POST /guess`
  * `GET /similar_word`
  * `GET /hint`
  * `POST /quit`

### Frontend → GitHub Pages

* **HTML + CSS + Vanilla JavaScript** (ES modules, no build step)
* Calls the backend via REST (`docs/js/api.js`); backend URL set in `docs/js/config.js`

---

## 🗂️ Project Structure

```
project-root/
│
├─ backend/
│   ├─ api.py               # FastAPI app + startup
│   ├─ game.py              # WordGameEngine: target selection + game state
│   ├─ scoring.py           # Final score rules
│   ├─ routes/              # One router per endpoint
│   ├─ actions/             # Guess / hint / similar-word logic
│   ├─ utils/               # File loaders, percentile + hotness
│   ├─ scripts/             # Offline data pipeline (see below)
│   └─ tests/               # API tests (pytest)
│
├─ data/
│   ├─ common_nouns.txt     # Vocabulary source
│   ├─ embeddings.npz       # Embeddings for the vocabulary
│   ├─ similarity.txt       # Ranked neighbours per word
│   └─ big_hints.json       # LLM riddle hints for 100 words (not used by the game yet)
│
├─ docs/                    # Frontend, served by GitHub Pages
│   ├─ index.html
│   ├─ styles.css
│   └─ js/                  # main.js, ui.js, api.js, config.js
│
├─ words_20k.txt            # Candidate 20k-noun vocabulary (not used by the game yet)
├─ requirements.txt         # Server dependencies
├─ requirements-dev.txt     # + test dependencies
├─ requirements-scripts.txt # Offline script dependencies
├─ build.sh / start.sh      # Render build + start
└─ run_backend.bat          # Local start on Windows
```

---

## 🔌 Deployment

### Backend (Render)

Settings, run from the repo root:

| Setting        | Value        |
| -------------- | ------------ |
| Build Command  | `bash build.sh` (installs `requirements.txt`) |
| Start Command  | `bash start.sh` (`uvicorn backend.api:app --host 0.0.0.0 --port $PORT`) |

---

### Frontend (GitHub Pages)

1. Settings → Pages
2. Deploy from branch → `/docs`

Visit:

```
https://<username>.github.io/<repo-name>/
```

Ensure `CORS_ORIGINS` in `backend/config.py` includes the frontend's origin.

---

## 📦 Local Development

From the repo root:

```bash
pip install -r requirements-dev.txt
uvicorn backend.api:app --reload --host 0.0.0.0 --port 8000
```

Serve the frontend (ES modules don't load from `file://`):

```bash
python -m http.server 8080 -d docs
```

Then point `API_BASE_URL` in `docs/js/config.js` at `http://localhost:8000` and open `http://localhost:8080`.

Run the tests (`python -m` puts the repo root on the import path):

```bash
python -m pytest
```

### Rebuilding the data

Needs `pip install -r requirements-scripts.txt` and the GloVe file `data/glove.6B.300d.txt` (not committed). Run from the repo root:

1. `python backend/scripts/extract_embeddings.py` — `common_nouns.txt` + GloVe → `embeddings.npz` (unmatched words go to `missing.txt`)
2. `python backend/scripts/build_similarity.py` — `embeddings.npz` → `similarity.txt`

Optional:

* `python backend/scripts/build_vocabulary.py` — builds `words_20k.txt`
* `python backend/scripts/generate_big_hints.py` — riddle hints via a local Ollama model → `big_hints.json`

---

## 🔮 Roadmap

| Planned Feature                    |     Status    |
| ---------------------------------- | :-----------: |
| Expanded vocab (20k nouns)         | ⏳ List built, not wired in |
| Riddle hints from a local LLM      | ⏳ 100 words generated, not wired in |
| Leaderboards                       | 📝 Considered |
| Game modes (timed, category-based) | 📝 Considered |
| UI polish + animations             | 📝 Considered |

---

## 🏁 Summary

This project demonstrates:

* Semantic similarity ranking from word embeddings, precomputed offline
* Free-tier friendly architecture with no runtime ML dependencies
* Clean separation of frontend & backend services

If you like semantic puzzles, this game gives real “AHA!” moments 🔥🧊

---

## 🤝 Contributing

Issues & pull requests welcome!
Have an idea for a mode or feature? Let’s build it 😄

---

## 📜 License

MIT License — use, modify, and build on top of this freely.

---
