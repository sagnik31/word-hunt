#!/usr/bin/env python3
"""
api.py

FastAPI app exposing an HTTP API:

  - GET  /health
  - POST /guess
  - GET  /hint    (suggest a hot word)
  - POST /quit    (reveal the answer)

Run locally:
  uvicorn api:app --host 0.0.0.0 --port 8000
"""

from typing import Optional, Any, Dict

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from game import WordGameEngine

app = FastAPI(
    title="Word Hot-Cold Game API",
    version="1.1.0",
    description="API to get the rank of a guessed word relative to a hidden target word.",
)

# ---- CORS (adjust origins for your GitHub Pages) ----
origins = [
    "https://<your-github-username>.github.io",
    "https://<your-github-username>.github.io/<your-frontend-repo>",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # or ["*"] while testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Pydantic models ----------

class GuessRequest(BaseModel):
    word: str


class GuessResponse(BaseModel):
    guess: str
    valid: bool
    error: Optional[str] = None
    is_correct: Optional[bool] = None
    rank: Optional[int] = None
    total: Optional[int] = None
    similarity: Optional[float] = None
    percentile: Optional[float] = None
    hotness: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    target_word_loaded: bool


class HintResponse(BaseModel):
    word: str
    rank: int
    total: int
    similarity: float
    percentile: float
    hotness: str


class QuitResponse(BaseModel):
    answer: str


# ---------- Engine lifecycle & dependency ----------

def get_engine() -> WordGameEngine:
    engine = getattr(app.state, "engine", None)
    if engine is None:
        raise HTTPException(status_code=500, detail="Game engine not initialized.")
    return engine


@app.on_event("startup")
def startup_event() -> None:
    try:
        app.state.engine = WordGameEngine()
    except Exception as e:  # noqa: BLE001
        app.state.engine = None
        print(f"[startup] Failed to initialize WordGameEngine: {e}")


# ---------- Endpoints ----------

@app.get("/")
def root():
    return {
        "message": "Word Hot-Cold Game API",
        "endpoints": ["/health", "/guess", "/hint", "/quit", "/docs"],
    }


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    engine = getattr(app.state, "engine", None)
    return HealthResponse(
        status="ok" if engine is not None else "degraded",
        target_word_loaded=engine is not None,
    )


@app.post("/guess", response_model=GuessResponse)
def make_guess_endpoint(
    payload: GuessRequest,
    engine: WordGameEngine = Depends(get_engine),
) -> GuessResponse:
    result: Dict[str, Any] = engine.make_guess(payload.word)
    return GuessResponse(**{
        "guess": result.get("guess", ""),
        "valid": bool(result.get("valid", False)),
        "error": result.get("error"),
        "is_correct": result.get("is_correct"),
        "rank": result.get("rank"),
        "total": result.get("total"),
        "similarity": result.get("similarity"),
        "percentile": result.get("percentile"),
        "hotness": result.get("hotness"),
    })


@app.get("/hint", response_model=HintResponse)
def hint_endpoint(
    engine: WordGameEngine = Depends(get_engine),
) -> HintResponse:
    """
    Suggest a 'hot' word: randomly selected from top-N most similar words
    to the current target.
    """
    info = engine.get_hint(top_n=10)
    return HintResponse(**info)


@app.post("/quit", response_model=QuitResponse)
def quit_endpoint(
    engine: WordGameEngine = Depends(get_engine),
) -> QuitResponse:
    """
    Reveal the current target word.
    (Does not reset the game by itself.)
    """
    answer = engine.get_answer()
    return QuitResponse(answer=answer)
