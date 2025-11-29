from typing import Dict, List, Optional, Set, Tuple

from backend.utils.scoring import describe_hotness


def make_guess(
    guess_word: str,
    target_word: str,
    target_similarity_list: List[Tuple[str, float]],
    target_pos_map: Dict[str, int],
    target_total: int,
    vocab_set: Set[str],
    offsets: Dict[str, int],
) -> Dict[str, Optional[object]]:
    guess_norm = (guess_word or "").strip().lower()

    base_response: Dict[str, Optional[object]] = {
        "guess": guess_norm,
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

    if guess_norm not in offsets:
        base_response["error"] = "Word is missing from similarity data."
        return base_response

    base_response["valid"] = True

    if guess_norm == target_word:
        sim = 1.0
        rank = 1
        percentile = 100.0
        hotness = describe_hotness(sim)

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

    if guess_norm in target_pos_map:
        idx = target_pos_map[guess_norm]
        rank = idx + 1
        sim = target_similarity_list[idx][1]
    else:
        idx = None
        sim = None
        for j, (w, sc) in enumerate(target_similarity_list):
            if w == guess_norm:
                idx = j
                sim = sc
                break
        if idx is None or sim is None:
            base_response["error"] = (
                "Internal error: guess not found in target similarity list."
            )
            base_response["valid"] = False
            return base_response
        rank = idx + 1

    total_others = max(1, target_total - 1)
    percentile = 100.0 * (1.0 - (rank - 1) / total_others)
    hotness = describe_hotness(sim)

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
