from fastapi import APIRouter, Depends

from backend.dependencies import get_engine
from backend.game import WordGameEngine
from backend.schemas import HintResponse

router = APIRouter()


@router.post("/hint", response_model=HintResponse)
def hint_endpoint(
    engine: WordGameEngine = Depends(get_engine),
) -> HintResponse:
    """
    Suggest a word ranked better than the player's best so far.
    POST because it changes game state (help count, best rank).
    """
    info = engine.get_hint()
    return HintResponse(**info)