"""
Write three clues per answer word with a local Ollama model, then check them.

Clues go from vague to strong and describe the word's meaning only. The
writer is given a dictionary meaning (WordNet) so it doesn't have to recall
the facts itself. Of a word's senses it gets the one closest to the word's
nearest neighbours in the game's embeddings, so the clues describe the same
meaning the hot-and-cold ranks are built on ("washer" the machine, not the
person or the seal). It writes the meaning and the strong clue first, then
the medium and vague ones, so all three stay on that sense.

Each set is checked three times:

1. Rules: no answer word or a word built from it, no talk of letters,
   spelling or sounds, no names, at most MAX_WORDS words per clue.
2. Facts: a second model, also given the dictionary meaning, checks each
   clue for errors. A vague clue that fits other things too is fine.
3. Solver: the second model sees the clues one at a time (clue 1, then
   1-2, then 1-3, as a player would) and makes 3 guesses each time. Each
   guess is ranked against the answer exactly as the game ranks a player's
   guess. The strong clue must bring the solver to rank STRONG_MAX_RANK or
   better, and none of the 3 guesses from the vague clue alone may be the
   answer.

When a set fails, the writer is told exactly what went wrong (which rule,
which clue was judged wrong and why, what the solver guessed) and asked to
fix it, up to --attempts tries in all. The best attempt is kept and marked as
failed if none passed. Every attempt's details go to the report (git-ignored,
since it names the words), saved after every word so an interrupted run picks
up where it stopped. At the end the passing clues are written to
data/clues.json, keyed by the schedule codes so the public file doesn't say
which clues belong to which word. That step needs the schedule key.

    python backend/scripts/generate_clues.py --sample 30 --report <file>   # pilot
    python backend/scripts/generate_clues.py                               # all
    python backend/scripts/generate_clues.py --export-only                 # rewrite clues.json
"""

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

import numpy as np
import requests
from nltk.corpus import wordnet as wn

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.config import CLUES_PATH, schedule_key  # noqa: E402
from backend.daily import word_code  # noqa: E402
from backend.game import WordGameEngine  # noqa: E402
from backend.utils.word_forms import plural_forms  # noqa: E402

OLLAMA_URL = "http://localhost:11434/api/chat"
WRITER_MODEL = "qwen3.5:4b"
SOLVER_MODEL = "gemma4:e2b"
CHECKER_MODEL = "gemma4:e2b"

TARGETS_PATH = ROOT / "data" / "target_words.txt"
DEFAULT_REPORT = ROOT / "data" / "raw" / "clue_report.json"

MAX_WORDS = 16
STRONG_MAX_RANK = 10  # "Boiling"
MAX_SENSES = 6
NEIGHBOURS = 25  # how many nearest words show which sense the embeddings mean
SENSE_MARGIN = 0.05  # how much closer a less frequent sense must be to be picked
STOPWORDS = set(
    "a an the of or and to in on for by with as at from that which is are be its it any "
    "used into out than can one some who what this these those such".split()
)

SYSTEM_PROMPT = (
    "You write clues for a daily word-guessing game. A player who is stuck "
    "unlocks one clue at a time, so the clues go from vague to strong. "
    "You only state facts you are sure of."
)

PROMPT = """Secret word: "{word}"
Meaning to use: {sense}

Write 3 clues for "{word}" in this meaning only. Fill in the fields in this order:
- meaning: the meaning above in your own plain words. All three clues must be about it.
- strong: the clearest description of that meaning, so a player names this exact word and not a close relative of it.
- medium: one telling detail, true of the word, that narrows it to a handful of words.
- vague: only the broad category, such as "something found in a kitchen" or "a kind of worker". Dozens of words should fit it. Use no detail from the other two clues.

Rules for the three clues:
- Each is one plain sentence of at most 15 words.
- Only state what is plainly true of this meaning. If you are not sure of a fact, leave it out.
- Never use the secret word or any word made from it (plural, verb form, compound).
- Never mention letters, spelling, word length, sounds or rhymes.
- No names of people, places, countries, brands, books or films.

Example for the secret word "kettle":
{{"meaning": "a pot with a spout and handle for boiling water", "strong": "You fill it with water and heat it to make tea.", "medium": "It gets noisy just as it is ready.", "vague": "You will find this in most kitchens."}}"""

FACT_PROMPT = """Word: "{word}" (meaning: {meaning})
Clue: "{clue}"

Check the clue for factual errors about this word.
- A vague clue that also fits many other things is fine. Only judge whether what it says is correct.
- It is wrong if any part is false, if it describes something else (a related object, place or person), or if it is about a different meaning of the word.

First say in one short sentence what the clue claims and whether that is right for "{word}". Then give the verdict."""

SOLVER_PROMPT = """Guess the secret English word from these clues:
{clues}

The secret word is a common noun, verb or adjective. Reply with your 3 best single-word guesses, best first."""

CLUES_SCHEMA = {
    "type": "object",
    "properties": {
        "meaning": {"type": "string"},
        "strong": {"type": "string"},
        "medium": {"type": "string"},
        "vague": {"type": "string"},
    },
    "required": ["meaning", "strong", "medium", "vague"],
}
FACT_SCHEMA = {
    "type": "object",
    "properties": {"reason": {"type": "string"}, "correct": {"type": "boolean"}},
    "required": ["reason", "correct"],
}
GUESSES_SCHEMA = {
    "type": "object",
    "properties": {
        "guesses": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3}
    },
    "required": ["guesses"],
}

CLUE_NAMES = ("vague", "medium", "strong")

# Talk about the word's form rather than its meaning.
FORM_TALK = re.compile(
    r"\b(letters?|spell(?:s|ed|ing)?|syllables?|rhym\w*|vowels?|consonants?|anagram\w*|"
    r"(?:starts?|begins?|ends?) with|sounds? like|initials?)\b"
    r"|['\"‘“][a-z]['\"’”]",
    re.IGNORECASE,
)
WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")


def chat(model, messages, schema, temperature, num_predict=200):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "messages": messages,
            "format": schema,
            "think": False,
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": temperature, "num_predict": num_predict},
        },
        timeout=300,
    )
    response.raise_for_status()
    return json.loads(response.json()["message"]["content"])


def ask(model, prompt, schema, temperature=0.0):
    return chat(model, [{"role": "user", "content": prompt}], schema, temperature)


def bag_vector(engine, words, skip):
    """Mean unit vector of the content words in words (None if none known)."""
    idx = [engine.word_index[w] for w in words
           if w in engine.word_index and w not in STOPWORDS and w != skip]
    if not idx:
        return None
    v = engine.vectors[idx].mean(axis=0)
    return v / np.linalg.norm(v)


def sense_words(synset):
    """Words that describe a sense: its gloss, synonyms and parent terms."""
    words = re.findall(r"[a-z]+", synset.definition().lower())
    lemmas = list(synset.lemmas())
    for parent in synset.hypernyms():
        lemmas += parent.lemmas()
    return words + [part for lemma in lemmas for part in lemma.name().lower().split("_")]


def pick_sense(engine, word):
    """The WordNet noun sense closest to the word's neighbours in the embeddings.

    Named things (a sense that is an instance, such as a person) and senses
    whose definition names something ("the United States head of state") are
    skipped, since clues may not contain names. Falls back to the word itself
    when WordNet has no usable noun sense.
    """
    def named(synset):
        return any(t.lower() != word for t in re.findall(r"\b[A-Z][a-z]+", synset.definition()))

    synsets = [s for s in wn.synsets(word, pos="n")[:MAX_SENSES] if not s.instance_hypernyms()]
    synsets = [s for s in synsets if not named(s)] or synsets  # "Mexican liquor" is all there is
    if not synsets:
        return word
    ranking = engine.ranking(word)
    centre = bag_vector(engine, [ranking.neighbour(i)[0] for i in range(NEIGHBOURS)], word)
    if centre is None:
        return synsets[0].definition()

    def closeness(synset):
        v = bag_vector(engine, sense_words(synset), word)
        return -1.0 if v is None else float(v @ centre)

    # WordNet lists the most frequent sense first, so a later sense has to be
    # clearly closer to win ("gift": a present, not the act of giving).
    best, best_score = synsets[0], closeness(synsets[0])
    for synset in synsets[1:]:
        score = closeness(synset)
        if score > best_score + SENSE_MARGIN:
            best, best_score = synset, score
    return best.definition()


def shares_stem(token, word):
    """True when token looks built from word ("accelerate" for "accelerator")."""
    if len(word) < 5 or len(token) < 5:
        return False
    common = 0
    for a, b in zip(token, word):
        if a != b:
            break
        common += 1
    return common >= 5 and common >= min(len(token), len(word)) - 2


class Checker:
    def __init__(self, engine):
        self.engine = engine
        self.base_of = engine.word_forms  # inflected form -> base word

    def forms(self, word):
        forms = {word} | plural_forms(word)
        forms |= {f for f, base in self.base_of.items() if base == word}
        return forms

    def rule_problems(self, word, clues):
        """Plain-language problems, phrased so they can go back to the writer."""
        if len(clues) != 3 or any(not isinstance(c, str) or not c.strip() for c in clues):
            return ["Write all three clues."]
        problems = []
        forms = self.forms(word)
        for name, clue in zip(CLUE_NAMES, clues):
            tokens = WORD.findall(clue)
            lowered = [t.lower().strip("'-") for t in tokens]
            # Also catches compounds such as "teapot" for "pot".
            used = [t for t, low in zip(tokens, lowered)
                    if low in forms or shares_stem(low, word) or (len(word) >= 4 and word in low)]
            if used:
                problems.append(f'The {name} clue uses "{used[0]}", which gives away the word.')
            if FORM_TALK.search(clue):
                problems.append(f"The {name} clue talks about letters or sounds.")
            if len(tokens) > MAX_WORDS:
                problems.append(f"The {name} clue is longer than 15 words.")
            # A capital after the first word suggests a name. "I" and
            # abbreviations such as "TV" or "IDs" are fine.
            names = [t for t in tokens[1:] if t[0].isupper() and not t.rstrip("s").isupper()]
            if names:
                problems.append(f'The {name} clue contains the name "{names[0]}".')
        return problems

    def false_clues(self, word, meaning, clues):
        """(clue name, reason) for each clue the checker model says is wrong."""
        wrong = []
        for name, clue in zip(CLUE_NAMES, clues):
            answer = ask(CHECKER_MODEL, FACT_PROMPT.format(word=word, meaning=meaning, clue=clue),
                         FACT_SCHEMA)
            if not answer.get("correct", False):
                wrong.append((name, answer.get("reason", "")))
        return wrong

    def rank_of(self, word, guess):
        if not isinstance(guess, str):
            return None
        result = self.engine.guess(word, guess.strip().lower())
        return result["rank"] if result["valid"] else None

    def best_rank(self, word, guesses):
        ranks = [r for r in (self.rank_of(word, g) for g in guesses) if r is not None]
        return min(ranks) if ranks else None

    def solve(self, word, clues):
        """Best rank the solver reaches after clue 1, clues 1-2 and clues 1-3."""
        ranks, guesses_seen = [], []
        for shown in range(1, 4):
            listed = "\n".join(f"{i}. {c}" for i, c in enumerate(clues[:shown], start=1))
            guesses = ask(SOLVER_MODEL, SOLVER_PROMPT.format(clues=listed), GUESSES_SCHEMA)
            guesses = [g for g in guesses.get("guesses", []) if isinstance(g, str)]
            guesses_seen.append(guesses)
            ranks.append(self.best_rank(word, guesses))
        return ranks, guesses_seen


def solver_problems(word, ranks, guesses):
    """Why the solver run fails, as feedback for the writer (empty = pass)."""
    problems = []
    if ranks[0] == 1:
        problems.append(
            f'From the vague clue alone a player guessed {", ".join(guesses[0])}, so it gives the '
            f'word away. Make the vague clue broader: only the general category.')
    if ranks[2] is None or ranks[2] > STRONG_MAX_RANK:
        problems.append(
            f'With all three clues a player guessed {", ".join(guesses[2])}, not "{word}". Rewrite '
            f'the strong clue so it clearly fits "{word}" and rules out those words.')
    return problems


def score(entry):
    """Order attempts: passing first, then by how close the strong clue got."""
    r3 = entry["solver_ranks"][2] if entry["solver_ranks"] else None
    return (entry["passed"], bool(entry["solver_ranks"]), -(r3 or 10**6))


def check(checker, word, sense, written):
    """Run all three checks. Returns (clues, problems, ranks, guesses)."""
    clues = [str(written.get(name, "")).strip() for name in CLUE_NAMES]
    problems = checker.rule_problems(word, clues)
    if problems:
        return clues, problems, [], []
    problems = [f'The {name} clue was judged wrong: {reason.strip().rstrip(".")}. '
                'Replace it with something plainly true.'
                for name, reason in checker.false_clues(word, sense, clues)]
    if problems:
        return clues, problems, [], []
    ranks, guesses = checker.solve(word, clues)
    return clues, solver_problems(word, ranks, guesses), ranks, guesses


def make_entry(checker, word, attempts):
    """Write clues, then revise them with feedback until they pass or tries run out."""
    sense = pick_sense(checker.engine, word)
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": PROMPT.format(word=word, sense=sense)}]
    best, tries = None, []
    for attempt in range(attempts):
        try:
            written = chat(WRITER_MODEL, messages, CLUES_SCHEMA, 0.6, num_predict=300)
        except (requests.RequestException, ValueError, KeyError) as error:
            tries.append({"error": str(error)})
            continue
        clues, problems, ranks, guesses = check(checker, word, sense, written)
        entry = {
            "sense": sense,
            "meaning": written.get("meaning", ""),
            "clues": clues,
            "passed": not problems,
            "reason": " ".join(problems) or "ok",
            "solver_ranks": ranks,
            "solver_guesses": guesses,
        }
        tries.append(entry)
        if best is None or score(entry) > score(best):
            best = entry
        if entry["passed"]:
            break
        messages += [
            {"role": "assistant", "content": json.dumps(written, ensure_ascii=False)},
            {"role": "user", "content": "Problems:\n- " + "\n- ".join(problems)
             + "\nFix these and keep what was fine. Reply with all four fields again."},
        ]
    best = dict(best or {"clues": [], "passed": False, "reason": "writer failed",
                         "solver_ranks": [], "solver_guesses": []})
    best["attempts"] = len(tries)
    best["tries"] = tries
    return best


def load_words(sample, seed):
    words = [w.strip() for w in TARGETS_PATH.read_text(encoding="utf-8").splitlines() if w.strip()]
    if sample:
        words = random.Random(seed).sample(words, sample)
    return words


def save(path, results):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def export(results, path):
    key = schedule_key()
    if key is None:
        print("No schedule key (WORDHUNT_SCHEDULE_KEY or schedule.key): clues.json not written")
        return
    passed = {word_code(w, key): e["clues"] for w, e in sorted(results.items()) if e["passed"]}
    path.write_text(json.dumps(passed, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote clues for {len(passed)} words to {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--clues", type=Path, default=CLUES_PATH)
    parser.add_argument("--export-only", action="store_true", help="only rewrite the clues file")
    parser.add_argument("--sample", type=int, default=0, help="random sample of N words")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--redo-failed", action="store_true", help="retry words that failed before")
    args = parser.parse_args()

    results = json.loads(args.report.read_text(encoding="utf-8")) if args.report.exists() else {}
    if args.export_only:
        export(results, args.clues)
        return

    checker = Checker(WordGameEngine())
    words = load_words(args.sample, args.seed)
    todo = [w for w in words if w not in results or (args.redo_failed and not results[w]["passed"])]
    print(f"{len(todo)} words to do ({len(results)} already in {args.report.name})")

    started = time.time()
    for n, word in enumerate(todo, start=1):
        entry = make_entry(checker, word, args.attempts)
        results[word] = entry
        save(args.report, results)
        mark = "PASS" if entry["passed"] else "FAIL"
        per_word = (time.time() - started) / n
        print(f"[{n}/{len(todo)}] {mark} {word}: ranks {entry['solver_ranks']} "
              f"({entry['reason']}, {entry['attempts']} tries, {per_word:.0f}s/word)", flush=True)

    passed = sum(1 for w in words if results.get(w, {}).get("passed"))
    print(f"Done: {passed}/{len(words)} passed")
    export(results, args.clues)


if __name__ == "__main__":
    main()
