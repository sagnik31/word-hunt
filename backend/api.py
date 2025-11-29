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

import traceback
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.game import WordGameEngine
from backend.config import CORS_ORIGINS
from backend.routes import health, guess, hint, quit

app = FastAPI(
    title="Word Hot-Cold Game API",
    version="1.1.0",
    description="API to get the rank of a guessed word relative to a hidden target word.",
)

# ---- CORS (adjust origins for your GitHub Pages) ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(guess.router)
app.include_router(hint.router)
app.include_router(quit.router)


@app.on_event("startup")
def startup_event() -> None:
    try:
        print("[startup] Initializing WordGameEngine...")
        app.state.engine = WordGameEngine()
        print("[startup] WordGameEngine initialized successfully!")
        print(f"[startup] Target word set to: {app.state.engine.get_target()}")
        print(f"[startup] Target similarity list length: {len(app.state.engine.target_similarity_list)}")
    except Exception as e:
        app.state.engine = None
        print(f"[startup] Failed to initialize WordGameEngine: {e}")
        print(f"[startup] Full traceback:")
        traceback.print_exc()


@app.get("/")
def root():
    return {
        "message": "Word Hot-Cold Game API",
        "endpoints": ["/health", "/guess", "/hint", "/quit", "/docs"],
    }
