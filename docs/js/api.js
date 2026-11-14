export class ApiClient {
    constructor(baseUrl) {
        this.baseUrl = baseUrl;
    }

    async get(path) {
        const res = await fetch(`${this.baseUrl}${path}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
    }

    async post(path, body) {
        const res = await fetch(`${this.baseUrl}${path}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            const err = new Error(`HTTP ${res.status}`);
            err.status = res.status;
            throw err;
        }
        return res.json();
    }

    checkHealth() {
        return this.get("/health");
    }

    getToday() {
        return this.get("/today");
    }

    // stats: { elapsed_seconds, guess_count, clue_count, hint_count, best_rank }
    makeGuess(puzzle, word, stats) {
        return this.post("/guess", { puzzle, word, stats });
    }

    // { puzzle, clue_total }
    getPuzzle(puzzle) {
        return this.get(`/puzzle/${puzzle}`);
    }

    // A word ranked better than bestRank; 409 when no hint is left to give.
    getHint(puzzle, bestRank, hintsUsed) {
        return this.post("/hint", { puzzle, best_rank: bestRank, hints_used: hintsUsed });
    }

    // The next written clue; 404 when the puzzle has none, 409 when used up.
    getClue(puzzle, cluesUsed) {
        return this.post("/clue", { puzzle, clues_used: cluesUsed });
    }

    quitGame(puzzle, stats) {
        return this.post("/quit", { puzzle, stats });
    }
}
