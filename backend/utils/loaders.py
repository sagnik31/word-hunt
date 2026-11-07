from typing import Dict, List


def load_word_list(path: str) -> List[str]:
    """Read a file with one word per line."""
    with open(path, "r", encoding="utf-8") as fh:
        return [line.strip().lower() for line in fh if line.strip()]


def load_word_forms(path: str) -> Dict[str, str]:
    """Read "form<TAB>base" lines, e.g. "cats\tcat"."""
    forms: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\r\n").split("\t")
            if len(parts) == 2:
                forms[parts[0]] = parts[1]
    return forms
