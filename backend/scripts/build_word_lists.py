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
  - data/word_forms.txt    "form<TAB>base" lines: plurals, verb forms,
                           comparatives and British spellings that aren't
                           guess words themselves ("cats" -> "cat",
                           "colour" -> "color")
  - data/hint_words.txt    guess words ordinary enough for a Hint to reveal
  - data/irregular_plurals.txt  "form<TAB>base" irregular plurals ("octopi"),
                           so a plural of the answer wins even when it's a
                           guess word of its own
"""

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.utils.word_forms import (  # noqa: E402
    KEEP_PLURALS,
    adjective_forms,
    inflections,
    singular_forms,
)
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
PLURALS_OUT = DATA / "irregular_plurals.txt"

# Target filters (agreed with the owner: "Option A", about 2,900 candidates).
MIN_PERCENT_KNOWN = 0.95  # share of raters who knew the word
MIN_CONCRETENESS = 4.0  # 1 = abstract, 5 = concrete
MIN_SUBTLEX = 50  # subtitle frequency count, drops rare words

# Hint words: a Hint only reveals ordinary words, not rare or inflected
# neighbours such as "marshy" (subtitle count 3) or "skidded" (a verb form).
HINT_MIN_PERCENT_KNOWN = 0.95
HINT_MIN_SUBTLEX = 10

# British spellings of guess words ("colour" -> "color"). Each rule rewrites
# part of an American word or one of its forms; the result counts only if
# it's in GloVe, WordNet knows it as a lowercase word and it isn't a guess
# word itself. The rules are narrow on purpose: wider ones matched other
# words ("lama" isn't "llama", "barbel" isn't "barbell").
UK_SPELLING_RULES = [
    (r"or(?=\b|s\b|ed\b|ing\b|ful)", "our"),  # color -> colour, colourful
    (r"(?<=[tbgcv])er(?=\b|s\b|ed\b)", "re"),  # center -> centre, fibres
    (r"iz(?=e|a|i)", "is"),  # organize -> organise, organisation
    (r"yz(?=e|i)", "ys"),  # analyze -> analyse
    (r"ense(?=\b|s\b)", "ence"),  # defense -> defence
    (r"(?<=.)e(?=..)", "ae"),  # pediatric -> paediatric
    (r"(?<=.)e(?=..)", "oe"),  # fetus -> foetus
    (r"ll(?=ment|ful)", "l"),  # enrollment -> enrolment, skillful -> skilful
    (r"(?<=...[iao])ll(?=\b|s\b)", "l"),  # fulfill -> fulfil, installs -> instals
]
# "traveled" -> "travelled": only after a guess word ending in one "l", so
# "tiling" (from "tile") never becomes "tilling".
UK_DOUBLE_L_SUFFIXES = ("ed", "ing", "er", "ers")
UK_SPELLING_SKIP = {"outre", "loess"}  # words of their own, not "outer", "less"
# British spellings the rules can't reach, with the American guess word.
UK_SPELLINGS = {
    "aeroplane": "airplane", "ageing": "aging", "aluminium": "aluminum",
    "artefact": "artifact", "cheque": "check", "chilli": "chili",
    "cosy": "cozy", "gaol": "jail", "jewellery": "jewelry",
    "judgement": "judgment", "kerb": "curb", "manoeuvre": "maneuver",
    "mould": "mold", "practise": "practice", "programme": "program",
    "pyjama": "pajama", "pyjamas": "pajamas", "sceptic": "skeptic",
    "smoulder": "smolder", "storey": "story", "tyre": "tire",
    "yoghurt": "yogurt",
}

# Usual parts of speech (the dataset's Dom_Pos) that never take "-er" or
# "-est", so "in" doesn't give "iner" and "all" doesn't give "aller".
NOT_COMPARABLE_POS = {
    "Article", "Conjunction", "Determiner", "Interjection", "Letter", "Name",
    "Number", "Preposition", "Pronoun",
}

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


def wordnet_knows(word: str) -> bool:
    """True when WordNet has the word in lowercase, or as a form of one."""
    if any(lemma.name() == word for s in wordnet.synsets(word) for lemma in s.lemmas()):
        return True
    return any(
        base != word
        for pos in "nvar"
        for base in wordnet._morphy(word, pos)
    )


def build_word_forms(guesses: set, glove: dict, comparable: set) -> dict:
    """Map each real (GloVe) form that isn't a guess word to its base:
    plurals and verb forms, irregular forms ("mice", "became", "worse"),
    comparatives ("bigger"), "-men" plurals and British spellings ("colour",
    "centres"). When several bases fit ("hoping": hop or hope), pick the
    most frequent one. `comparable` holds the words that may take "-er" and
    "-est"."""
    forms = {}

    def add(form, base):
        if form in guesses or form not in glove or not GUESS_PATTERN.fullmatch(form):
            return
        current = forms.get(form)
        if current is None or glove[base] < glove[current]:
            forms[form] = base

    for base in guesses:
        for form in inflections(base):
            add(form, base)
        # Comparatives only where WordNet agrees, and not of participles or
        # closed-class words ("mader", "aller").
        if base in comparable:
            for form in adjective_forms(base):
                if form in glove and base in wordnet._morphy(form, "a"):
                    add(form, base)
        # "fisherman" -> "fishermen", but not "human" -> "humen".
        head = base[:-3]
        if base.endswith("man") and (head in guesses or any(s in guesses for s in singular_forms(head))):
            add(head + "men", base)
    # Irregular forms from WordNet's exception lists ("larvae", "blew").
    for form, base in wordnet_exceptions("nva", guesses):
        add(form, base)

    # British spellings, of base words and of the forms found so far.
    spellings = {}
    # Sorted, so the first base found for a spelling is the same every run.
    for form, base in sorted([(g, g) for g in guesses] + list(forms.items())):
        for pattern, replacement in UK_SPELLING_RULES:
            for match in re.finditer(pattern, form):
                uk = form[: match.start()] + replacement + form[match.end():]
                spellings.setdefault(uk, base)
        for suffix in UK_DOUBLE_L_SUFFIXES:
            stem = form[: -len(suffix)]
            if form.endswith(suffix) and stem in guesses and stem.endswith("l") and not stem.endswith("ll"):
                spellings.setdefault(stem + "l" + suffix, base)
    for uk, us in UK_SPELLINGS.items():
        if us in guesses:
            for form in sorted({uk} | inflections(uk)):
                spellings.setdefault(form, us)
    for uk, base in spellings.items():
        if (
            uk not in forms
            and uk not in UK_SPELLING_SKIP
            and uk in glove
            and (uk in UK_SPELLINGS or wordnet_knows(uk))
            and not is_proper_noun(uk)
        ):
            add(uk, base)
    return forms


def build_irregular_plurals(guesses: set, glove: dict) -> dict:
    """Irregular plurals WordNet lists ("octopi", "larvae"), base -> forms.
    Unlike word_forms.txt this keeps plurals that are guess words too, so
    the game can let them win when their singular is the answer."""
    plurals = {}
    for form, base in wordnet_exceptions("n", guesses):
        if form in glove and GUESS_PATTERN.fullmatch(form):
            plurals.setdefault(base, set()).add(form)
    return plurals


def wordnet_exceptions(parts_of_speech: str, guesses: set):
    """(form, base) pairs from WordNet's lists of irregular forms, for bases
    that are guess words. Forms WordNet also knows as words of their own are
    left out: the lists pair "cola" with "colon" and "dive" with "diva"."""
    for pos in parts_of_speech:
        for form, bases in sorted(wordnet._exception_map[pos].items()):
            if any(lemma.name() == form for s in wordnet.synsets(form) for lemma in s.lemmas()):
                continue
            for base in bases:
                if base in guesses and base != form:
                    yield form, base


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
    comparable = set()  # words that may take "-er" and "-est"
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
            len(word) >= 3
            and not word.endswith(("ed", "ing"))
            and row["Dom_Pos"] not in NOT_COMPARABLE_POS
            and not is_inflected(word)  # "made" doesn't give "mader"
        ):
            comparable.add(word)
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

    word_forms = build_word_forms(guesses, glove, comparable)
    irregular_plurals = build_irregular_plurals(guesses, glove)

    GUESS_OUT.write_text("\n".join(sorted(guesses)) + "\n", encoding="utf-8")
    TARGET_OUT.write_text("\n".join(sorted(targets)) + "\n", encoding="utf-8")
    HINT_OUT.write_text("\n".join(sorted(hint_words)) + "\n", encoding="utf-8")
    FORMS_OUT.write_text(
        "".join(f"{form}\t{base}\n" for form, base in sorted(word_forms.items())),
        encoding="utf-8",
    )
    PLURALS_OUT.write_text(
        "".join(
            f"{form}\t{base}\n"
            for base, forms in sorted(irregular_plurals.items())
            for form in sorted(forms)
        ),
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
    print(f"Irregular plurals:         {sum(map(len, irregular_plurals.values()))}  -> {PLURALS_OUT.name}")


if __name__ == "__main__":
    build()
