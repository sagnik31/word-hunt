# scoring.py — percentile (used for the score) and rank-based temperature labels


def compute_percentile(rank: int, total: int) -> float:
    """
    Convert rank into a percentile where:
      - rank=1 => ~100% (best)
      - rank=total => ~0% (worst)
    """
    total_others = max(1, total - 1)
    return 100.0 * (1.0 - (rank - 1) / total_others)


# Temperature bands by rank: (worst rank in the band, label).
# Fixed ranks rather than percentiles: past ~1,000 the neighbours are mostly
# unrelated to the answer, so every band sits inside the top 1,000 and
# everything beyond is "Freezing". The rank number still shows the detail.
HOTNESS_BANDS = [
    (10, "Boiling"),
    (30, "Very hot"),
    (100, "Hot"),
    (300, "Warm"),
    (600, "Cool"),
    (1000, "Cold"),
]


def describe_hotness(rank: int) -> str:
    """Temperature label for a guess's rank (rank 1 is the answer)."""
    if rank == 1:
        return "Correct"
    for max_rank, label in HOTNESS_BANDS:
        if rank <= max_rank:
            return label
    return "Freezing"
