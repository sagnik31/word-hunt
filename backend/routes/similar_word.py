from fastapi import APIRouter, Depends

from backend.dependencies import get_engine
from backend.game import WordGameEngine
from backend.schemas import SimilarWordResponse

router = APIRouter()


@router.get("/similar_word", response_model=SimilarWordResponse)
def similar_word_endpoint(
    engine: WordGameEngine = Depends(get_engine),
) -> SimilarWordResponse:
    """
    Suggest a 'hot' word: randomly selected from top-N most similar words
    to the current target.
    """
    info = engine.get_similar_word()
    return SimilarWordResponse(**info)