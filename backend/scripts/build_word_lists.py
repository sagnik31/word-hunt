#!/usr/bin/env python3
"""
Build the word lists from the Brysbaert et al. (2014) concreteness ratings.

Run from the repository root:
    python backend/scripts/build_word_lists.py

Inputs:
  - data/raw/concreteness_ratings.csv  (Hugging Face mirror of the dataset)
  - data/glove.6B.300d.txt             (only its vocabulary is read)
  - data/target_blocklist.txt          (words never used as answers)
  - data/proper_nouns.txt              (proper nouns WordNet doesn't know)
  - NLTK's WordNet data: python -m nltk.downloader wordnet

Proper nouns are never allowed, as guesses or answers. A word counts as one
when WordNet only knows it with a capital letter ("Monday", "Kleenex"), or
when it's listed in data/proper_nouns.txt.

Outputs, sorted:
  - data/guess_words.txt   every single word that has a GloVe vector
  - data/target_words.txt  everyday, picturable nouns used as answers
  - data/word_forms.txt    "form<TAB>base" lines: plurals and verb forms that
                           aren't guess words themselves ("cats" -> "cat")
  - data/hint_words.txt    guess words ordinary enough for a Hint to reveal
"""

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.utils.word_forms import inflections  # noqa: E402
from nltk.corpus import wordnet  # noqa: E402

DATA = ROOT / "data"
RATINGS_PATH = DATA / "raw" / "concreteness_ratings.csv"
GLOVE_PATH = DATA / "glove.6B.300d.txt"
BLOCKLIST_PATH = DATA / "target_blocklist.txt"
PROPER_NOUNS_PATH = DATA / "proper_nouns.txt"
GUESS_OUT = DATA / "guess_words.txt"
TARGET_OUT = DATA / "target_words.txt"
FORMS_OUT = DATA / "word_forms.txt"
HINT_OUT = DATA / "hint_words.txt"

# Target filters (agreed with the owner: "Option A", about 2,900 candidates).
MIN_PERCENT_KNOWN = 0.95  # share of raters who knew the word
MIN_CONCRETENESS = 4.0  # 1 = abstract, 5 = concrete
MIN_SUBTLEX = 50  # subtitle frequency count, drops rare words

# Hint words: a Hint only reveals ordinary words, not rare or inflected
# neighbours such as "marshy" (subtitle count 3) or "skidded" (a verb form).
HINT_MIN_PERCENT_KNOWN = 0.95
HINT_MIN_SUBTLEX = 10

# Plurals that mean something other than "more than one" of the singular,
# so the plural rule below keeps them.
KEEP_PLURALS = {"clothes", "glasses", "pajamas", "checkers"}

GUESS_PATTERN = re.compile(r"[a-z]+(?:[-'][a-z]+)*")  # e.g. t-shirt, yo-yo

# WordNet capitalises these, but they're ordinary lowercase words. The first
# row is function words that clash with acronyms or names ("IT", "US", "Who").
NOT_PROPER_NOUNS = {
    "am", "an", "it", "me", "oh", "or", "us", "who",
    "adrenalin", "afro", "amen", "brie", "chardonnay", "cognac", "draconian",
    "eureka", "hazmat", "highlander", "lowlander", "mayday", "merlot",
    "mister", "monsieur", "northerner", "parmesan", "pharaoh", "renaissance",
    "senorita", "southerner", "statehouse", "t-shirt", "westernization", "wifi",
}


def is_proper_noun(word: str) -> bool:
    """True when WordNet only knows the word capitalised ("Monday"), and it
    isn't an inflection of a lowercase word ("Acts" the book vs "act")."""
    if word in NOT_PROPER_NOUNS:
        return False
    names = {
        name
        for synset in wordnet.synsets(word)
        for name in synset.lemma_names()
        if name.lower() == word
    }
    if not names or any(name == word for name in names):
        return False
    # All candidate base forms; morphy() alone stops at "Fungi" the kingdom
    # and never reaches "fungus".
    bases = {b for pos in "nvar" for b in wordnet._morphy(word, pos)} - {word}
    return not any(
        name == base
        for base in bases
        for synset in wordnet.synsets(base)
        for name in synset.lemma_names()
    )


def read_glove_vocab(path: Path) -> dict:
    """Word -> frequency rank (GloVe lists words most frequent first)."""
    vocab = {}
    with open(path, encoding="utf-8") as fh:
        for rank, line in enumerate(fh):
            vocab[line[: line.index(" ")]] = rank
    return vocab


def build_word_forms(guesses: set, glove: dict) -> dict:
    """Map each real (GloVe) plural or verb form that isn't a guess word to
    its base. When several bases fit ("hoping": hop or hope), pick the most
    frequent one."""
    forms = {}
    for base in guesses:
        for form in inflections(base):
            if form in guesses or form not in glove:
                continue
            if not GUESS_PATTERN.fullmatch(form):
                continue
            current = forms.get(form)
            if current is None or glove[base] < glove[current]:
                forms[form] = base
    return forms


def read_blocklist(path: Path) -> set:
    words = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            word = line.split("#", 1)[0].strip().lower()
            if word:
                words.add(word)
    return words


def is_inflected(word: str) -> bool:
    """True for a form of another word ("skidded", "cats") that WordNet
    doesn't list as a word of its own ("fishing" and "glasses" it does)."""
    lemmas = {lemma.name().lower() for s in wordnet.synsets(word) for lemma in s.lemmas()}
    if word in lemmas:
        return False
    return any(base != word for pos in "nvar" for base in wordnet._morphy(word, pos))


def singular_forms(word: str) -> list:
    """Possible singulars of a regular English plural."""
    forms = []
    if word.endswith("ies"):
        forms.append(word[:-3] + "y")
    if word.endswith("es"):
        forms.append(word[:-2])
    if word.endswith("s") and not word.endswith("ss"):
        forms.append(word[:-1])
    return forms


def build():
    for path in (RATINGS_PATH, GLOVE_PATH, BLOCKLIST_PATH, PROPER_NOUNS_PATH):
        if not path.exists():
            sys.exit(f"Missing input: {path}")

    print(f"Reading GloVe vocabulary from {GLOVE_PATH.name} ...")
    glove = read_glove_vocab(GLOVE_PATH)
    blocklist = read_blocklist(BLOCKLIST_PATH)
    listed_proper_nouns = read_blocklist(PROPER_NOUNS_PATH)

    with open(RATINGS_PATH, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    guesses = set()
    proper_nouns = set()
    nouns = set()
    hint_words = set()
    for row in rows:
        word = row["Word"].strip().lower()
        if row["Bigram"] != "0" or not GUESS_PATTERN.fullmatch(word):
            continue
        if word not in glove:
            continue
        # Not the dataset's "Name" tag: it also marks ordinary words that are
        # often capitalised in subtitles ("daisy", "crane").
        if word in listed_proper_nouns or is_proper_noun(word):
            proper_nouns.add(word)
            continue
        guesses.add(word)
        if (
            float(row["Percent_known"]) >= HINT_MIN_PERCENT_KNOWN
            and int(row["SUBTLEX"]) >= HINT_MIN_SUBTLEX
            and not is_inflected(word)
        ):
            hint_words.add(word)
        if (
            row["Dom_Pos"] == "Noun"
            and word.isalpha()
            and float(row["Percent_known"]) >= MIN_PERCENT_KNOWN
            and float(row["Conc.M"]) >= MIN_CONCRETENESS
            and int(row["SUBTLEX"]) >= MIN_SUBTLEX
        ):
            nouns.add(word)

    # Drop "dogs" when "dog" is also a target, so answers are base forms.
    plurals = {
        w
        for w in nouns
        if w not in KEEP_PLURALS and any(s in nouns for s in singular_forms(w))
    }
    blocked = nouns & blocklist
    targets = nouns - plurals - blocked

    unused = blocklist - nouns
    if unused:
        print(f"Note: {len(unused)} blocklist words were not candidates anyway: "
              f"{', '.join(sorted(unused))}")

    word_forms = build_word_forms(guesses, glove)

    GUESS_OUT.write_text("\n".join(sorted(guesses)) + "\n", encoding="utf-8")
    TARGET_OUT.write_text("\n".join(sorted(targets)) + "\n", encoding="utf-8")
    HINT_OUT.write_text("\n".join(sorted(hint_words)) + "\n", encoding="utf-8")
    FORMS_OUT.write_text(
        "".join(f"{form}\t{base}\n" for form, base in sorted(word_forms.items())),
        encoding="utf-8",
    )

    print(f"Rows in ratings file:      {len(rows)}")
    print(f"Proper nouns left out:     {len(proper_nouns)}")
    print(f"Guess words:               {len(guesses)}  -> {GUESS_OUT.name}")
    print(f"Hint words:                {len(hint_words)}  -> {HINT_OUT.name}")
    print(f"Target candidates:         {len(nouns)}")
    print(f"  dropped as plurals:      {len(plurals)}")
    print(f"  dropped by blocklist:    {len(blocked)}")
    print(f"Target words:              {len(targets)}  -> {TARGET_OUT.name}")
    print(f"Extra word forms accepted: {len(word_forms)}  -> {FORMS_OUT.name}")


if __name__ == "__main__":
    build()
