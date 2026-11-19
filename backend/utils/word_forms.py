"""
English plural and verb-form rules, shared by the word-list build script and
the game engine.

The word lists hold base forms ("cat", "bake"); these rules let the game accept
"cats", "baked" or "bigger" and treat them as the base word.
"""

from typing import Dict, List, Set

VOWELS = set("aeiou")

# Plurals that mean something other than "more than one" of the singular.
# They stay answers of their own, and typing the singular doesn't win them.
KEEP_PLURALS = {"clothes", "glasses", "pajamas", "checkers"}

# Irregular forms the dataset doesn't already list (base -> forms).
IRREGULAR_FORMS: Dict[str, Set[str]] = {
    "man": {"men"},
    "woman": {"women"},
    "child": {"children"},
    "person": {"people"},
    "foot": {"feet"},
    "tooth": {"teeth"},
    "goose": {"geese"},
    "mouse": {"mice"},
    "louse": {"lice"},
    "ox": {"oxen"},
    "die": {"dice"},
    "cactus": {"cacti"},
    "fungus": {"fungi"},
    "knife": {"knives"},
    "wife": {"wives"},
    "life": {"lives"},
    "wolf": {"wolves"},
    "leaf": {"leaves"},
    "loaf": {"loaves"},
    "half": {"halves"},
    "calf": {"calves"},
    "shelf": {"shelves"},
    "thief": {"thieves"},
    "elf": {"elves"},
    "hoof": {"hooves"},
    "scarf": {"scarves"},
    "pay": {"paid"},
    "hide": {"hid", "hidden"},
    "hear": {"heard"},
    "hold": {"held"},
    "begin": {"began", "begun"},
    "forgive": {"forgave", "forgiven"},
}


def _ends_consonant_y(word: str) -> bool:
    return len(word) > 1 and word[-1] == "y" and word[-2] not in VOWELS


def _ends_cvc(word: str) -> bool:
    """Consonant-vowel-consonant ending, as in "hop" -> "hopping"."""
    return (
        len(word) >= 3
        and word[-1] not in VOWELS | {"w", "x", "y"}
        and word[-2] in VOWELS
        and word[-3] not in VOWELS
    )


def plural_forms(word: str) -> Set[str]:
    """Plurals of a noun (also third-person verb forms: "bakes")."""
    forms = {word + "s"}
    if word.endswith(("s", "x", "z", "ch", "sh", "o")):
        forms.add(word + "es")
    if _ends_consonant_y(word):
        forms.add(word[:-1] + "ies")
    forms |= IRREGULAR_FORMS.get(word, set())
    return forms


def verb_forms(word: str) -> Set[str]:
    """Past tense and -ing forms of a verb."""
    forms = set()
    if word.endswith("e"):
        forms.add(word + "d")
        if not word.endswith(("ee", "ye", "oe")):
            forms.add(word[:-1] + "ing")
        else:
            forms.add(word + "ing")
    elif _ends_consonant_y(word):
        forms |= {word[:-1] + "ied", word + "ing"}
    else:
        forms |= {word + "ed", word + "ing"}
    if _ends_cvc(word):
        forms |= {word + word[-1] + "ed", word + word[-1] + "ing"}
    return forms


def adjective_forms(word: str) -> Set[str]:
    """Comparative and superlative of an adjective: "bigger", "largest"."""
    if word.endswith("e"):
        return {word + "r", word + "st"}
    if _ends_consonant_y(word):
        return {word[:-1] + "ier", word[:-1] + "iest"}
    forms = {word + "er", word + "est"}
    if _ends_cvc(word):
        forms |= {word + word[-1] + "er", word + word[-1] + "est"}
    return forms


def singular_forms(word: str) -> List[str]:
    """Possible singulars of a regular English plural."""
    forms = []
    if word.endswith("ies"):
        forms.append(word[:-3] + "y")
    if word.endswith("es"):
        forms.append(word[:-2])
    if word.endswith("s") and not word.endswith("ss"):
        forms.append(word[:-1])
    return forms


def inflections(word: str) -> Set[str]:
    return (plural_forms(word) | verb_forms(word)) - {word}
