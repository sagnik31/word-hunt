from typing import Dict, List, Tuple


def load_vocab(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    tokens = text.split()
    return [t.strip().lower() for t in tokens if t.strip()]

def build_line_index(path: str) -> Dict[str, int]:
    offsets: Dict[str, int] = {}
    with open(path, "r", encoding="utf-8") as fh:
        while True:
            pos = fh.tell()
            line = fh.readline()
            if not line:
                break
            parts = line.split("\t", 1)
            if not parts:
                continue
            word = parts[0].strip()
            if word:
                offsets[word] = pos
    return offsets

def read_similarity_row(path: str, offset: int) -> List[Tuple[str, float]]:
    with open(path, "r", encoding="utf-8") as fh:
        fh.seek(offset)
        line = fh.readline()
    if not line:
        raise ValueError("Failed to read line at offset")

    parts = line.rstrip("\n").split("\t", 1)
    if len(parts) != 2:
        return []

    right = parts[1]
    if not right:
        return []

    pairs = right.split(",")
    result: List[Tuple[str, float]] = []
    for p in pairs:
        try:
            other, sc = p.rsplit(":", 1)
            result.append((other, float(sc)))
        except ValueError:
            continue
    return result
