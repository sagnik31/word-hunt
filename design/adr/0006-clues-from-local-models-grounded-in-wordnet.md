# ADR 0006: Generate clues offline with small local models, grounded in WordNet and checked by a solver

- **Status:** Accepted
- **Date:** 2026-11-08 (vague and medium clues revised 2026-11-12; medium prompt, review flag and run safety 2026-11-21; failed sets ship 2026-11-23)

## Context

Players who get stuck can unlock three written clues for the answer, going from a broad category to close to a definition. With thousands of possible answers, writing every clue by hand isn't practical, but the clues have to be:

- **true,** and about the same meaning of the word that the game's rankings use (a word like `crane` is both a bird and a machine, and the embeddings favour one);
- **graded,** so the first clue doesn't give the word away and the last one gets a player close;
- **free of names, spelling hints and the word itself.**

The project prefers to run on free, local tools, and the generation only has to happen once per answer list.

## Decision

- **Offline, not live.** `backend/scripts/generate_clues.py` runs on a developer's machine and writes `data/clues.json`. The server only reads that file at startup.
- **Small local models through Ollama:** one writes the clues and a second checks them. No paid API.
- **Ground the writer in a dictionary meaning** instead of asking it to recall facts. Of the word's WordNet senses, the writer gets the one closest to the word's nearest neighbours in the game's embeddings, so the clues and the hot-and-cold ranks describe the same meaning.
- **Take the vague clue from WordNet itself:** the meaning's broader category ("A kind of wading bird"), skipping categories that are too narrow, too abstract or not everyday words. The model writes a vague clue only when no category fits.
- **Check every set three ways:**
  - **Rules** in code: no answer word or a word built from it, nothing about letters or sounds, no names.
  - **Facts:** the second model, given the same meaning, looks for errors.
  - **Solver:** the second model guesses the word from the clues one at a time, and its guesses are ranked exactly like a player's. The strongest clue must bring it into the top 10, and the vague clue alone must not.
- **Targeted retries:** a failed set goes back to the writer with exactly what failed, up to four tries.
- **Keep it reviewable:** every attempt goes to a git-ignored report, saved after each word so a long run can resume, and a human skims the clues before they're exported. A run never exports by itself: `--export-only` is a separate step. Sets whose medium clue shares no word with the dictionary meaning are marked `review_first`.
- **Tune on words that aren't answers.** Prompt changes are measured on a test set drawn from the answer candidates, with hand-labelled facts, never on the answers themselves.

## Alternatives considered

- **A large hosted model.** An early pilot had many wrong clues, and a bigger model was the obvious suggestion. Measurement showed most failures came from the prompt and the pipeline (recalling facts from memory, the wrong sense, blind retries), not the model. After those fixes, the small local models passed most of the pilot. A hosted model would need a key, cost money, and still need the same checks.
- **Generating clues live per request.** It needs a model on the server, makes clues differ between players, and can't be reviewed before players see them.
- **Hand-written clues.** The best quality, but practical only for a small answer list. The pipeline is designed so a human edits its output instead of starting from nothing.

## Tuning results (2026-11-21)

On a 50-word test set, one change at a time against the then-current prompts:

- **Kept:** a medium-clue instruction to take its detail straight from the meaning and add no other fact. Passes went from 43 to 45 (within noise), failed fact checks from 11 to 8, and hand-labelled wrong or doubtful medium clues from 9/20 to 5/20.
- **Dropped:** two worked examples instead of one (41 passed, more rule failures), and more specific revision feedback (40 passed).
- **Dropped:** a strict checker that judges every clue against the definition only. It caught 6 of 8 wrong clues instead of 2, but rejected 22 of 35 correct ones instead of 3.

## Consequences

- A full run is slow on a CPU (about 45 seconds per word), so clues are generated for the final answer list, not every candidate.
- The fact check catches only some subtly wrong details, so **the clues need a human skim** whichever model writes them.
- **Failed sets ship too (owner's call, 2026-11-23).** After the run and two redo rounds, 187 of 200 answers passed. Rather than leave 13 days without clues, `--export-only` writes every full set. The help ladder, unlock gates and costs are the same on every puzzle, so nothing in the game changes; those days just get a weaker or flawed set. Of the 13: 10 have a strong clue that didn't bring the solver into the top 10, 2 have a vague clue that alone gave the word away (on those days Clue 1 is worth more than its 5-point cost; one of the 2 also has a weak strong clue), 1 tripped the letters-or-sounds check, and 1 has a clue the fact checker judged wrong. The owner's skim of the failed sets is the safeguard for the last two kinds, and none of the 13 failed the answer-form or name checks.
- An answer whose models never finished a try still has no clues, and the help ladder skips straight to hints.
- Exporting `data/clues.json` needs the schedule key, because the file is keyed by hashes of the answers (not the schedule's codes; see [ADR 0003](0003-hmac-hashed-schedule-in-a-public-repo.md)).
- The pipeline needs WordNet and the concreteness ratings locally, and its tests are skipped in CI, which has neither.
