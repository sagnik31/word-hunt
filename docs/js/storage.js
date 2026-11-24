// The player's progress lives in this browser: every puzzle they've touched,
// with its guess history, help used, timer and result. The server keeps none.

const STORAGE_KEY = "wordhunt:v1";
const DEVICE_KEY = "wordhunt:device";
const DAY_MS = 24 * 60 * 60 * 1000;
// Puzzle numbers restart when the game relaunches, so a save belongs to one
// launch date. Saves from before the date was stored come from the first launch.
const FIRST_LAUNCH = "2026-11-08";
const OLD_SAVES_PREFIX = "wordhunt:old:";

// What the server accepts as a device ID (DEVICE_ID_PATTERN in backend/results.py).
const DEVICE_ID = /^[A-Za-z0-9-]{8,64}$/;

const isObject = (x) => x !== null && typeof x === "object" && !Array.isArray(x);

// The saved data, or null when there's none, it's damaged or it can't be read.
function readAll() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        const data = raw ? JSON.parse(raw) : null;
        if (isObject(data?.games)) return data;
    } catch (err) {
        console.warn("Could not read saved progress:", err);
    }
    return null;
}

// Returns whether it worked.
function writeAll(data) {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
        return true;
    } catch (err) {
        // Private mode or storage blocked: the game still works, it just
        // won't remember progress after the tab closes.
        console.warn("Could not save progress:", err);
        return false;
    }
}

function newGame() {
    return {
        entries: [], // guesses, suggestions and the final result, oldest first
        hintCount: 0, // hints used (similar-word reveals)
        clues: [], // clue texts shown so far, vaguest first
        clueTotal: null, // how many clues the puzzle has, once the server says
        bestRank: null,
        noHintAt: null, // the best rank at which the server had no hint to give
        startedAt: null, // ms timestamp of pressing Play (older saves: the first guess or help)
        finishedAt: null, // ms timestamp of solving or quitting
        status: "playing", // "playing" | "won" | "quit"
        score: null,
        onTheDay: false, // won on the puzzle's own UTC day (counts for streaks)
    };
}

// A history entry that can be shown and counted.
function validEntry(e) {
    if (!isObject(e)) return false;
    if (e.type === "quit") return typeof e.answer === "string";
    if (e.type === "clue") return typeof e.clue === "string";
    const ranked = typeof e.rank === "number" && typeof e.similarity === "number";
    if (e.type === "guess") return typeof e.guess === "string" && (!e.valid || ranked);
    return (e.type === "hint" || e.type === "similar word") && typeof e.word === "string" && ranked;
}

// A saved game with every field usable: a missing one (older saves) or a
// damaged one gets its value from a fresh game.
function cleanGame(saved) {
    const fresh = newGame();
    if (!isObject(saved)) return fresh;
    const game = { ...fresh, ...saved };
    game.entries = Array.isArray(saved.entries) ? saved.entries.filter(validEntry) : [];
    game.clues = Array.isArray(saved.clues) ? saved.clues.filter((c) => typeof c === "string") : [];
    if (!Number.isFinite(game.hintCount)) game.hintCount = 0;
    for (const key of ["clueTotal", "bestRank", "noHintAt", "startedAt", "finishedAt", "score"]) {
        if (!Number.isFinite(game[key])) game[key] = null;
    }
    if (!["playing", "won", "quit"].includes(game.status)) game.status = "playing";
    return game;
}

const finished = (game) => game?.status === "won" || game?.status === "quit";

export class Progress {
    constructor() {
        this.data = readAll() || { games: {} };
        this.unsaved = new Set(); // puzzles whose last write failed
    }

    // Take in what other tabs have saved. Games this tab couldn't write stay.
    // False when another tab has moved the saves to a different launch.
    sync() {
        const stored = readAll();
        if (stored === null) return true;
        if (this.data.launch && stored.launch && stored.launch !== this.data.launch) return false;
        const games = { ...stored.games };
        for (const n of this.unsaved) {
            if (!finished(games[n])) games[n] = this.data.games[n];
        }
        this.data = { ...stored, launch: stored.launch || this.data.launch, games };
        return true;
    }

    // Match the saves to the server's launch date. After a relaunch the old
    // games would land on the new puzzles with the same numbers, so they move
    // to a backup key and play starts afresh.
    useLaunch(launchDate) {
        const saved = this.data.launch || FIRST_LAUNCH;
        if (saved === launchDate) {
            if (!this.data.launch) {
                this.data.launch = launchDate;
                writeAll(this.data);
            }
            return;
        }
        if (Object.keys(this.data.games).length > 0) {
            this.backUp(OLD_SAVES_PREFIX + saved);
        }
        this.data = { launch: launchDate, games: {} };
        writeAll(this.data);
    }

    // With no room for a second copy, the first one goes before the backup is
    // written.
    backUp(key) {
        const old = JSON.stringify(this.data);
        try {
            localStorage.setItem(key, old);
        } catch {
            try {
                localStorage.removeItem(STORAGE_KEY);
                localStorage.setItem(key, old);
            } catch (err) {
                console.warn("Could not back up old progress:", err);
            }
        }
    }

    game(puzzle) {
        const game = cleanGame(this.data.games[puzzle]);
        // Saves from before gameplay v2 counted Hint and Similar Word apart;
        // both are Hints now.
        if ("similarCount" in game) {
            game.hintCount += Number(game.similarCount) || 0;
            delete game.similarCount;
        }
        return game;
    }

    // Has the player started this puzzle?
    has(puzzle) {
        return puzzle in this.data.games;
    }

    // Saves one puzzle, leaving the others as they are in storage: another
    // tab may have saved them since. A finish saved by another tab stays, and
    // false says this game wasn't saved over it.
    save(puzzle, game) {
        if (!this.sync()) return false;
        const stored = this.data.games[puzzle];
        if (stored !== game && finished(stored)) return false;
        this.data.games[puzzle] = game;
        if (writeAll(this.data)) this.unsaved.clear();
        else this.unsaved.add(puzzle);
        return true;
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

// A random ID for this browser, so the server counts one result per device
// per puzzle. It's not tied to an account and says nothing about the player.
// Null if storage is blocked: the game then just isn't counted.
export function deviceId() {
    try {
        let id = localStorage.getItem(DEVICE_KEY);
        if (!DEVICE_ID.test(id || "")) {
            id = typeof crypto.randomUUID === "function" ? crypto.randomUUID() : randomId();
            localStorage.setItem(DEVICE_KEY, id);
        }
        return id;
    } catch (err) {
        console.warn("Could not keep a device ID:", err);
        return null;
    }
}

// A version-4 UUID, for browsers without crypto.randomUUID (non-HTTPS pages).
function randomId() {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

// --- Dates (puzzles change at midnight UTC) ---------------------------------

export function puzzleOnDate(launchDate, when) {
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
