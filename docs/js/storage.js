// The player's progress lives in this browser: every puzzle they've touched,
// with its guess history, help used, timer and result. The server keeps none.

const STORAGE_KEY = "wordhunt:v1";
const DAY_MS = 24 * 60 * 60 * 1000;

function readAll() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        const data = raw ? JSON.parse(raw) : null;
        if (data && typeof data.games === "object") return data;
    } catch (err) {
        console.warn("Could not read saved progress:", err);
    }
    return { games: {} };
}

function writeAll(data) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (err) {
        // Private mode or storage blocked: the game still works, it just
        // won't remember progress after the tab closes.
        console.warn("Could not save progress:", err);
    }
}

function newGame() {
    return {
        entries: [], // guesses, suggestions and the final result, oldest first
        hintCount: 0,
        similarCount: 0,
        clues: [], // clue texts shown so far, vaguest first
        clueTotal: null, // how many clues the puzzle has, once the server says
        bestRank: null,
        startedAt: null, // ms timestamp of the first guess or help
        status: "playing", // "playing" | "won" | "quit"
        score: null,
        onTheDay: false, // won on the puzzle's own UTC day (counts for streaks)
    };
}

export class Progress {
    constructor() {
        this.data = readAll();
    }

    game(puzzle) {
        // Older saves lack newer fields, so fill them in from a fresh game.
        return { ...newGame(), ...this.data.games[puzzle] };
    }

    // Has the player started this puzzle?
    has(puzzle) {
        return puzzle in this.data.games;
    }

    save(puzzle, game) {
        this.data.games[puzzle] = game;
        writeAll(this.data);
    }

    // Current streak: puzzles solved on their own day, back from today.
    // Today doesn't break the streak until it's over, so an unsolved
    // today counts from yesterday.
    streaks(today) {
        const solvedOnDay = (n) => {
            const g = this.data.games[n];
            return Boolean(g && g.status === "won" && g.onTheDay);
        };

        let n = solvedOnDay(today) ? today : today - 1;
        let current = 0;
        while (n >= 1 && solvedOnDay(n)) {
            current += 1;
            n -= 1;
        }

        let best = 0;
        let run = 0;
        for (let i = 1; i <= today; i += 1) {
            run = solvedOnDay(i) ? run + 1 : 0;
            best = Math.max(best, run);
        }
        return { current, best };
    }
}

// --- Dates (puzzles change at midnight UTC) ---------------------------------

export function puzzleOnDate(launchDate, when = Date.now()) {
    const launch = Date.parse(`${launchDate}T00:00:00Z`);
    return Math.floor((when - launch) / DAY_MS) + 1;
}

export function dateOfPuzzle(launchDate, puzzle) {
    const launch = Date.parse(`${launchDate}T00:00:00Z`);
    return new Date(launch + (puzzle - 1) * DAY_MS);
}

export function formatDate(date) {
    return date.toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
    });
}

export function msUntilNextPuzzle(when = Date.now()) {
    return DAY_MS - (when % DAY_MS);
}
