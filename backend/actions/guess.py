from typing import TYPE_CHECKING, Dict, Optional

from backend.utils.scoring import compute_percentile, describe_hotness

if TYPE_CHECKING:
    from backend.game import Ranking


def make_guess(
    guess_word: str,
    ranking: "Ranking",
    word_index: Dict[str, int],
    word_forms: Dict[str, str],
) -> Dict[str, Optional[object]]:
    typed = (guess_word or "").strip().lower()

    # Plurals and verb forms count as their base word: "cats" -> "cat".
    # A plural of the answer wins even when it's a guess word itself ("dogs").
    if typed in ranking.plurals:
        guess_norm = ranking.answer
    elif typed not in word_index:
        guess_norm = word_forms.get(typed, typed)
    else:
        guess_norm = typed

    response: Dict[str, Optional[object]] = {
        "guess": typed,
        "matched": guess_norm if guess_norm != typed else None,
        "valid": False,
        "error": None,
        "is_correct": None,
        "rank": None,
        "total": None,
        "similarity": None,
        "percentile": None,
        "hotness": None,
    }

    if not guess_norm:
        response["error"] = "Empty guess."
        return response

    if guess_norm not in word_index:
        response["error"] = "Word is not in the allowed vocabulary."
        return response

    i = word_index[guess_norm]
    rank = int(ranking.rank_of[i])
    is_correct = guess_norm == ranking.answer
    response.update(
        {
            "valid": True,
            "is_correct": is_correct,
            "rank": rank,
            "total": ranking.total,
            "similarity": 1.0 if is_correct else float(ranking.sims[i]),
            "percentile": 100.0 if is_correct else compute_percentile(rank, ranking.total),
            "hotness": describe_hotness(rank),
        }
    )
    return response
