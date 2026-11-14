import {
    Progress,
    dateOfPuzzle,
    deviceId,
    formatDate,
    msUntilNextPuzzle,
    puzzleOnDate,
} from "./storage.js";

// Revealed words in the history. "similar word" entries come from saves made
// before Hint and Similar Word became one Hint.
const SUGGESTION_LABELS = {
    "similar word": "🧠 Hint",
    hint: "🧠 Hint",
};

// Help comes in a fixed order, only when the player is stuck: Clue 1, 2 and
// 3 (written clues), then Hint 1 and 2 (a word ranked 6-10, then 2-5). The
// first needs HELP_FIRST_AFTER guesses; each one needs HELP_STUCK_RUN guesses
// in a row, since the last help, with no new best rank. A puzzle without
// clues goes straight to the hints, with the same gates.
const HELP_FIRST_AFTER = 10;
const HELP_STUCK_RUN = 5;
// Points each use costs, in order. Mirrors backend/scoring.py.
const CLUE_COSTS = [5, 10, 15];
const HINT_COSTS = [20, 25];
const HELP_TYPES = new Set(["clue", "hint", "similar word"]);

const guessCount = (n) => `${n} more guess${n === 1 ? "" : "es"}`;
const players = (n) => `${n} player${n === 1 ? "" : "s"}`;

// "6–10", or "101+" for the last bar.
const bucketLabel = (b) => (b.high === null ? `${b.low}+` : `${b.low}–${b.high}`);

// How many more guesses until the next help unlocks, and whether they must
// be without a new best (false while the first-help guess count is short).
function helpProgress(game) {
    let best = null;
    let guesses = 0;
    let run = 0; // guesses in a row, since the last help, with no new best
    let helped = false;
    for (const entry of game.entries) {
        if (HELP_TYPES.has(entry.type)) {
            run = 0;
            helped = true;
        }
        if (typeof entry.rank !== "number") continue; // invalid guesses don't count
        const improved = best === null || entry.rank < best;
        if (improved) best = entry.rank;
        if (entry.type === "guess") {
            guesses += 1;
            run = improved ? 0 : run + 1;
        }
    }
    const first = helped ? 0 : Math.max(0, HELP_FIRST_AFTER - guesses);
    const stuck = Math.max(0, HELP_STUCK_RUN - run);
    return { needed: Math.max(first, stuck), stuck: stuck >= first };
}

// The next help on the ladder: { kind: "clue" | "hint", number, cost }, or null.
function nextHelp(game) {
    const cluesLeft = game.clueTotal === null || game.clues.length < game.clueTotal;
    if (cluesLeft && game.clues.length < CLUE_COSTS.length) {
        return { kind: "clue", number: game.clues.length + 1, cost: CLUE_COSTS[game.clues.length] };
    }
    if (game.hintCount < HINT_COSTS.length) {
        return { kind: "hint", number: game.hintCount + 1, cost: HINT_COSTS[game.hintCount] };
    }
    return null;
}

// '"cats" (as "cat")' when a plural or verb form counted as its base word.
function describeGuess(result) {
    if (result.matched && result.matched !== result.guess) {
        return `"${result.guess}" (as "${result.matched}")`;
    }
    return `"${result.guess}"`;
}

function withScore(text, score) {
    return typeof score === "number" ? `${text} Final score: ${score} points.` : text;
}

// One line of the guess history.
function describeEntry(entry) {
    if (entry.type in SUGGESTION_LABELS) {
        return `${SUGGESTION_LABELS[entry.type]}: try "${entry.word}" — rank #${entry.rank}/${entry.total
            }, sim=${entry.similarity.toFixed(3)}, ${entry.hotness}`;
    }
    if (entry.type === "clue") {
        return `🧩 Clue ${entry.number}/${entry.total}: ${entry.clue}`;
    }
    if (entry.type === "quit") {
        return withScore(`🚪 You quit. The answer was "${entry.answer}".`, entry.score);
    }
    if (!entry.valid) {
        return `❌ "${entry.guess}" — invalid (${entry.error})`;
    }
    if (entry.is_correct) {
        return withScore(`✅ ${describeGuess(entry)} — CORRECT!`, entry.score);
    }
    return `⭐ ${describeGuess(entry)} — rank #${entry.rank}/${entry.total
        }, sim=${entry.similarity.toFixed(3)}, ${entry.hotness}`;
}

// "3:07", or "1:03:07" past an hour.
function formatClock(ms) {
    const total = Math.max(0, Math.floor(ms / 1000));
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = String(total % 60).padStart(2, "0");
    return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

function formatCountdown(ms) {
    const total = Math.max(0, Math.floor(ms / 1000));
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(Math.floor(total / 3600))}:${pad(Math.floor((total % 3600) / 60))}:${pad(total % 60)}`;
}

export class GameUI {
    constructor(apiClient) {
        this.api = apiClient;
        this.progress = new Progress();
        this.launchDate = null; // date of puzzle #1, from the server
        this.today = null; // today's puzzle number
        this.puzzle = null; // the puzzle on screen
        this.game = null; // its saved progress

        const $ = (id) => document.getElementById(id);
        this.statusEl = $("status");
        this.titleEl = $("puzzle-title");
        this.streakEl = $("streak");
        this.gameSection = $("game");
        this.archiveSection = $("archive");
        this.archiveList = $("archive-list");
        this.formEl = $("guess-form");
        this.inputEl = $("guess-input");
        this.resultSection = $("result");
        this.resultText = $("result-text");
        this.scoreText = $("score-text");
        this.nextPuzzleEl = $("next-puzzle");
        this.playPastButton = $("play-past-button");
        this.historySection = $("history");
        this.historyList = $("history-list");
        this.guessButton = $("guess-button");
        this.hintButton = $("hint-button");
        this.quitButton = $("quit-button");
        this.clueButton = $("clue-button");
        this.helpNote = $("help-note");
        this.cluesSection = $("clues");
        this.clueList = $("clue-list");
        this.helpBusy = false; // a clue or hint request is on its way
        this.startSection = $("start");
        this.playButton = $("play-button");
        this.clockEl = $("clock");
        this.standingEl = $("standing");
        this.standingBeat = $("standing-beat");
        this.standingRate = $("standing-rate");
        this.chartEl = $("standing-chart");
        this.chartBars = $("chart-bars");
        this.deviceId = deviceId(); // counts this browser once per puzzle

        this.formEl.addEventListener("submit", (e) => this.handleGuessSubmit(e));
        this.playButton.addEventListener("click", () => this.handlePlayClick());
        this.hintButton.addEventListener("click", () => this.handleHintClick());
        this.clueButton.addEventListener("click", () => this.handleClueClick());
        this.quitButton.addEventListener("click", () => this.handleQuitClick());
        this.playPastButton.addEventListener("click", () => this.goTo("archive"));
        $("archive-button").addEventListener("click", () => this.goTo("archive"));
        $("today-button").addEventListener("click", () => this.goTo(""));
        window.addEventListener("hashchange", () => this.route());
    }

    get gameOver() {
        return !this.game || this.game.status !== "playing";
    }

    setStatus(message, type = "info") {
        this.statusEl.textContent = message;
        this.statusEl.classList.remove("status--ok", "status--error");
        if (type === "ok") this.statusEl.classList.add("status--ok");
        if (type === "error") this.statusEl.classList.add("status--error");
    }

    async init() {
        this.disableControls();
        try {
            const today = await this.api.getToday();
            this.launchDate = today.launch_date;
            this.today = today.puzzle;
        } catch (err) {
            console.error("Loading today's puzzle failed:", err);
            this.setStatus("Cannot reach the server, or there's no puzzle today. Try again later.", "error");
            return;
        }
        this.setStatus("Server online.", "ok");
        this.route();
        setInterval(() => this.tick(), 1000);
    }

    // --- Navigation: "" is today, "#7" is puzzle 7, "#archive" the list ------

    goTo(hash) {
        const target = hash ? `#${hash}` : "";
        if (location.hash === target || (target === "" && location.hash === "#")) {
            this.route();
        } else {
            location.hash = target;
        }
    }

    route() {
        if (this.today === null) return;
        const hash = location.hash.replace("#", "");
        if (hash === "archive") {
            this.showArchive();
            return;
        }
        const n = Number.parseInt(hash, 10);
        this.openPuzzle(Number.isInteger(n) && n >= 1 && n <= this.today ? n : this.today);
    }

    openPuzzle(puzzle) {
        this.puzzle = puzzle;
        this.game = this.progress.game(puzzle);
        this.archiveSection.classList.add("hidden");
        this.gameSection.classList.remove("hidden");
        this.renderTitle();
        this.renderStreak();

        this.historyList.textContent = "";
        this.historySection.classList.toggle("hidden", this.game.entries.length === 0);
        this.game.entries.forEach((entry) => this.addToHistory(entry));
        this.renderClues();
        if (!this.gameOver) this.loadClueTotal(puzzle);

        this.resultSection.classList.add("hidden");
        this.standingEl.classList.add("hidden");
        this.nextPuzzleEl.classList.add("hidden");
        this.playPastButton.classList.add("hidden");
        this.inputEl.value = "";

        // Not started yet: show the Play button instead of the board.
        const waiting = !this.gameOver && this.game.startedAt === null;
        this.startSection.classList.toggle("hidden", !waiting);
        this.formEl.classList.toggle("hidden", waiting);
        this.playButton.textContent =
            this.puzzle === this.today ? "▶ Play today's game" : `▶ Play puzzle #${this.puzzle}`;
        this.renderClock();

        if (waiting) {
            this.disableControls();
            this.playButton.focus();
        } else if (this.gameOver) {
            this.showFinalResult();
        } else {
            this.enableControls();
            this.inputEl.focus();
        }
    }

    // Pressing Play starts the clock. It's wall time: it keeps running while
    // the tab is hidden or closed, and a reload keeps the original start.
    handlePlayClick() {
        if (this.gameOver || this.game.startedAt !== null) return;
        this.game.startedAt = Date.now();
        this.save();
        this.startSection.classList.add("hidden");
        this.formEl.classList.remove("hidden");
        this.renderClock();
        this.enableControls();
        this.inputEl.focus();
    }

    renderClock() {
        const g = this.game;
        const end = g.status === "playing" ? Date.now() : g.finishedAt;
        const shown = g.startedAt !== null && end !== null;
        this.clockEl.classList.toggle("hidden", !shown);
        if (shown) this.clockEl.textContent = `⏱ ${formatClock(end - g.startedAt)}`;
    }

    // Ask the server how many clues the puzzle has, so a puzzle without clues
    // offers hints instead. On failure the Clue button finds out when used.
    async loadClueTotal(puzzle) {
        try {
            const info = await this.api.getPuzzle(puzzle);
            if (puzzle !== this.puzzle || this.gameOver) return;
            this.game.clueTotal = info.clue_total;
            this.renderHelp();
        } catch (err) {
            console.warn("Could not load the puzzle's clue count:", err);
        }
    }

    renderTitle() {
        const date = formatDate(dateOfPuzzle(this.launchDate, this.puzzle));
        const suffix = this.puzzle === this.today ? " (today)" : "";
        this.titleEl.textContent = `Puzzle #${this.puzzle} · ${date}${suffix}`;
    }

    renderStreak() {
        const { current, best } = this.progress.streaks(this.today);
        this.streakEl.textContent = `🔥 Streak: ${current} · Best: ${best}`;
    }

    showArchive() {
        this.gameSection.classList.add("hidden");
        this.archiveSection.classList.remove("hidden");
        this.titleEl.textContent = "Past puzzles";
        this.renderStreak();

        this.archiveList.textContent = "";
        for (let n = this.today; n >= 1; n -= 1) {
            const li = document.createElement("li");
            const button = document.createElement("button");
            button.type = "button";
            button.className = "archive-item";
            const date = formatDate(dateOfPuzzle(this.launchDate, n));
            button.textContent = `#${n} · ${date}${n === this.today ? " (today)" : ""} — ${this.describeStatus(n)}`;
            button.addEventListener("click", () => this.goTo(String(n)));
            li.appendChild(button);
            this.archiveList.appendChild(li);
        }
    }

    describeStatus(puzzle) {
        if (!this.progress.has(puzzle)) return "Not played";
        const game = this.progress.game(puzzle);
        if (game.status === "won") return `✅ Solved · ${game.score ?? 0} pts`;
        if (game.status === "quit") return "🏳️ Gave up";
        const guesses = game.entries.filter((e) => e.type === "guess" && e.valid).length;
        return `▶️ In progress · ${guesses} guess${guesses === 1 ? "" : "es"}`;
    }

    // Once a second: the countdown, and noticing a new day has started.
    tick() {
        const nowToday = puzzleOnDate(this.launchDate);
        if (nowToday > this.today) {
            this.today = nowToday;
            if (!this.archiveSection.classList.contains("hidden")) {
                this.showArchive();
            } else {
                this.renderTitle();
                this.renderStreak();
            }
            this.setStatus("A new puzzle is out! Press \"Today's puzzle\" to play it.", "ok");
        }
        if (this.game && this.archiveSection.classList.contains("hidden")) this.renderClock();
        if (!this.nextPuzzleEl.classList.contains("hidden")) {
            this.nextPuzzleEl.textContent = `Next puzzle in ${formatCountdown(msUntilNextPuzzle())}`;
        }
    }

    // --- Saved progress ---------------------------------------------------

    save() {
        this.progress.save(this.puzzle, this.game);
    }

    recordRank(rank) {
        if (typeof rank !== "number") return;
        if (this.game.bestRank === null || rank < this.game.bestRank) this.game.bestRank = rank;
    }

    stats() {
        const g = this.game;
        return {
            elapsed_seconds: g.startedAt === null ? 0 : (Date.now() - g.startedAt) / 1000,
            guess_count: g.entries.filter((e) => e.type === "guess" && e.valid).length,
            clue_count: g.clues.length,
            hint_count: g.hintCount,
            best_rank: g.bestRank,
        };
    }

    // --- Rendering --------------------------------------------------------

    showResultLine(text, className = "") {
        this.resultSection.classList.remove("hidden");
        this.resultText.textContent = text;
        this.resultText.className = className;
        this.scoreText.textContent = "";
    }

    renderResult(result) {
        if (!result.valid) {
            this.showResultLine(`Invalid guess: ${result.error}`, "result-text-error");
            return;
        }
        if (result.is_correct) {
            this.showResultLine(
                `🎉 Correct! "${result.matched || result.guess}" is the hidden word.`,
                "result-text-success",
            );
            if (typeof result.score === "number") {
                this.scoreText.textContent = `Final score: ${result.score} points`;
            }
            return;
        }
        const { rank, total, similarity, percentile, hotness } = result;
        this.showResultLine(
            `Guess ${describeGuess(result)}: rank #${rank}/${total}, similarity=${similarity.toFixed(4)} (${percentile.toFixed(1)} percentile) — ${hotness}`,
        );
        this.applyHotnessColor(hotness);
    }

    renderQuit(data) {
        this.showResultLine(`🚪 You quit. The answer was "${data.answer}".`, "result-text-error");
        if (typeof data.score === "number") {
            this.scoreText.textContent = `Final score: ${data.score} points`;
        }
    }

    // A finished puzzle: its result, the countdown (today only), and a way on.
    showFinalResult() {
        this.disableControls();
        const last = this.game.entries[this.game.entries.length - 1];
        if (last && last.type === "quit") {
            this.renderQuit(last);
        } else if (last) {
            this.renderResult(last);
        }
        this.nextPuzzleEl.classList.toggle("hidden", this.puzzle !== this.today);
        this.playPastButton.classList.remove("hidden");
        this.renderHelp(); // clears the help note
        this.renderStreak();
        this.tick();
        this.loadStanding(this.puzzle);
    }

    // --- How the result compares with the puzzle's on-the-day players ------

    // The first request after the database has been idle can take a second
    // or so (Neon wakes up), hence the loading line. If results are off or
    // unreachable, the panel just goes away.
    async loadStanding(puzzle) {
        this.standingEl.classList.remove("hidden");
        this.standingBeat.textContent = "Loading how others did…";
        this.standingRate.textContent = "";
        this.chartEl.classList.add("hidden");
        try {
            const data = await this.api.getResults(puzzle, this.deviceId, this.game.score);
            if (puzzle !== this.puzzle || !this.gameOver) return;
            this.renderStanding(data);
        } catch (err) {
            if (puzzle !== this.puzzle) return;
            console.warn("Could not load the day's results:", err);
            this.standingEl.classList.add("hidden");
        }
    }

    renderStanding(data) {
        const today = this.puzzle === this.today;
        const n = data.players;
        let beat;
        if (data.beat_percent !== null) {
            beat = today
                ? `You beat ${data.beat_percent}% of today's players.`
                : `${data.counted ? "You beat" : "You'd have beaten"} ${data.beat_percent}% of the players on its day.`;
        } else if (n === 0) {
            beat = today ? "No one else has finished today's puzzle yet." : "No one played this puzzle on its day.";
        } else if (n < data.min_players) {
            beat = today ? `Only ${players(n)} so far.` : `Only ${players(n)} played it on its day.`;
        } else {
            beat = today ? `${players(n)} so far today.` : `${players(n)} played it on its day.`;
        }
        this.standingBeat.textContent = beat;

        let rate = n > 0 ? `Solve rate: ${data.solve_rate}% (${data.solvers} of ${n})` : "";
        if (!data.counted && !today) rate += `${rate ? " · " : ""}Past puzzles played later aren't counted.`;
        this.standingRate.textContent = rate;

        this.renderChart(data.buckets, data.solvers);
    }

    // One bar per range of guess counts; the player's own bar is highlighted
    // when they solved.
    renderChart(buckets, solvers) {
        this.chartBars.textContent = "";
        this.chartEl.classList.toggle("hidden", solvers === 0);
        if (solvers === 0) return;

        const g = this.game;
        const mine = g.status === "won"
            ? g.entries.filter((e) => e.type === "guess" && e.valid).length
            : null;
        const most = Math.max(...buckets.map((b) => b.count));
        for (const b of buckets) {
            const you = mine !== null && mine >= b.low && (b.high === null || mine <= b.high);
            const li = document.createElement("li");
            if (you) li.classList.add("chart-you");

            const label = document.createElement("span");
            label.className = "chart-label";
            label.textContent = bucketLabel(b);

            const track = document.createElement("span");
            track.className = "chart-track";
            const fill = document.createElement("span");
            fill.className = "chart-fill";
            fill.style.display = "block";
            fill.style.width = b.count ? `${Math.max(2, (100 * b.count) / most)}%` : "0";
            track.appendChild(fill);

            const count = document.createElement("span");
            count.className = "chart-count";
            count.textContent = you ? `${b.count} · you` : String(b.count);

            li.append(label, track, count);
            li.title = `${b.count} solver${b.count === 1 ? "" : "s"} took ${bucketLabel(b)} guesses${you ? " (you too)" : ""}`;
            this.chartBars.appendChild(li);
        }
    }

    renderClues() {
        this.clueList.textContent = "";
        for (const clue of this.game.clues) {
            const li = document.createElement("li");
            li.textContent = clue;
            this.clueList.appendChild(li);
        }
        this.cluesSection.classList.toggle("hidden", this.game.clues.length === 0);
        this.renderHelp();
    }

    // The Clue and Hint buttons, and a note on what unlocks next.
    renderHelp() {
        const g = this.game;
        const next = this.gameOver ? null : nextHelp(g);
        const { needed, stuck } = helpProgress(g);
        const onlyAnswerLeft = g.bestRank !== null && g.bestRank <= 2;
        const ready = next !== null && needed === 0 && !(next.kind === "hint" && onlyAnswerLeft);

        this.clueButton.textContent =
            next && next.kind === "clue" ? `🧩 Clue ${next.number} (−${next.cost})` : "🧩 Clue";
        this.hintButton.textContent =
            next && next.kind === "hint" ? `🧠 Hint ${next.number} (−${next.cost})` : "🧠 Hint";
        this.clueButton.disabled = !(ready && next.kind === "clue") || this.helpBusy;
        this.hintButton.disabled = !(ready && next.kind === "hint") || this.helpBusy;

        let note = "";
        if (this.gameOver) {
            note = "";
        } else if (next === null) {
            note = "You've used every clue and hint.";
        } else if (next.kind === "hint" && onlyAnswerLeft) {
            note = "Your best is #2, so only the answer is closer: no hint can help.";
        } else {
            const name = `${next.kind === "clue" ? "Clue" : "Hint"} ${next.number}`;
            const noClues =
                next.kind === "hint" && g.clueTotal === 0 && g.hintCount === 0 ? "This puzzle has no clues. " : "";
            if (needed === 0) {
                note = `${noClues}${name} is ready (−${next.cost} points).`;
            } else {
                const how = stuck ? " without a new best" : "";
                note = `${noClues}${name} unlocks after ${guessCount(needed)}${how}.`;
            }
        }
        this.helpNote.textContent = note;
    }

    applyHotnessColor(hotness) {
        if (["Boiling", "Very hot", "Hot", "Warm"].includes(hotness)) {
            this.resultText.classList.add("result-text-warm");
        } else if (["Cool", "Cold", "Freezing"].includes(hotness)) {
            this.resultText.classList.add("result-text-cold");
        }
    }

    addToHistory(entry) {
        this.historySection.classList.remove("hidden");
        const li = document.createElement("li");
        li.textContent = describeEntry(entry);
        this.historyList.prepend(li);
    }

    record(entry) {
        this.game.entries.push(entry);
        this.save();
        this.addToHistory(entry);
        this.renderHelp();
    }

    // --- Actions ----------------------------------------------------------

    async handleGuessSubmit(event) {
        event.preventDefault();
        if (this.gameOver) return;

        const word = this.inputEl.value.trim();
        if (!word) return;

        const puzzle = this.puzzle;
        this.guessButton.disabled = true;

        try {
            const data = await this.api.makeGuess(puzzle, word, this.stats(), this.deviceId);
            if (puzzle !== this.puzzle) return; // the player moved to another puzzle

            if (data.valid) this.recordRank(data.rank);
            if (data.valid && data.is_correct) {
                this.game.status = "won";
                this.game.finishedAt = Date.now();
                this.game.score = data.score;
                this.game.onTheDay = puzzle === puzzleOnDate(this.launchDate);
            }
            this.renderResult(data);
            this.record({ ...data, type: "guess" });
            if (this.gameOver) this.showFinalResult();
        } catch (err) {
            console.error("Guess request failed:", err);
            this.showResultLine("Error communicating with the server. Please try again.", "result-text-error");
        } finally {
            this.inputEl.value = "";
            // A winning guess has already disabled everything.
            if (!this.gameOver) {
                this.guessButton.disabled = false;
                this.inputEl.focus();
            }
        }
    }

    // Is this kind of help unlocked right now?
    helpReady(kind) {
        if (this.gameOver || this.helpBusy) return false;
        const next = nextHelp(this.game);
        return next !== null && next.kind === kind && helpProgress(this.game).needed === 0;
    }

    async handleHintClick() {
        if (!this.helpReady("hint")) return;

        const puzzle = this.puzzle;
        this.helpBusy = true;
        this.renderHelp();
        try {
            const s = await this.api.getHint(puzzle, this.game.bestRank, this.game.hintCount);
            if (puzzle !== this.puzzle) return;

            this.game.hintCount += 1;
            this.recordRank(s.rank);
            this.showResultLine(
                `🧠 Hint: try "${s.word}" — rank #${s.rank}/${s.total}, similarity=${s.similarity.toFixed(4)} (${s.percentile.toFixed(1)} percentile) — ${s.hotness}`,
            );
            this.applyHotnessColor(s.hotness);
            this.record({ ...s, type: "hint" });
        } catch (err) {
            if (puzzle !== this.puzzle) return;
            if (err.status === 409) {
                this.showResultLine("No hint can help now: only the answer is closer than your best.", "result-text-error");
            } else {
                console.error("Hint request failed:", err);
                this.showResultLine("Error fetching a hint from the server. Please try again.", "result-text-error");
            }
        } finally {
            this.helpBusy = false;
            if (puzzle === this.puzzle) this.renderHelp();
        }
    }

    async handleClueClick() {
        if (!this.helpReady("clue")) return;

        const puzzle = this.puzzle;
        this.helpBusy = true;
        this.renderHelp();
        try {
            const data = await this.api.getClue(puzzle, this.game.clues.length);
            if (puzzle !== this.puzzle) return;

            this.game.clues.push(data.clue);
            this.game.clueTotal = data.total;
            this.showResultLine(`🧩 Clue ${data.number}/${data.total}: ${data.clue}`);
            this.record({ ...data, type: "clue" });
            this.renderClues();
        } catch (err) {
            if (puzzle !== this.puzzle) return;
            if (err.status === 404 || err.status === 409) {
                // No clues for this puzzle, or none left: stop offering them.
                this.game.clueTotal = this.game.clues.length;
                this.save();
            } else {
                console.error("Clue request failed:", err);
                this.showResultLine("Error fetching a clue from the server. Please try again.", "result-text-error");
            }
        } finally {
            this.helpBusy = false;
            if (puzzle === this.puzzle) this.renderHelp();
        }
    }

    async handleQuitClick() {
        if (this.gameOver) return;

        const puzzle = this.puzzle;
        this.disableControls();
        try {
            const data = await this.api.quitGame(puzzle, this.stats(), this.deviceId);
            if (puzzle !== this.puzzle) return;

            this.game.status = "quit";
            this.game.finishedAt = Date.now();
            this.game.score = data.score;
            this.record({ ...data, type: "quit" });
            this.showFinalResult();
        } catch (err) {
            console.error("Quit request failed:", err);
            this.showResultLine("Error quitting the game. Please try again.", "result-text-error");
            this.enableControls();
        }
    }

    disableControls() {
        for (const el of [this.inputEl, this.guessButton, this.hintButton, this.quitButton, this.clueButton]) {
            el.disabled = true;
        }
    }

    enableControls() {
        for (const el of [this.inputEl, this.guessButton, this.quitButton]) {
            el.disabled = false;
        }
        this.renderHelp();
    }
}
