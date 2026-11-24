# ADR 0009: Pick the answers by hand instead of by filters

- **Status:** Accepted
- **Date:** 2026-11-20

## Context

[ADR 0002](0002-word-lists-from-concreteness-ratings.md) chose the answers with filters: nouns known by at least 95% of raters, concreteness of at least 4.0 and a subtitle frequency of at least 50, minus a hand-edited blocklist. That gave about 2,500 answers, too many to check by hand. Playing it showed two problems:

- **Noisy rankings.** For some answers, GloVe's nearest words are brands, films or people rather than the everyday meaning. For a player, the ranks then make no sense.
- **The filters cut good words.** Subtitle frequency is a poor guide to whether a word is well known. Many well-known, picturable nouns fall under 50, and some words that pass are still poor answers.

The owner decided on a shorter list of about 200, each checked by hand, with clues the owner can skim.

## Decision

- **Answers come from a hand-edited file,** `data/answer_list.txt`, one word per line. `build_word_lists.py` writes it to `data/target_words.txt` after checking it. The schedule and clue scripts read that file, as before.
- **The checks:** every answer must be a guess word (so it has a vector and isn't a proper noun), mustn't be in `data/target_blocklist.txt`, and mustn't be a plural of another answer. The build stops with the offending words if any check fails.
- **The filters stay, as a source of candidates.** Words that pass them but aren't answers yet go to the git-ignored `data/raw/answer_candidates.txt`, to pick more answers from.
- **What makes a good answer:** a well-known, picturable, mid-frequency noun whose nearest words in the game are on topic. It should be hard because it doesn't spring to mind, not because it's rare.

## Alternatives considered

- **Tighter filters** (for example a higher frequency floor). They still can't tell whether an answer's neighbours make sense, and they would cut more of the good, less frequent words.
- **Filters plus a much longer blocklist.** Crossing out about 2,300 words by hand is more work than picking 200, and it still leaves every new candidate unchecked.

## Consequences

- **Changing the answers** means editing `data/answer_list.txt`, rerunning `build_word_lists.py`, then `build_schedule.py`. The schedule script still never changes released puzzles.
- **The list isn't secret.** Like the old `target_words.txt`, it's committed. The schedule's hashing (ADR 0003) hides which day uses which word, not which words are answers.
- **About 200 answers last about 200 days,** so the list has to grow before it runs out, from the candidates file or elsewhere. Since the 2026-11-23 relaunch the last scheduled puzzle is on 2027-06-10; after that `/today` gives no puzzle, and only past ones can be played, until more answers (with their clues) are added.
- **The list is small enough to audit:** for each answer, its nearest neighbours, what the hints can reveal, and how its plurals and spellings are matched.
