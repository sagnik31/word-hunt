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
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
    }

    checkHealth() {
        return this.get("/health");
    }

    getToday() {
        return this.get("/today");
    }

    // stats: { elapsed_seconds, hint_count, similar_count, best_rank }
    makeGuess(puzzle, word, stats) {
        return this.post("/guess", { puzzle, word, stats });
    }

    getSimilarWord(puzzle, bestRank, timesUsed) {
        return this.post("/similar_word", { puzzle, best_rank: bestRank, times_used: timesUsed });
    }

    getHint(puzzle, bestRank, timesUsed) {
        return this.post("/hint", { puzzle, best_rank: bestRank, times_used: timesUsed });
    }

    quitGame(puzzle, stats) {
        return this.post("/quit", { puzzle, stats });
    }
}
