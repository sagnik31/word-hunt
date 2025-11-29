from fastapi import APIRouter, Depends

from backend.dependencies import get_engine
from backend.game import WordGameEngine
from backend.schemas import QuitResponse

router = APIRouter()


@router.post("/quit", response_model=QuitResponse)
def quit_endpoint(
    engine: WordGameEngine = Depends(get_engine),
) -> QuitResponse:
    """
    Reveal the current target word.
    (Does not reset the game by itself.)
    """
    answer = engine.get_answer()
    return QuitResponse(answer=answer)
