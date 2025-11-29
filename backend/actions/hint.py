import random
from typing import Dict, List, Tuple

from backend.utils.scoring import describe_hotness


def get_hint(
    target_similarity_list: List[Tuple[str, float]], target_total: int, top_n: int = 10
) -> Dict[str, object]:
    if not target_similarity_list:
        raise RuntimeError(
            "Target similarity list is empty; engine not initialized properly."
        )

    n_others = len(target_similarity_list)
    k = min(max(top_n, 1), n_others)

    idx = random.randint(0, k - 1)
    word, sim = target_similarity_list[idx]
    rank = idx + 1

    total_others = max(1, target_total - 1)
    percentile = 100.0 * (1.0 - (rank - 1) / total_others)
    hotness = describe_hotness(sim)

    return {
        "word": word,
        "rank": rank,
        "total": target_total,
        "similarity": sim,
        "percentile": percentile,
        "hotness": hotness,
    }
