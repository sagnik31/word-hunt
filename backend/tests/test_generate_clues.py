"""The clue generator's error handling, resuming and rules (no Ollama needed)."""

import json

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
    targets = tmp_path / "targets.txt"
    targets.write_text(WORD + "\n", encoding="utf-8")
    monkeypatch.setattr(gc, "TARGETS_PATH", targets)
    results = {WORD: {"passed": True, "clues": ["a", "b", "c"]}}

    monkeypatch.setattr(gc, "schedule_key", lambda: "wrong key")
    gc.export(results, clues, schedule)
    assert not clues.exists()

    monkeypatch.setattr(gc, "schedule_key", lambda: "right key")
    gc.export(results, clues, schedule)
    assert gc.json.loads(clues.read_text(encoding="utf-8")) == {gc.word_code(WORD, "right key"): ["a", "b", "c"]}


def test_export_leaves_out_words_that_arent_answers(tmp_path, monkeypatch):
    schedule = tmp_path / "schedule.txt"
    schedule.write_text(gc.word_code(WORD, "key") + "\n", encoding="utf-8")
    targets = tmp_path / "targets.txt"
    targets.write_text(WORD + "\n", encoding="utf-8")
    monkeypatch.setattr(gc, "TARGETS_PATH", targets)
    monkeypatch.setattr(gc, "schedule_key", lambda: "key")
    clues = tmp_path / "clues.json"
    results = {WORD: {"passed": True, "clues": ["a", "b", "c"]},
               "slowly": {"passed": True, "clues": ["d", "e", "f"]}}
    gc.export(results, clues, schedule)
    assert list(json.loads(clues.read_text(encoding="utf-8"))) == [gc.word_code(WORD, "key")]


@pytest.mark.parametrize("length, ok", [(gc.MAX_WORDS, True), (gc.MAX_WORDS + 1, False)])
def test_clue_length_matches_the_prompt(checker, length, ok):
    assert gc.MAX_WORDS == 15  # the writer's prompt says "at most 15 words"
    clue = " ".join(["walk"] * length)
    long_problems = [p for p in checker.rule_problems(WORD, [clue, WRITTEN["medium"], WRITTEN["strong"]])
                     if "longer" in p]
    assert not long_problems if ok else long_problems


# The run loop, with a fake entry maker instead of the models.

WORDS = ["slowly", "quickly", "gently"]


def _entry(passed=True):
    return {"passed": passed, "clues": ["a", "b", "c"], "reason": "ok", "kinds": [],
            "solver_ranks": [5, 3, 1], "attempts": 1, "tries": []}


def test_a_rerun_does_only_the_unfinished_words(tmp_path):
    report = tmp_path / "report.json"
    results = {"slowly": _entry()}
    gc.save(report, results)
    made = []
    gc.run(WORDS, results, report, lambda w: made.append(w) or _entry())
    assert made == ["quickly", "gently"]
    assert set(json.loads(report.read_text(encoding="utf-8"))) == set(WORDS)


def test_redo_keeps_the_old_entry_until_replaced(tmp_path):
    report = tmp_path / "report.json"
    results = {w: _entry(passed=False) for w in WORDS}
    gc.save(report, results)

    def make(word):
        if word == "quickly":
            raise KeyboardInterrupt
        return _entry()

    with pytest.raises(KeyboardInterrupt):
        gc.run(WORDS, results, report, make, redo=set(WORDS))
    saved = json.loads(report.read_text(encoding="utf-8"))
    assert set(saved) == set(WORDS)  # nothing lost
    assert saved["slowly"]["passed"] and not saved["quickly"]["passed"]


def test_a_stop_mid_word_leaves_the_report_intact(tmp_path):
    report = tmp_path / "report.json"
    results = {}

    def make(word):
        if word == "quickly":
            raise KeyboardInterrupt  # Ctrl+C while the models work on it
        return _entry()

    with pytest.raises(KeyboardInterrupt):
        gc.run(WORDS, results, report, make)
    assert json.loads(report.read_text(encoding="utf-8")).keys() == {"slowly"}


def test_a_crash_while_saving_keeps_the_old_report(tmp_path, monkeypatch):
    report = tmp_path / "report.json"
    gc.save(report, {"slowly": _entry()})
    before = report.read_text(encoding="utf-8")

    def broken_fsync(fd):
        raise KeyboardInterrupt  # stopped after writing the temp file, before the move

    monkeypatch.setattr(gc.os, "fsync", broken_fsync)
    with pytest.raises(KeyboardInterrupt):
        gc.save(report, {"slowly": _entry(), "quickly": _entry()})
    assert report.read_text(encoding="utf-8") == before


def test_a_failing_word_is_logged_and_skipped(tmp_path):
    report = tmp_path / "report.json"
    results = {}

    def make(word):
        if word == "slowly":
            raise RuntimeError("model went away")
        if word == "quickly":
            return {"error": True, "attempts": 4, "reason": "no try finished"}
        return _entry()

    errors = gc.run(WORDS, results, report, make)
    assert errors == 2
    assert list(json.loads(report.read_text(encoding="utf-8"))) == ["gently"]
    log = gc.log_path(report).read_text(encoding="utf-8")
    assert "ERROR slowly: RuntimeError: model went away" in log
    assert "ERROR quickly" in log


def test_the_run_stops_when_every_word_errors(tmp_path):
    report = tmp_path / "report.json"
    words = [f"word{i}" for i in range(gc.MAX_ERRORS_IN_A_ROW + 3)]
    made = []
    gc.run(words, {}, report, lambda w: made.append(w) or {"error": True, "reason": "down"})
    assert len(made) == gc.MAX_ERRORS_IN_A_ROW


def test_progress_and_summary_name_no_words(tmp_path, capsys):
    report = tmp_path / "report.json"
    results = {}
    gc.run(WORDS, results, report, lambda w: _entry(passed=w != "gently"))
    shown = capsys.readouterr().out + gc.summary(results, WORDS)
    assert "[3/3] FAIL" in shown and "Passed: 2/3" in shown
    assert not any(w in shown for w in WORDS)


def test_a_run_never_exports(tmp_path, monkeypatch):
    words = tmp_path / "words.txt"
    words.write_text("\n".join(WORDS) + "\n", encoding="utf-8")
    report = tmp_path / "report.json"
    monkeypatch.setattr(gc, "WordGameEngine", lambda: None)
    monkeypatch.setattr(gc, "Checker", lambda engine: None)
    monkeypatch.setattr(gc, "familiar_words", set)
    monkeypatch.setattr(gc, "make_entry", lambda *args: _entry())
    monkeypatch.setattr(gc, "export", lambda *args: pytest.fail("a run exported"))
    gc.main(["--words", str(words), "--report", str(report)])
    assert set(json.loads(report.read_text(encoding="utf-8"))) == set(WORDS)


def test_the_prompt_keeps_the_medium_clue_to_the_meaning():
    prompt, _ = gc.writer_prompt(WORD, WRITTEN["meaning"], [])
    assert "Every fact in the medium clue must be in the meaning" in prompt
    assert f"at most {gc.MAX_WORDS} words" in prompt


@pytest.mark.parametrize("medium, flagged", [
    ("It moves at a fast pace.", False),         # "fast" comes from the meaning
    ("Sprinters wear red shoes for it.", True),  # nothing from the meaning
    ("It is a kind of thing.", False),           # filler only: nothing to judge
])
def test_review_first_marks_medium_clues_that_leave_the_meaning(medium, flagged):
    assert gc.review_first(WORD, "at a fast speed", medium) is flagged


class FakeResponse:
    def __init__(self, prompt_tokens):
        self.body = {"prompt_eval_count": prompt_tokens, "message": {"content": "{}"}}

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


@pytest.mark.parametrize("prompt_tokens, fits", [(1500, True), (gc.NUM_CTX - 100, False)])
def test_chat_caps_the_context_and_refuses_a_prompt_that_would_not_fit(monkeypatch, prompt_tokens, fits):
    sent = {}

    def fake_post(url, json, timeout):
        sent.update(json)
        return FakeResponse(prompt_tokens)
    monkeypatch.setattr(gc.requests, "post", fake_post)
    if fits:
        assert gc.chat("m", [], {}, 0.0) == {}
    else:
        with pytest.raises(RuntimeError):
            gc.chat("m", [], {}, 0.0)
    assert sent["options"]["num_ctx"] == gc.NUM_CTX


def test_each_redo_round_uses_a_new_seed(tmp_path, monkeypatch):
    words = tmp_path / "words.txt"
    words.write_text("\n".join(WORDS) + "\n", encoding="utf-8")
    report = tmp_path / "report.json"
    seeds = []

    def failing_entry(*args):
        seeds.append(gc.seed)
        return _entry(passed=False)
    monkeypatch.setattr(gc, "WordGameEngine", lambda: None)
    monkeypatch.setattr(gc, "Checker", lambda engine: None)
    monkeypatch.setattr(gc, "familiar_words", set)
    monkeypatch.setattr(gc, "make_entry", failing_entry)
    monkeypatch.setattr(gc, "seed", gc.OLLAMA_SEED)
    argv = ["--words", str(words), "--report", str(report)]
    gc.main(argv)
    gc.main(argv + ["--redo-failed"])
    gc.main(argv + ["--redo-failed"])
    n = len(WORDS)
    assert seeds == [gc.OLLAMA_SEED] * n + [gc.OLLAMA_SEED + 1] * n + [gc.OLLAMA_SEED + 2] * n
    assert {e["round"] for e in json.loads(report.read_text(encoding="utf-8")).values()} == {2}
