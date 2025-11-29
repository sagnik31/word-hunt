from fastapi import HTTPException, Request

from backend.game import WordGameEngine


def get_engine(request: Request) -> WordGameEngine:
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        raise HTTPException(status_code=500, detail="Game engine not initialized.")
    return engine
