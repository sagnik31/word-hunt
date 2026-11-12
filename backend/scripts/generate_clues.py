"""
Write three clues per answer word with a local Ollama model, then check them.

Clues go from vague to strong and describe the word's meaning only. The
writer is given a dictionary meaning (WordNet) so it doesn't have to recall
the facts itself. Of a word's senses it gets the one closest to the word's
nearest neighbours in the game's embeddings, so the clues describe the same
meaning the hot-and-cold ranks are built on ("washer" the machine, not the
person or the seal).

The vague clue isn't written by the model: it's the sense's WordNet parent,
"A kind of home appliance.", which is always true and always broad. Parents
that are too narrow, too abstract or not everyday words are skipped, and the
model writes the vague clue only for the few words with no usable parent.
The model writes the meaning and the strong clue first, then the medium clue,
which should restate a detail the dictionary meaning gives, so it has no
room to invent facts.

Each set is checked three times:

1. Rules: no answer word or a word built from it, no talk of letters,
   spelling or sounds, no names, at most MAX_WORDS words per clue.
2. Facts: a second model, also given the dictionary meaning, checks the
   model-written clues for errors, the medium one against the meaning.
   A vague clue that fits other things too is fine.
3. Solver: the second model sees the clues one at a time (clue 1, then
   1-2, then 1-3, as a player would) and makes 3 guesses each time. Each
   guess is ranked against the answer exactly as the game ranks a player's
   guess. The strong clue must bring the solver to rank STRONG_MAX_RANK or
   better, and none of the 3 guesses from the vague clue alone may be the
   answer. If a WordNet category gives the word away, the next broader one
   is tried.

The category words are checked against the concreteness ratings
(data/raw/concreteness_ratings.csv), so that file is needed.

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
import csv
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
RATINGS_PATH = ROOT / "data" / "raw" / "concreteness_ratings.csv"
# A category word must be one nearly everyone knows ("liquor", not "lipid").
FAMILIAR_KNOWN = 0.95  # share of raters who knew the word
FAMILIAR_SUBTLEX = 20  # subtitle frequency count
MIN_KINDS = 10  # a category must cover at least this many WordNet terms
MIN_DEPTH = 4  # shallower categories ("object", "communication") say nothing
# Categories that are true but read oddly as a clue ("A kind of artifact").
DULL_CATEGORIES = {
    "artifact.n.01", "instrumentality.n.03", "way.n.06", "molecule.n.01", "unit.n.05",
    "acquisition.n.02", "indication.n.01", "message.n.02", "framework.n.03", "line.n.02",
    "mark.n.04", "commodity.n.01", "consumer_goods.n.01", "activity.n.01", "act.n.02",
    "white_goods.n.01", "transferred_property.n.01",
    "organism.n.01", "tract.n.01",
}
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
{category}
Write {count} clues for "{word}" in this meaning only. Fill in the fields in this order:
- meaning: the meaning above in your own plain words. The clues must all be about it.
- strong: the clearest description of that meaning, so a player names this exact word and not a close relative of it.
- medium: one detail that the meaning above gives (what it is made of, what it does, what it has or where it is), in your own plain words. Add no fact the meaning doesn't give. It should narrow the word down to a handful of words.
{vague}
Rules for the clues:
- Each is one plain sentence of at most 15 words.
- Only state what is plainly true of this meaning. If you are not sure of a fact, leave it out.
- Never use the secret word or any word made from it (plural, verb form, compound).
- Never mention letters, spelling, word length, sounds or rhymes.
- No names of people, places, countries, brands, books or films.

Example for the secret word "kettle" (meaning: a metal pot with a spout and handle, for boiling water):
{example}"""

VAGUE_FIELD = ('- vague: only the broad category, such as "something found in a kitchen" or '
               '"a kind of worker". Dozens of words should fit it. Use no detail from the other '
               'two clues.\n')
KETTLE = {"meaning": "a metal pot with a spout and a handle for boiling water",
          "strong": "You fill it with water and heat it to make tea.",
          "medium": "It is a metal pot with a spout for pouring.",
          "vague": "You will find this in most kitchens."}

FACT_PROMPT = """Word: "{word}" (meaning: {meaning})
Clue: "{clue}"

Check the clue for factual errors about this word.
- A vague clue that also fits many other things is fine. Only judge whether what it says is correct.
- It is wrong if any part is false, if it describes something else (a related object, place or person), or if it is about a different meaning of the word.

First say in one short sentence what the clue claims and whether that is right for "{word}". Then give the verdict."""

MEDIUM_FACT_PROMPT = """Word: "{word}"
Dictionary meaning: {meaning}
Clue: "{clue}"

Check the clue against the dictionary meaning.
- It is correct if everything it says is given by the meaning, or is plainly true of every "{word}".
- It is wrong if it adds a detail that is false, only sometimes true, or about something else.

First say in one short sentence what the clue claims and whether the meaning backs it up. Then give the verdict."""

SOLVER_PROMPT = """Guess the secret English word from these clues:
{clues}

The secret word is a common noun, verb or adjective. Reply with your 3 best single-word guesses, best first."""

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


def familiar_words():
    """Words nearly everyone knows, from the concreteness ratings."""
    if not RATINGS_PATH.exists():
        sys.exit(f"Missing {RATINGS_PATH}: see 'Rebuilding the data' in the README.")
    with RATINGS_PATH.open(encoding="utf-8") as f:
        return {row["Word"].lower() for row in csv.DictReader(f)
                if float(row["Percent_known"]) >= FAMILIAR_KNOWN
                and float(row["SUBTLEX"]) >= FAMILIAR_SUBTLEX}


def category_clues(synset, word, familiar):
    """Vague clues from the sense's WordNet parents, nearest first.

    "A kind of home appliance." is always true and always broad, so the
    model doesn't have to write the vaguest clue. A parent is skipped when it
    is too narrow (fewer than MIN_KINDS terms under it), too abstract, dull,
    or has no everyday name that isn't built from the word itself.
    """
    clues, seen, level = [], set(), [synset]
    while level:
        level = [p for s in level for p in s.hypernyms() if p not in seen]
        seen.update(level)
        for parent in level:
            if parent.min_depth() < MIN_DEPTH or parent.name() in DULL_CATEGORIES:
                continue
            if len(set(parent.closure(lambda s: s.hyponyms()))) < MIN_KINDS:
                continue
            for lemma in parent.lemmas():
                parts = lemma.name().split("_")
                if lemma.name().islower() and all(
                        p in familiar and p != word and not shares_stem(p, word) and word not in p
                        for p in parts):
                    clues.append(f"A kind of {' '.join(parts)}.")
                    break
    return list(dict.fromkeys(clues))


def pick_sense(engine, word):
    """The WordNet noun sense closest to the word's neighbours in the embeddings.

    Named things (a sense that is an instance, such as a person) and senses
    whose definition names something ("the United States head of state") are
    skipped, since clues may not contain names. Returns None when WordNet has
    no usable noun sense.
    """
    def named(synset):
        return any(t.lower() != word for t in re.findall(r"\b[A-Z][a-z]+", synset.definition()))

    synsets = [s for s in wn.synsets(word, pos="n")[:MAX_SENSES] if not s.instance_hypernyms()]
    synsets = [s for s in synsets if not named(s)] or synsets  # "Mexican liquor" is all there is
    if not synsets:
        return None
    ranking = engine.ranking(word)
    centre = bag_vector(engine, [ranking.neighbour(i)[0] for i in range(NEIGHBOURS)], word)
    if centre is None:
        return synsets[0]

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
    return best


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

    def false_clues(self, word, meaning, clues, check_vague=True):
        """(clue name, reason) for each clue the checker model says is wrong.

        The medium clue is checked against the dictionary meaning, since it
        should only restate a detail from it. A vague clue taken from WordNet
        is true by construction and needs no check.
        """
        wrong = []
        for name, clue in zip(CLUE_NAMES, clues):
            if name == "vague" and not check_vague:
                continue
            prompt = MEDIUM_FACT_PROMPT if name == "medium" else FACT_PROMPT
            answer = ask(CHECKER_MODEL, prompt.format(word=word, meaning=meaning, clue=clue),
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


def solver_problems(word, ranks, guesses, fixed_vague=False):
    """Why the solver run fails, as feedback for the writer (empty = pass).

    A giveaway vague clue from WordNet isn't the writer's to fix, so it's
    left out when fixed_vague is set; the caller moves up a category instead.
    """
    problems = []
    if ranks[0] == 1 and not fixed_vague:
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


def check(checker, word, sense, written, vague=None):
    """Run all three checks. Returns (clues, problems, ranks, guesses).

    vague is the WordNet category clue, or None when the writer wrote one.
    """
    clues = [vague or str(written.get("vague", "")).strip(),
             str(written.get("medium", "")).strip(), str(written.get("strong", "")).strip()]
    problems = checker.rule_problems(word, clues)
    if problems:
        return clues, problems, [], []
    problems = [f'The {name} clue was judged wrong: {reason.strip().rstrip(".")}. '
                'Replace it with something plainly true.'
                for name, reason in checker.false_clues(word, sense, clues, vague is None)]
    if problems:
        return clues, problems, [], []
    ranks, guesses = checker.solve(word, clues)
    return clues, solver_problems(word, ranks, guesses, vague is not None), ranks, guesses


def writer_prompt(word, sense, categories):
    """The writer's first message and the JSON schema for its reply."""
    fields = ["meaning", "strong", "medium"] + ([] if categories else ["vague"])
    category = f"It is {categories[0][0].lower()}{categories[0][1:]}\n" if categories else ""
    prompt = PROMPT.format(
        word=word, sense=sense, category=category, count=len(fields) - 1,
        vague="" if categories else VAGUE_FIELD,
        example=json.dumps({f: KETTLE[f] for f in fields}, ensure_ascii=False))
    schema = {"type": "object", "properties": {f: {"type": "string"} for f in fields},
              "required": fields}
    return prompt, schema


def make_entry(checker, word, attempts, familiar):
    """Write clues, then revise them with feedback until they pass or tries run out.

    When WordNet gives the sense an everyday category, the vague clue is
    "A kind of <category>." and the writer only writes the other two. If the
    solver guesses the word from it, the next broader category is tried.
    """
    synset = pick_sense(checker.engine, word)
    sense = synset.definition() if synset else word
    categories = category_clues(synset, word, familiar) if synset else []
    prompt, schema = writer_prompt(word, sense, categories)
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}]
    best, tries, level, written = None, [], 0, None
    for attempt in range(attempts):
        if written is None:
            try:
                written = chat(WRITER_MODEL, messages, schema, 0.6, num_predict=300)
            except (requests.RequestException, ValueError, KeyError) as error:
                tries.append({"error": str(error)})
                continue
        vague = categories[level] if categories else None
        clues, problems, ranks, guesses = check(checker, word, sense, written, vague)
        giveaway = vague is not None and bool(ranks) and ranks[0] == 1
        if giveaway:
            problems.insert(0, f"The vague clue gave the word away ({', '.join(guesses[0])}).")
        entry = {
            "sense": sense,
            "meaning": written.get("meaning", ""),
            "clues": clues,
            "category": vague is not None,
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
        if giveaway:
            if level + 1 == len(categories):
                break  # no broader category left
            level += 1
            problems = problems[1:]
        if problems:  # something the writer has to fix
            messages += [
                {"role": "assistant", "content": json.dumps(written, ensure_ascii=False)},
                {"role": "user", "content": "Problems:\n- " + "\n- ".join(problems)
                 + "\nFix these and keep what was fine. Reply with all the fields again."},
            ]
            written = None
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
    familiar = familiar_words()
    words = load_words(args.sample, args.seed)
    todo = [w for w in words if w not in results or (args.redo_failed and not results[w]["passed"])]
    print(f"{len(todo)} words to do ({len(results)} already in {args.report.name})")

    started = time.time()
    for n, word in enumerate(todo, start=1):
        entry = make_entry(checker, word, args.attempts, familiar)
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
