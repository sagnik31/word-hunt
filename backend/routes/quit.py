from fastapi import APIRouter, Depends

from backend.dependencies import get_engine
from backend.game import WordGameEngine
from backend.schemas import QuitResponse
from backend.scoring import calculate_final_score

router = APIRouter()


@router.post("/quit", response_model=QuitResponse)
def quit_endpoint(
    engine: WordGameEngine = Depends(get_engine),
) -> QuitResponse:
    score = calculate_final_score(
        False,
        engine.start_time,
        engine.hint_count,
        engine.similar_click_count,
        engine.best_percentile,
    )

    answer = engine.get_target()

    # Reset the game for next round
    engine.set_target()

    return QuitResponse(
        answer=answer,
        score=score,
    )
