def describe_hotness(similarity_score: float) -> str:
    s = similarity_score
    if s >= 0.99:
        return "Correct"
    if s >= 0.90:
        return "Boiling"
    if s >= 0.75:
        return "Very hot"
    if s >= 0.60:
        return "Hot"
    if s >= 0.45:
        return "Warm"
    if s >= 0.30:
        return "Cool"
    if s >= 0.15:
        return "Cold"
    return "Freezing"
