"""The clue generator's error handling and rules (no Ollama needed)."""

import pytest

pytest.importorskip("nltk")
pytest.importorskip("requests")

from backend.game import WordGameEngine  # noqa: E402
from backend.scripts import generate_clues as gc  # noqa: E402

# An adverb: it has no noun sense, so no WordNet category, and it's never
# an answer (answers are nouns).
WORD = "quickly"
WRITTEN = {
    "meaning": "at a fast speed",
    "strong": "How a sprinter runs a race.",
    "medium": "In a short amount of time.",
    "vague": "A way of doing something.",
}


@pytest.fixture(scope="module")
def checker():
    return gc.Checker(WordGameEngine())


def _name_problems(checker, first_clue):
    clues = [first_clue, WRITTEN["medium"], WRITTEN["strong"]]
    return [p for p in checker.rule_problems(WORD, clues) if "name" in p]


@pytest.mark.parametrize("clue", ["Paris has plenty of this.", "Monday's way of doing things."])
def test_a_name_as_the_first_word_is_caught(checker, clue):
    assert _name_problems(checker, clue)


@pytest.mark.parametrize(
    "clue", ["Often how a sprinter moves.", "It describes a way of moving.", "TV hosts speak like this."]
)
def test_ordinary_first_words_pass(checker, clue):
    assert not _name_problems(checker, clue)


def test_a_checker_error_doesnt_stop_the_run(checker, monkeypatch):
    def broken_ask(*args, **kwargs):
        raise gc.requests.ConnectionError("Ollama went away")

    monkeypatch.setattr(gc, "chat", lambda *args, **kwargs: dict(WRITTEN))
    monkeypatch.setattr(gc, "ask", broken_ask)
    entry = gc.make_entry(checker, WORD, attempts=2, familiar=set())
    assert entry["passed"] is False
    assert entry["attempts"] == 2
    assert all("check failed" in t["error"] for t in entry["tries"])


def test_export_refuses_a_key_that_doesnt_decode_the_schedule(tmp_path, monkeypatch):
    schedule = tmp_path / "schedule.txt"
    schedule.write_text(gc.word_code(WORD, "right key") + "\n", encoding="utf-8")
    clues = tmp_path / "clues.json"
    results = {WORD: {"passed": True, "clues": ["a", "b", "c"]}}

    monkeypatch.setattr(gc, "schedule_key", lambda: "wrong key")
    gc.export(results, clues, schedule)
    assert not clues.exists()

    monkeypatch.setattr(gc, "schedule_key", lambda: "right key")
    gc.export(results, clues, schedule)
    assert gc.json.loads(clues.read_text(encoding="utf-8")) == {gc.word_code(WORD, "right key"): ["a", "b", "c"]}
