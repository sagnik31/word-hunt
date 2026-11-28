# ADR 0001: Measure closeness with static GloVe embeddings, ranked on the fly

- **Status:** Accepted
- **Date:** 2026-11-08

## Context

The game's only feedback is how close a guess is in meaning to the secret word. That number has to be:

- **the same for every player and every request,** so a day's puzzle is fair and players can compare notes;
- **cheap,** since the backend runs on a free hosting tier with about 512 MB of memory and no GPU;
- **readable,** so a player can tell "very close" from "warm" without knowing what a cosine similarity is.

The first version stored a precomputed similarity table (`data/similarity.txt`, about 90 MB) for a vocabulary of about 2,300 nouns. Players could only guess nouns, the file was too big to keep in git comfortably, and adding words meant rebuilding the whole table.

## Decision

- **Embeddings:** use the GloVe 6B 300-dimensional vectors (Pennington, Socher & Manning, 2014). An offline script keeps one vector for each of the ~31,000 guessable words, scales each to unit length and saves them as float16 in `data/embeddings.npz` (about 18 MB, committed).
- **Similarity:** cosine similarity, which for unit vectors is a dot product.
- **Ranking on the fly:** when a puzzle's answer is first needed, the engine multiplies the whole matrix by the answer's vector and sorts. That takes a few milliseconds. The result is cached for the last few answers, behind a lock because FastAPI runs endpoints on a thread pool.
- **Feedback is the rank, not the raw score.** The answer is rank 1 and its nearest neighbour rank 2. The temperature labels (Boiling, Hot, … Freezing) are fixed rank bands, so they mean the same thing on every puzzle even though raw cosine values vary a lot from word to word.

## Alternatives considered

- **A precomputed similarity table** (the old approach). It's simple at runtime, but its size grows with vocabulary × answers, and it limited guesses to a small noun list. Dropped.

## Consequences

- The server loads about 115 MB at startup and needs `numpy`. GloVe itself (about 1 GB) is only needed offline.
- Any single word with a GloVe vector can be a guess, of any part of speech.
- GloVe was trained on web and news text, so some neighbours reflect brands, films or people instead of the everyday sense. A fruit can sit near a software company, for example. This is the main reason answers are chosen to be common, picturable nouns, and it's a known limit of the approach.
- Changing the vocabulary means rerunning the offline scripts and committing the new `.npz`. Nothing is computed at deploy time.
