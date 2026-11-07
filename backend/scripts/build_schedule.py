#!/usr/bin/env python3
"""
Build or extend the daily puzzle schedule, data/daily_schedule.txt.

Run from the repository root:
    python backend/scripts/build_schedule.py

Needs the schedule key: the WORDHUNT_SCHEDULE_KEY environment variable, or a
schedule.key file at the repo root. With no key at all, pass --new-key to
create schedule.key. Keep a copy of the key somewhere safe (a password
manager): without it the schedule can't be read, and past puzzles are lost.

Rules:
  - Puzzles up to and including today (UTC) never change.
  - Future puzzles keep their word if it's still in target_words.txt;
    pruned words are dropped and the gap closes.
  - Every target word not yet scheduled is added in a random order, so the
    schedule never repeats a word.
"""

import argparse
import random
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.config import (  # noqa: E402
    LAUNCH_DATE,
    SCHEDULE_KEY_FILE,
    SCHEDULE_PATH,
    TARGET_WORDS_PATH,
    schedule_key,
)
from backend.daily import DailySchedule, decode, read_codes, word_code  # noqa: E402
from backend.utils.loaders import load_word_list  # noqa: E402

HEADER = (
    "# Daily puzzle schedule: line N is puzzle #N. Each line is a keyed hash of\n"
    "# the answer, so the words stay hidden. Built by backend/scripts/build_schedule.py.\n"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--new-key", action="store_true", help="create schedule.key if no key exists")
    args = parser.parse_args()

    key = schedule_key()
    if key is None:
        if not args.new_key:
            sys.exit("No schedule key. Set WORDHUNT_SCHEDULE_KEY, or rerun with --new-key.")
        if read_codes(SCHEDULE_PATH):
            sys.exit("A schedule exists but there's no key to read it. Find the original key.")
        key = secrets.token_hex(32)
        SCHEDULE_KEY_FILE.write_text(key + "\n", encoding="utf-8")
        print(f"Created {SCHEDULE_KEY_FILE.name}. Save a copy of it somewhere safe.")

    targets = load_word_list(str(TARGET_WORDS_PATH))
    target_set = set(targets)

    codes = read_codes(SCHEDULE_PATH)
    # Every scheduled word was a target once; decode against the current
    # targets plus anything still in the guess list.
    guess_words = load_word_list(str(ROOT / "data" / "guess_words.txt"))
    old_words = decode(codes, key, set(guess_words) | target_set)
    if any(w is None for w in old_words):
        sys.exit("Some schedule lines don't decode: wrong key, or a word left the guess list.")

    schedule = DailySchedule(old_words, LAUNCH_DATE)
    frozen = max(0, min(schedule.current(), len(old_words)))
    past = old_words[:frozen]
    used = set(past)

    future = []
    for w in old_words[frozen:]:
        if w in target_set and w not in used:
            future.append(w)
            used.add(w)

    new_words = [w for w in targets if w not in used]
    random.SystemRandom().shuffle(new_words)
    words = past + future + new_words

    SCHEDULE_PATH.write_text(HEADER + "".join(word_code(w, key) + "\n" for w in words), encoding="utf-8")
    dropped = len(old_words) - frozen - len(future)
    print(f"Puzzles kept as they were (today and before): {len(past)}")
    print(f"Future puzzles kept: {len(future)}  dropped (pruned): {dropped}")
    print(f"New puzzles added:   {len(new_words)}")
    print(f"Schedule length:     {len(words)}  -> {SCHEDULE_PATH.relative_to(ROOT)}")
    print(f"Last puzzle date:    {schedule.date_of(len(words))}")


if __name__ == "__main__":
    main()
