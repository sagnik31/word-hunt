#!/usr/bin/env python3
"""
api.py

FastAPI app for the daily puzzle. The server keeps no player state: each
request names a puzzle number, and the browser sends the player's progress.

  - GET  /health
  - GET  /today           (today's puzzle number, UTC)
  - GET  /puzzle/{number} (how many clues a puzzle has)
  - POST /guess
  - POST /hint            (reveal a word close to the answer)
  - POST /clue            (the next written clue)
  - POST /quit            (reveal the answer)
  - GET  /results/{number} (how a finished play compares; needs DATABASE_URL)

Run locally (from the repo root):
  uvicorn backend.api:app --host 0.0.0.0 --port 8000
"""

import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import (
    CLUES_PATH,
    CORS_ORIGINS,
    DATABASE_URL_ENV,
    LAUNCH_DATE,
    SCHEDULE_PATH,
    database_url,
    schedule_key,
)
from backend.daily import DailySchedule, load_clues
from backend.game import WordGameEngine
from backend.results import open_store
from backend.routes import guess, health, help, quit, results, today


def load_schedule(engine: WordGameEngine) -> DailySchedule:
    key = schedule_key()
    if key is None:
        raise RuntimeError("No schedule key: set WORDHUNT_SCHEDULE_KEY or add schedule.key.")
    schedule = DailySchedule.load(SCHEDULE_PATH, key, engine.vocabulary, LAUNCH_DATE)
    if not schedule.words:
        raise RuntimeError(f"Schedule is empty: {SCHEDULE_PATH}")
    missing = sum(w is None for w in schedule.words)
    if missing:
        print(f"[startup] Warning: {missing} schedule lines don't decode (wrong key?)")
    return schedule


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.engine = None
    app.state.schedule = None
    app.state.clues = {}
    # Opening the store doesn't connect: the server starts even if the
    # database is asleep or unreachable.
    url = database_url()
    app.state.results = open_store(url)
    if app.state.results is None:
        reason = "unrecognised URL" if url else f"no {DATABASE_URL_ENV}"
        print(f"[startup] Results are off ({reason})")
    else:
        print(f"[startup] Results on ({type(app.state.results).__name__})")
    try:
        print("[startup] Initializing WordGameEngine...")
        app.state.engine = WordGameEngine()
        app.state.schedule = load_schedule(app.state.engine)
        schedule = app.state.schedule
        app.state.clues = load_clues(CLUES_PATH, schedule_key(), schedule.words)
        print(f"[startup] Clues for {len(app.state.clues)} of {len(schedule.words)} puzzles")
        print(f"[startup] {len(schedule.words)} puzzles scheduled; today is #{schedule.current()}")
    except Exception as e:
        print(f"[startup] Failed to initialize: {e}")
        traceback.print_exc()
    yield
    if app.state.results is not None:
        app.state.results.close()


app = FastAPI(
    title="Word Hot-Cold Game API",
    version="2.0.0",
    description="Daily puzzle: rank a guessed word against the day's hidden word.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(today.router)
app.include_router(guess.router)
app.include_router(help.router)
app.include_router(quit.router)
app.include_router(results.router)


@app.get("/")
def root():
    return {
        "message": "Word Hot-Cold Game API",
        "endpoints": ["/health", "/today", "/puzzle/{number}", "/guess", "/hint", "/clue", "/quit", "/results/{number}", "/docs"],
    }
