"""
The daily puzzle schedule.

Puzzle #1 is the launch date and each UTC day after it is the next puzzle.
The schedule file stores one code per puzzle, not the word itself: a keyed
hash (HMAC) of the answer. The repo is public, and without the key nobody can
tell which word a code stands for, so future answers stay hidden.
"""

import hashlib
import hmac
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional


def word_code(word: str, key: str) -> str:
    """The schedule code for a word: a short keyed hash."""
    digest = hmac.new(key.encode("utf-8"), word.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()[:20]


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def seconds_until_next_puzzle(now: Optional[datetime] = None) -> int:
    now = now or datetime.now(timezone.utc)
    tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), timezone.utc)
    return max(0, int((tomorrow - now).total_seconds()))


def read_codes(path: Path) -> List[str]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip() and not line.startswith("#")]


def decode(codes: Iterable[str], key: str, vocabulary: Iterable[str]) -> List[Optional[str]]:
    """Turn codes back into words. A code no word matches becomes None."""
    by_code: Dict[str, str] = {word_code(w, key): w for w in vocabulary}
    return [by_code.get(c) for c in codes]


class DailySchedule:
    """Which word is the answer on which day."""

    def __init__(self, words: List[Optional[str]], launch: date):
        self.words = words
        self.launch = launch

    @classmethod
    def load(cls, path: Path, key: str, vocabulary: Iterable[str], launch: date) -> "DailySchedule":
        return cls(decode(read_codes(path), key, vocabulary), launch)

    def number_on(self, day: date) -> int:
        """Puzzle number for a UTC date (0 or less before launch)."""
        return (day - self.launch).days + 1

    def current(self, today: Optional[date] = None) -> int:
        return self.number_on(today or today_utc())

    def date_of(self, number: int) -> date:
        return self.launch + timedelta(days=number - 1)

    def is_open(self, number: int, today: Optional[date] = None) -> bool:
        """Released (today or earlier) and has an answer."""
        return (
            1 <= number <= self.current(today)
            and number <= len(self.words)
            and self.words[number - 1] is not None
        )

    def answer(self, number: int) -> str:
        word = self.words[number - 1] if 1 <= number <= len(self.words) else None
        if word is None:
            raise KeyError(f"No answer scheduled for puzzle #{number}")
        return word


def load_clues(path: Path, key: str, answers: Iterable[Optional[str]]) -> Dict[str, List[str]]:
    """Clues for each answer. The file is keyed by word codes, like the schedule."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        by_code: Dict[str, List[str]] = json.load(fh)
    clues = {}
    for word in answers:
        if word and word_code(word, key) in by_code:
            clues[word] = by_code[word_code(word, key)]
    return clues
