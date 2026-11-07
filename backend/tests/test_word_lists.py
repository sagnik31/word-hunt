"""Checks on the generated word lists (see backend/scripts/build_word_lists.py)."""

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
