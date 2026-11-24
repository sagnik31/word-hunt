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
A passing set whose medium clue shares no word with the meaning is marked
review_first in the report, so the human skim starts with the likeliest
invented details.

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
up where it stopped, and a one-line summary per word goes to a log next to it.
The progress shown on screen never names a word.

The report is written to a temporary file and then moved into place, so a
Ctrl+C or a kill leaves the last good report behind and a rerun redoes only
the unfinished word. A word whose models fail (Ollama down, a timeout, bad
JSON on every try) is logged and left out of the report, so a rerun tries it
again; after MAX_ERRORS_IN_A_ROW such words the run stops.

A run never writes data/clues.json. After a human has skimmed the report,
--export-only writes every answer's full clue set, passed or not, keyed by
clue codes, which differ from the schedule's so nobody can tell which day a
set of clues is for. That step needs the schedule key.

    python backend/scripts/generate_clues.py                                # all answers
    python backend/scripts/generate_clues.py --words <file> --report <file> # other words
    python backend/scripts/generate_clues.py --summary                      # counts only
    python backend/scripts/generate_clues.py --export-only                  # write clues.json
"""

import argparse
import csv
import json
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
import requests
from nltk.corpus import wordnet as wn

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.config import CLUES_PATH, SCHEDULE_PATH, schedule_key  # noqa: E402
from backend.daily import clue_code, decode, read_codes  # noqa: E402
from backend.game import WordGameEngine  # noqa: E402
from backend.scripts.build_word_lists import (  # noqa: E402
    PROPER_NOUNS_PATH,
    is_proper_noun,
    read_blocklist,
)
from backend.utils.files import write_atomic  # noqa: E402

OLLAMA_URL = "http://localhost:11434/api/chat"
WRITER_MODEL = "qwen3.5:4b"
SOLVER_MODEL = "gemma4:e2b"
CHECKER_MODEL = "gemma4:e2b"

TARGETS_PATH = ROOT / "data" / "target_words.txt"
GUESS_PATH = ROOT / "data" / "guess_words.txt"
DEFAULT_REPORT = ROOT / "data" / "raw" / "clue_report.json"

MAX_WORDS = 15  # per clue, as the writer's prompt says
STRONG_MAX_RANK = 10  # "Boiling"
OLLAMA_SEED = 7  # fixed sampling seed, so a rerun of the same prompt is comparable
# --redo-failed adds the word's redo round to the seed: with the same seed a
# retry repeats nearly the same tries and fails the same way.
seed = OLLAMA_SEED
# Context Ollama reserves per model. Its default is the model's maximum (262k
# tokens for the writer, about 12 GB); our longest conversation is a few
# thousand tokens, and a prompt that would not fit is an error, not a silent cut.
NUM_CTX = 8192
MAX_ERRORS_IN_A_ROW = 3  # words whose models all failed before the run stops
# Why a try failed, as recorded in the report and counted by --summary.
FAILURE_KINDS = ("rules", "facts", "vague too easy", "strong too weak", "error")
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

# Words a clue uses without stating a fact ("It is a kind of ..."), ignored
# when checking whether the medium clue's words come from the meaning.
FILLER = set(
    "it its this they them their you your he she his her has have had was were not no very "
    "often usually most many much made make makes there where when while all also only more "
    "less like so do does lot lots kind type piece part thing things something someone people "
    "person place plain".split()
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
- medium: take one detail straight from the meaning above (what it is made of, what it does, what it has or where it is) and say it in plain words. Every fact in the medium clue must be in the meaning; if the meaning doesn't say it, leave it out. Use a different detail from the strong clue, so the two clues tell the player different things.
{vague}
Rules for the clues:
- Each is one plain sentence of at most 15 words.
- Only state what is plainly true of this meaning. If you are not sure of a fact, leave it out.
- Never use the secret word or any word made from it (plural, verb form, compound).
- Never mention letters, spelling, word length, sounds or rhymes.
- No names of people, places, countries, brands, books or films.

Example for the secret word "teapot" (meaning: a pot with a handle, a spout and a lid, for brewing tea):
{example}"""

VAGUE_FIELD = ('- vague: only the broad category, such as "something found in a kitchen" or '
               '"a kind of worker". Dozens of words should fit it. Use no detail from the other '
               'two clues.\n')
# The worked example in the writer's prompt; never an answer word.
EXAMPLE = {"meaning": "a pot with a handle, a spout and a lid, for brewing tea",
           "strong": "You put tea leaves and hot water in it to brew tea.",
           "medium": "It is a pot with a spout for pouring and a lid.",
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

# What a failed or garbled Ollama reply raises: a network error or timeout,
# JSON that doesn't parse (truncated output), or a reply missing its fields.
OLLAMA_ERRORS = (requests.RequestException, ValueError, KeyError, TypeError)

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
            "options": {"temperature": temperature, "num_predict": num_predict,
                        "seed": seed, "num_ctx": NUM_CTX},
        },
        timeout=300,
    )
    response.raise_for_status()
    body = response.json()
    if body.get("prompt_eval_count", 0) + num_predict >= NUM_CTX:
        raise RuntimeError(f"The prompt nearly fills the {NUM_CTX}-token context.")
    reply = json.loads(body["message"]["content"])
    if not isinstance(reply, dict):
        raise ValueError("The model's reply isn't an object.")
    return reply


def ask(model, prompt, schema, temperature=0.0):
    return chat(model, [{"role": "user", "content": prompt}], schema, temperature)


def text_field(reply, field):
    """A text field of a model's reply; "" when it's missing or not text."""
    value = reply.get(field)
    return value.strip() if isinstance(value, str) else ""


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
        sys.exit(f"Missing {RATINGS_PATH}: see design/data-pipeline.md.")
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
        self.listed_names = read_blocklist(PROPER_NOUNS_PATH) if PROPER_NOUNS_PATH.exists() else set()

    def is_name(self, token):
        """True for a proper noun ("Paris", "Italy's"), by the same test as the
        word lists. Abbreviations such as "TV" are fine."""
        if token.rstrip("s").isupper():
            return False
        low = re.sub(r"'s?$", "", token.lower())
        return low in self.listed_names or is_proper_noun(low)

    def forms(self, word):
        forms = {word} | self.engine.answer_forms(word)
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
                problems.append(f"The {name} clue is longer than {MAX_WORDS} words.")
            # A capital after the first word suggests a name. "I" and
            # abbreviations such as "TV" or "IDs" are fine. The first word is
            # always capitalised, so it's checked against the dictionary.
            names = [t for t in tokens[1:] if t[0].isupper() and not t.rstrip("s").isupper()]
            if tokens and self.is_name(tokens[0]):
                names.insert(0, tokens[0])
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
            if answer.get("correct") is not True:
                wrong.append((name, text_field(answer, "reason")))
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
            guesses = guesses.get("guesses")
            guesses = [g for g in guesses if isinstance(g, str)] if isinstance(guesses, list) else []
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


def stem(token):
    for suffix in ("ing", "ed", "es", "s", "er", "ly"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[:-len(suffix)]
    return token


def review_first(word, sense, medium):
    """True when none of the medium clue's content words is in the meaning.

    The medium clue should restate the meaning, so one that shares no word
    with it is the likeliest to have invented a detail. On the hand-labelled
    dev set this flagged about a third of the passing clues, and over half of
    those were doubtful or wrong (against about a quarter of the rest). It
    only orders the human skim; it doesn't fail anything.
    """
    meaning = {stem(w) for w in re.findall(r"[a-z]+", sense.lower())}
    content = [t for t in re.findall(r"[a-z]+", medium.lower())
               if len(t) > 2 and t not in STOPWORDS | FILLER and stem(t) != stem(word)]
    return bool(content) and not any(stem(t) in meaning for t in content)


def score(entry):
    """Order attempts: passing first, then by how close the strong clue got."""
    r3 = entry["solver_ranks"][2] if entry["solver_ranks"] else None
    return (entry["passed"], bool(entry["solver_ranks"]), -(r3 or 10**6))


def solver_kinds(ranks):
    """The FAILURE_KINDS a solver run shows (empty = pass)."""
    kinds = []
    if ranks[0] == 1:
        kinds.append("vague too easy")
    if ranks[2] is None or ranks[2] > STRONG_MAX_RANK:
        kinds.append("strong too weak")
    return kinds


def check(checker, word, sense, written, vague=None):
    """Run all three checks. Returns (clues, problems, kinds, ranks, guesses).

    vague is the WordNet category clue, or None when the writer wrote one.
    kinds names the FAILURE_KINDS found, so the report can be counted.
    """
    clues = [vague or text_field(written, "vague"),
             text_field(written, "medium"), text_field(written, "strong")]
    problems = checker.rule_problems(word, clues)
    if problems:
        return clues, problems, ["rules"], [], []
    problems = [f'The {name} clue was judged wrong: {reason.strip().rstrip(".")}. '
                'Replace it with something plainly true.'
                for name, reason in checker.false_clues(word, sense, clues, vague is None)]
    if problems:
        return clues, problems, ["facts"], [], []
    ranks, guesses = checker.solve(word, clues)
    return (clues, solver_problems(word, ranks, guesses, vague is not None), solver_kinds(ranks),
            ranks, guesses)


def writer_prompt(word, sense, categories):
    """The writer's first message and the JSON schema for its reply."""
    fields = ["meaning", "strong", "medium"] + ([] if categories else ["vague"])
    category = f"It is {categories[0][0].lower()}{categories[0][1:]}\n" if categories else ""
    prompt = PROMPT.format(
        word=word, sense=sense, category=category, count=len(fields) - 1,
        vague="" if categories else VAGUE_FIELD,
        example=json.dumps({f: EXAMPLE[f] for f in fields}, ensure_ascii=False))
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
            except OLLAMA_ERRORS as error:
                tries.append({"error": str(error), "kinds": ["error"]})
                continue
        vague = categories[level] if categories else None
        try:
            clues, problems, kinds, ranks, guesses = check(checker, word, sense, written, vague)
        except OLLAMA_ERRORS as error:
            # The checker or solver failed (timeout, bad JSON): the same
            # clues are checked again on the next try, not the run stopped.
            tries.append({"error": f"check failed: {error}", "kinds": ["error"]})
            continue
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
            "kinds": kinds,
            "review_first": review_first(word, sense, clues[1]),
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
    # error: no try got through the models, so the word isn't saved and a
    # rerun tries it again.
    best = dict(best or {"clues": [], "passed": False, "reason": "no try finished (see tries)",
                         "kinds": ["error"], "solver_ranks": [], "solver_guesses": [],
                         "error": True})
    best["attempts"] = len(tries)
    best["tries"] = tries
    return best


def read_words(path):
    return [w.strip() for w in path.read_text(encoding="utf-8").splitlines() if w.strip()]


def load_words(sample, seed, path=TARGETS_PATH):
    words = read_words(path)
    if sample:
        words = random.Random(seed).sample(words, sample)
    return words


def save(path, results):
    write_atomic(path, json.dumps(results, ensure_ascii=False, indent=2))


def log_path(report):
    return report.with_name(report.stem + ".log")


def log_line(report, text):
    """Append one line to the run log next to the report (it names words)."""
    with log_path(report).open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {text}\n")


def clock(seconds):
    minutes = round(seconds / 60)
    return f"{minutes // 60}h{minutes % 60:02d}m" if minutes >= 60 else f"{minutes}m"


def run(words, results, report, make, redo=()):
    """Make an entry for each word not yet in results (or in redo), saving
    after each one.

    make(word) returns the entry. A redone word keeps its old entry until the
    new one replaces it, so a stop part-way loses nothing. A word whose models fail is logged and
    skipped (not saved, so a rerun tries it again). Progress on screen never
    names a word; the log does. Returns the number of words that errored.
    """
    todo = [w for w in words if w not in results or w in redo]
    done_before = len(words) - len(todo)
    print(f"{len(todo)} words to do ({done_before} of {len(words)} already in {report.name})",
          flush=True)
    log_line(report, f"start: {len(todo)} to do, {done_before} already done")
    started, finished, errors, in_a_row = time.time(), 0, 0, 0
    for n, word in enumerate(todo, start=1):
        word_started = time.time()
        try:
            entry = make(word)
        except Exception as error:  # noqa: BLE001  one word must never stop the run
            entry = {"error": True, "attempts": 0, "reason": f"{type(error).__name__}: {error}"}
        seconds = time.time() - word_started
        position = f"[{done_before + n}/{len(words)}]"
        if entry.get("error"):
            errors += 1
            in_a_row += 1
            print(f"{position} ERROR (models failed, will retry on the next run)", flush=True)
            log_line(report, f"ERROR {word}: {entry.get('reason', '')}")
            if in_a_row >= MAX_ERRORS_IN_A_ROW:
                print(f"Stopping: {in_a_row} words in a row failed (is Ollama running?). "
                      "Rerun the same command to carry on.", flush=True)
                break
            continue
        in_a_row = 0
        entry["seconds"] = round(seconds)
        results[word] = entry
        save(report, results)
        finished += 1
        mark = "PASS" if entry["passed"] else "FAIL"
        per_word = (time.time() - started) / n
        eta = clock(per_word * (len(todo) - n))
        print(f"{position} {mark} ({entry['attempts']} tries, {per_word:.0f}s/word, ETA {eta})",
              flush=True)
        log_line(report, f"{mark} {word}: {entry['attempts']} tries, {seconds:.0f}s, "
                         f"kinds {entry.get('kinds', [])}, ranks {entry['solver_ranks']}, "
                         f"{entry['reason']}")
    log_line(report, f"stop: {finished} saved, {errors} errors")
    return errors


def summary(results, words=None):
    """Counts for the report, naming no words."""
    entries = [results[w] for w in (words or results) if w in results]
    lines = []
    if words:
        lines.append(f"In the report: {len(entries)} of {len(words)} words")
    passed = sum(e["passed"] for e in entries)
    lines.append(f"Passed: {passed}/{len(entries)}"
                 + (f" ({100 * passed / len(entries):.0f}%)" if entries else ""))
    final = Counter(k for e in entries if not e["passed"] for k in e.get("kinds", []))
    lines.append("Failed words, last reason: "
                 + (", ".join(f"{k} {final[k]}" for k in FAILURE_KINDS if final[k]) or "none"))
    every = Counter(k for e in entries for t in e.get("tries", []) for k in t.get("kinds", []))
    lines.append(f"All failed tries ({sum(len(e.get('tries', [])) for e in entries)} tries): "
                 + (", ".join(f"{k} {every[k]}" for k in FAILURE_KINDS if every[k]) or "none"))
    flagged = sum(1 for e in entries if e["passed"] and e.get("review_first"))
    lines.append(f"Passing sets to review first (medium clue shares no word with the meaning): "
                 f"{flagged}")
    tries = Counter(e["attempts"] for e in entries if e["passed"])
    lines.append("Tries per passing word: "
                 + (", ".join(f"{n}: {tries[n]}" for n in sorted(tries)) or "none"))
    seconds = [e["seconds"] for e in entries if "seconds" in e]
    if seconds:
        lines.append(f"Time: {clock(sum(seconds))} in all, {sum(seconds) / len(seconds):.0f}s/word")
    return "\n".join(lines)


def export(results, path, schedule_path=SCHEDULE_PATH):
    key = schedule_key()
    if key is None:
        print("No schedule key (WORDHUNT_SCHEDULE_KEY or schedule.key): clues.json not written")
        return
    # With the wrong key every code is wrong, and the server would quietly
    # find no clues for any puzzle. The right key decodes the schedule.
    targets = set(read_words(TARGETS_PATH))
    codes = read_codes(schedule_path)
    scheduled = decode(codes, key, targets | set(results) | set(read_words(GUESS_PATH)))
    if not any(scheduled):
        print(f"The schedule key doesn't decode {schedule_path.name} (wrong key?): clues.json not written")
        return
    # Only answers: a report made with --words (a test set) must never leak in.
    # A scheduled word counts even if it has since left the answer list.
    answers = targets | {w for w in scheduled if w}
    others = sum(1 for w in results if w not in answers)
    # Every answer with a full set ships, passed or not (owner's call,
    # 2026-11-23): a failed set is weaker or flawed, not missing, and the owner
    # skims those first. Only a word whose models never finished is left out.
    shipped = {w: e for w, e in sorted(results.items())
               if w in answers and not e.get("error") and len(e.get("clues") or []) == 3}
    failed = sum(1 for e in shipped.values() if not e["passed"])
    if not shipped:
        print("The report has no finished clue sets (wrong path?): clues.json not written")
        return
    clues = {clue_code(w, key): e["clues"] for w, e in shipped.items()}
    # A scheduled puzzle never loses the clues it already has.
    published = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    live = [clue_code(w, key) for w in scheduled if w]
    kept = {c: published[c] for c in live if c in published and c not in clues}
    clues.update(kept)
    # Sorted by code: in word order, the codes would match the public answer list.
    write_atomic(path, json.dumps(clues, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    print(f"Wrote clues for {len(clues)} words to {path}, {failed} of them sets that failed a check"
          + (f", {len(kept)} kept from before" if kept else "")
          + (f" (left out {others} words that aren't answers)" if others else ""))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--clues", type=Path, default=CLUES_PATH)
    parser.add_argument("--words", type=Path, default=TARGETS_PATH,
                        help="word list to run on (default: the answers)")
    parser.add_argument("--export-only", action="store_true",
                        help="write every answer's clue set to the clues file, then stop")
    parser.add_argument("--summary", action="store_true", help="print counts only, then stop")
    parser.add_argument("--sample", type=int, default=0, help="random sample of N words")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--redo-failed", action="store_true", help="retry words that failed before")
    args = parser.parse_args(argv)

    results = json.loads(args.report.read_text(encoding="utf-8")) if args.report.exists() else {}
    if args.export_only:
        export(results, args.clues)
        return
    words = load_words(args.sample, args.seed, args.words)
    if args.summary:
        print(summary(results, words))
        return

    checker = Checker(WordGameEngine())
    familiar = familiar_words()
    redo = {w for w in words if w in results and not results[w]["passed"]} if args.redo_failed \
        else set()

    def make(word):
        global seed
        rounds = results[word].get("round", 0) + 1 if word in redo else 0
        seed = OLLAMA_SEED + rounds
        entry = make_entry(checker, word, args.attempts, familiar)
        entry["round"] = rounds
        return entry

    try:
        run(words, results, args.report, make, redo)
    except KeyboardInterrupt:
        print("\nStopped. Finished words are saved; rerun the same command to carry on.")
        sys.exit(130)
    print(summary(results, words))
    print("Not exported. Skim the report, then run with --export-only to write the clues file.")


if __name__ == "__main__":
    main()
