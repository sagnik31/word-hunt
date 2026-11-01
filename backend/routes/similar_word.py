from fastapi import APIRouter, Depends

from backend.dependencies import get_engine
from backend.game import WordGameEngine
from backend.schemas import SimilarWordResponse

router = APIRouter()


@router.post("/similar_word", response_model=SimilarWordResponse)
def similar_word_endpoint(
    engine: WordGameEngine = Depends(get_engine),
) -> SimilarWordResponse:
    """
    Suggest a word ranked better than the player's best so far.
    POST because it changes game state (help count, best rank).
    """
    info = engine.get_similar_word()
    return SimilarWordResponse(**info)