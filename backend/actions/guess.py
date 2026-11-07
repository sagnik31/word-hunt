from typing import Dict, List, Optional, Set, Tuple

from backend.utils.scoring import describe_hotness, compute_percentile


def make_guess(
    guess_word: str,
    target_word: str,
    target_similarity_list: List[Tuple[str, float]],
    target_pos_map: Dict[str, int],
    target_total: int,
    vocab_set: Set[str],
    word_forms: Dict[str, str],
    target_plurals: Set[str],
) -> Dict[str, Optional[object]]:
    typed = (guess_word or "").strip().lower()

    # Plurals and verb forms count as their base word: "cats" -> "cat".
    # A plural of the answer wins even when it's a guess word itself ("dogs").
    if typed in target_plurals:
        guess_norm = target_word
    elif typed not in vocab_set:
        guess_norm = word_forms.get(typed, typed)
    else:
        guess_norm = typed

    base_response: Dict[str, Optional[object]] = {
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
        base_response["error"] = "Empty guess."
        return base_response

    if guess_norm not in vocab_set:
        base_response["error"] = "Word is not in the allowed vocabulary."
        return base_response

    base_response["valid"] = True

    # Correct guess case
    if guess_norm == target_word:
        sim = 1.0
        rank = 1
        percentile = 100.0
        hotness = describe_hotness(rank, target_total)

        base_response.update(
            {
                "is_correct": True,
                "rank": rank,
                "total": target_total,
                "similarity": sim,
                "percentile": percentile,
                "hotness": hotness,
            }
        )
        return base_response

    # In-vocab, not equal to target: find its rank & similarity.
    # The target is rank 1, so its closest neighbour (index 0) is rank 2.
    if guess_norm not in target_pos_map:
        base_response["error"] = (
            "Internal error: guess not found in target similarity list."
        )
        base_response["valid"] = False
        return base_response
    idx = target_pos_map[guess_norm]
    rank = idx + 2
    sim = target_similarity_list[idx][1]

    # Percentile & hotness are now rank-based
    percentile = compute_percentile(rank, target_total)
    hotness = describe_hotness(rank, target_total)

    base_response.update(
        {
            "is_correct": False,
            "rank": rank,
            "total": target_total,
            "similarity": sim,
            "percentile": percentile,
            "hotness": hotness,
        }
    )
    return base_response
