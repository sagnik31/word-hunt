#!/usr/bin/env python3
"""
api.py

FastAPI app exposing an HTTP API to get the rank of a guessed word
relative to the current target in the WordGameEngine.

Endpoints:
  - GET  /health            : simple health check
  - POST /guess             : takes a guess word and returns rank + metadata

Run with:
  uvicorn api:app --reload

Requirements:
  - fastapi
  - uvicorn
  - numpy
"""

from typing import Optional, Any, Dict

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

from game import WordGameEngine

app = FastAPI(
    title="Word Hot-Cold Game API",
    version="1.0.0",
    description="API to get the rank of a guessed word relative to a hidden target word.",
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


# ---------- Engine lifecycle & dependency ----------


def get_engine() -> WordGameEngine:
    """
    FastAPI dependency that returns the singleton WordGameEngine.
    Raises HTTP 500 if the engine is not initialized.
    """
    engine = getattr(app.state, "engine", None)
    if engine is None:
        # This should only happen if startup failed
        raise HTTPException(status_code=500, detail="Game engine not initialized.")
    return engine


@app.on_event("startup")
def startup_event() -> None:
    """
    Initialize the WordGameEngine once, at app startup.
    """
    try:
        app.state.engine = WordGameEngine()
    except Exception as e:  # noqa: BLE001 - broad OK for startup failure
        # If initialization fails, we keep engine as None; /health will report it.
        app.state.engine = None
        # Log to server console
        print(f"[startup] Failed to initialize WordGameEngine: {e}")


# ---------- Endpoints ----------


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """
    Simple health check endpoint to verify the API and engine are up.
    """
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
    """
    Main API to make a guess.

    Request body:
      {
        "word": "cat"
      }

    Response (example):
      {
        "guess": "cat",
        "valid": true,
        "error": null,
        "is_correct": false,
        "rank": 123,
        "total": 1999,
        "similarity": 0.45,
        "percentile": 93.8,
        "hotness": "Warm"
      }
    """
    result: Dict[str, Any] = engine.make_guess(payload.word)

    # NOTE: you can choose whether to:
    #   - always return 200 with valid=false for invalid guesses (current behavior), or
    #   - raise HTTP 400 for invalid guesses.
    # Here we return 200 and encode the error in the JSON, to keep the client logic simple.

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
