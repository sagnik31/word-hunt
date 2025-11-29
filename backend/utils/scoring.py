# scoring.py — Updated percentile-based hotness

from typing import Optional

def compute_percentile(rank: int, total: int) -> float:
    """
    Convert rank into a percentile where:
      - rank=1 => ~100% (best)
      - rank=total => ~0% (worst)
    """
    total_others = max(1, total - 1)
    return 100.0 * (1.0 - (rank - 1) / total_others)


def describe_hotness(rank: int, total: int) -> str:
    """
    Hotness categories based on percentile bands.
    """
    if rank == 1:
        return "Correct"

    percentile = compute_percentile(rank, total)

    if percentile >= 99.0:
        return "Boiling"
    if percentile >= 95.0:
        return "Very hot"
    if percentile >= 90.0:
        return "Hot"
    if percentile >= 75.0:
        return "Warm"
    if percentile >= 50.0:
        return "Cool"
    if percentile >= 25.0:
        return "Cold"
    return "Freezing"
