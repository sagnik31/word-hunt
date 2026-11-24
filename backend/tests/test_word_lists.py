"""Checks on the generated word lists (see backend/scripts/build_word_lists.py)."""

import pytest

from backend.config import DATA_DIR

# Hard requirement: proper nouns can never be guessed or be the answer.
PROPER_NOUNS = {
    "monday", "sunday", "january", "december", "christmas", "halloween",
    "ramadan", "muslim", "hindu", "facebook", "google", "iphone", "kleenex",
    "walmart", "venus", "olympics", "africa", "america", "london", "paris",
    "france", "india", "david", "mary",
}


def _words(name):
    return (DATA_DIR / name).read_text(encoding="utf-8").splitlines()


def _forms():
    return dict(line.split("\t") for line in _words("word_forms.txt"))


def test_no_proper_nouns_anywhere():
    forms = _forms()
    for name in ("guess_words.txt", "target_words.txt"):
        assert not PROPER_NOUNS & set(_words(name)), name
    assert not PROPER_NOUNS & set(forms)
    assert not PROPER_NOUNS & set(forms.values())
    assert "mondays" not in forms


def test_ordinary_words_that_look_like_names_are_kept():
    guesses = set(_words("guess_words.txt"))
    assert {"daisy", "crane", "robin", "china", "mark", "it", "fungi"} <= guesses


def test_lists_are_clean():
    guesses = _words("guess_words.txt")
    targets = _words("target_words.txt")
    for words in (guesses, targets):
        assert words == sorted(set(words))
        assert all(w and " " not in w for w in words)
    assert set(targets) <= set(guesses)


def test_word_forms_point_at_guess_words():
    guesses = set(_words("guess_words.txt"))
    forms = _forms()
    assert not set(forms) & guesses
    assert set(forms.values()) <= guesses


def test_word_forms_cover_irregular_comparative_and_british_forms():
    forms = _forms()
    expected = {
        "became": "become",  # irregular verb
        "genii": "genius",  # irregular plural
        "tradesmen": "tradesman",  # "-men" plural
        "largest": "large",  # superlative
        "sadder": "sad",  # comparative, doubled consonant
        "colour": "color",  # British spellings, and their forms
        "favour": "favor",
        "centre": "center",
        "centres": "center",
    }
    assert {form: forms.get(form) for form in expected} == expected
    # Narrow rules: other words, and made-up forms, aren't matched.
    assert not {"lama", "loess", "outre", "humen", "iner", "aller"} & set(forms)
    assert forms["tilling"] == "till"  # not "tile"


def test_irregular_plurals_point_at_guess_words():
    guesses = set(_words("guess_words.txt"))
    pairs = [line.split("\t") for line in _words("irregular_plurals.txt")]
    assert {base for _, base in pairs} <= guesses
    assert ["larvae", "larva"] in pairs and ["stimuli", "stimulus"] in pairs
    # WordNet pairs these too, but they're words of their own.
    assert not {"cola", "dive", "crying"} & {form for form, _ in pairs}
    assert not PROPER_NOUNS & {w for pair in pairs for w in pair}


def test_answers_are_the_hand_picked_list():
    picked = {
        line.split("#", 1)[0].strip()
        for line in _words("answer_list.txt")
    } - {""}
    assert set(_words("target_words.txt")) == picked


def test_hint_words_are_clean_guess_words_with_no_proper_nouns():
    # A hint reveals one of these words on screen, so the proper-noun rule
    # applies here too.
    hints = _words("hint_words.txt")
    assert hints == sorted(set(hints))
    assert set(hints) <= set(_words("guess_words.txt"))
    assert not PROPER_NOUNS & set(hints)
    listed = {line.split("#", 1)[0].strip() for line in _words("proper_nouns.txt")} - {""}
    assert not listed & set(hints)
    # Only ordinary words: no inflected forms such as "skidded".
    assert "skidded" not in hints and {"fishing", "glasses"} <= set(hints)


def test_shipped_clues_are_complete_and_give_no_day_away():
    # Checked without the key, so no answer is decoded: one set of three short
    # clues per puzzle, under codes the schedule doesn't use, in code order.
    import json
    import re

    clues = json.loads((DATA_DIR / "clues.json").read_text(encoding="utf-8"))
    codes = {line.strip() for line in _words("daily_schedule.txt") if line.strip() and not line.startswith("#")}
    word = re.compile(r"[A-Za-z][A-Za-z'-]*")
    # Counts only: a failure must never print a clue (it would spoil a puzzle).
    assert len(clues) == len(codes)
    shared = len(set(clues) & codes)
    unsorted = sum(a > b for a, b in zip(clues, list(clues)[1:]))
    malformed = sum(
        not (isinstance(v, list) and len(v) == 3 and all(isinstance(c, str) and c.strip() for c in v))
        for v in clues.values()
    )
    too_long = sum(
        len(word.findall(c)) > 15  # MAX_WORDS in generate_clues.py
        for v in clues.values() if isinstance(v, list) for c in v if isinstance(c, str)
    )
    assert (shared, unsorted, malformed, too_long) == (0, 0, 0, 0)


def test_word_forms_hold_no_names():
    forms = _forms()
    names = {"dorking", "golding", "harding", "lessing", "maritimes", "ming", "redding", "rockies", "rogers"}
    assert not names & set(forms)


def test_word_forms_pass_the_builders_own_name_check():
    # Needs WordNet, so it's skipped in CI.
    pytest.importorskip("nltk")
    from backend.scripts.build_word_lists import is_proper_noun

    try:
        is_proper_noun("apple")
    except LookupError:
        pytest.skip("WordNet data isn't installed")
    assert sum(is_proper_noun(form) for form in _forms()) == 0
