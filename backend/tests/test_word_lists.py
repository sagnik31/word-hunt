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
