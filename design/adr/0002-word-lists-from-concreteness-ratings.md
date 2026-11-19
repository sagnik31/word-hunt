# ADR 0002: Build every word list from one concreteness-ratings dataset, with no proper nouns

- **Status:** Accepted
- **Date:** 2026-11-08

## Context

The game needs several word lists that have to agree with each other:

- **guesses:** every word a player may type;
- **answers:** the possible secret words, which should be fair (everyday, picturable things), not obscure;
- **hints:** the words a Hint may reveal, which must look ordinary;
- **word forms:** plurals and verb forms that should count as their base word.

Earlier versions used ad-hoc noun lists from different sources, which disagreed about what a "common word" was. The project also has a firm rule: **only common words, never proper nouns** (no names, places, brands, days or months), as guesses, answers, hints or clues.

## Decision

- **One source:** Brysbaert, Warriner & Kuperman (2014), *Concreteness ratings for 40 thousand generally known English word lemmas*. For each word it gives a concreteness rating (1–5), the share of raters who knew it, a subtitle frequency and its usual part of speech. Those four fields are enough to define every list with a few thresholds.
- **The lists** (built by `backend/scripts/build_word_lists.py`; the thresholds are constants at its top):
  - **Guesses:** every single word in the dataset that has a GloVe vector and isn't a proper noun (~31,000).
  - **Answers:** nouns known by ≥ 95% of raters, concreteness ≥ 4.0 and subtitle frequency ≥ 50, minus plurals and a hand-edited blocklist (~2,500).
  - **Hints:** known by ≥ 95% of raters, subtitle frequency ≥ 10 and not an inflected form (~16,700).
  - **Word forms:** ~24,000 forms that aren't guess words themselves, each mapped to a base word, so a plural of the answer wins: plurals and verb forms, irregular forms from WordNet, comparatives, and British spellings (added 2026-11-20). A separate list of irregular plurals lets those win too when they're guess words of their own.
- **Proper nouns:** a word is excluded when WordNet only knows it with a capital letter, or when it's listed in `data/proper_nouns.txt`. A short allowlist in the script keeps ordinary words WordNet happens to capitalise. A test checks the generated lists.
- **Generated offline, committed:** the lists are plain text in `data/`, so the server and the tests don't need the dataset, WordNet or GloVe.

## Alternatives considered

- **Word-frequency lists alone** (for example, the most common N words). Frequency doesn't say whether a word is a picturable thing, and many frequent words are names.
- **"Known by most people" alone for hints.** Tried and rejected: some ugly inflected forms are known by nearly everyone, so the hint filter also needs a frequency floor and the inflection check.
- **A part-of-speech tagger or a named-entity model for proper nouns.** Heavier, and less predictable on single words with no sentence around them than a dictionary lookup plus a hand-kept list.

## Consequences

- Changing which words can be the answer is a matter of editing `data/target_blocklist.txt` or a threshold and rerunning the script (then the schedule script).
- The proper-noun rule depends on WordNet's coverage. Brands and characters WordNet doesn't know have to be added to `data/proper_nouns.txt` by hand when they slip through.
- Some words with a real lowercase meaning that is also a name (the word for plates that is also a country) are kept on purpose.
- The dataset's authors haven't stated licence terms, and the CSV is not committed: anyone rebuilding the lists downloads it themselves.
