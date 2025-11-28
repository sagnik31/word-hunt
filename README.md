# 🧠 Word Hot-Cold Game

*A semantic word-guessing game powered by word embeddings + AI-generated hints*

Try to guess the hidden word! After each guess, you’ll see whether you’re **hot** or **cold** based on semantic similarity. Use hints to get subtle clues — but be careful, they won’t give the answer away!

---

## 🚀 How It Works

| Feature              | Description                                                  |
| -------------------- | ------------------------------------------------------------ |
| 💡 Semantic Hot/Cold | Each guess is ranked by cosine similarity to the target word |
| 🎯 10k+ Common Nouns | Expanding vocabulary stored efficiently in a SQLite DB       |
| 🔍 Precomputed Hints | Offline-generated LLM hints (no runtime LLM cost)            |
| ⚡ Fast API Backend   | Deployed on Render — lightweight + scalable                  |
| 🌐 Web UI Frontend   | Hosted on GitHub Pages with a clean minimal design           |

Gameplay loop:

1. A secret target word is selected from the vocabulary
2. You guess nouns — the UI shows **hot/cold** feedback
3. Use **Hint** for a subtle clue
4. **Quit** anytime to reveal the answer

---

## 🧩 Technology Stack

### Backend → Render

* **Python + FastAPI**
* **SQLite DB**
* Precomputed:

  * Word similarity rankings (top-K neighbors per word)
  * 5 hints per word from local LLM batch generation
* No heavy GPU or LLM dependencies in production
* Endpoints:

  * `GET /health`
  * `POST /guess`
  * `GET /hint`
  * `POST /quit`

### Frontend → GitHub Pages

* **HTML + CSS + Vanilla JavaScript**
* Calls backend via REST API
* Mobile-friendly and fast

---

## 🗂️ Project Structure

```
project-root/
│
├─ backend/
│   ├─ api.py               # FastAPI app
│   ├─ game.py              # Game engine + semantic scoring
│   ├─ similarities.db      # Top-K similarity neighbors per word
│   ├─ hints.db             # Precomputed hints for each word
│   ├─ common_nouns.txt     # Vocabulary source
│   ├─ requirements.txt
│   └─ start.sh
│
└─ frontend/
    ├─ index.html           # Web UI
    ├─ styles.css           # Styling
    └─ app.js               # Client logic + API calls
```

---

## 🔌 Deployment

### Backend (Render)

Settings:

| Setting        | Value                                         |
| -------------- | --------------------------------------------- |
| Root Directory | `backend/`                                    |
| Build Command  | `pip install -r requirements.txt`             |
| Start Command  | `uvicorn api:app --host 0.0.0.0 --port $PORT` |

Render automatically loads the FastAPI server and serves all API endpoints.

---

### Frontend (GitHub Pages)

1. Push frontend folder to GitHub
2. Settings → Pages
3. Deploy from branch → `/frontend/`

Visit:

```
https://<username>.github.io/<repo-name>/
```

Ensure backend CORS allows the frontend URL.

---

## 📦 Local Development

```bash
cd backend
pip install -r requirements.txt
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Visit frontend locally by opening:

```
frontend/index.html
```

---

## 🔮 Roadmap

| Planned Feature                    |     Status    |
| ---------------------------------- | :-----------: |
| Expanded vocab (10k+ nouns)        |       ⏳       |
| Precomputing hints w/ local LLM    |       ⏳       |
| Leaderboards                       | 📝 Considered |
| Game modes (timed, category-based) | 📝 Considered |
| UI polish + animations             | 📝 Considered |

---

## 🏁 Summary

This project demonstrates:

* Efficient similarity search over large vocabulary
* Offline AI-assisted hint generation
* Free-tier friendly architecture
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