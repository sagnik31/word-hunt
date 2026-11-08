import {
    Progress,
    dateOfPuzzle,
    formatDate,
    msUntilNextPuzzle,
    puzzleOnDate,
} from "./storage.js";

const SUGGESTION_LABELS = {
    "similar word": "💡 Similar Word",
    hint: "🧠 Hint",
};

// Clues unlock when the player is stuck: the first after CLUE_FIRST_AFTER
// guesses, and each one only once the last CLUE_STUCK_RUN guesses since the
// previous clue brought no new best rank.
const CLUE_FIRST_AFTER = 10;
const CLUE_STUCK_RUN = 5;

function guessesUntilClue(game) {
    let best = null;
    let guesses = 0;
    let run = 0; // guesses in a row, since the last clue, with no new best
    for (const entry of game.entries) {
        if (entry.type === "clue") {
            run = 0;
            continue;
        }
        if (typeof entry.rank !== "number") continue; // invalid guesses don't count
        const improved = best === null || entry.rank < best;
        if (improved) best = entry.rank;
        if (entry.type === "guess") {
            guesses += 1;
            run = improved ? 0 : run + 1;
        }
    }
    const first = game.clues.length === 0 ? Math.max(0, CLUE_FIRST_AFTER - guesses) : 0;
    return Math.max(first, CLUE_STUCK_RUN - run);
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
        this.similarWordButton = $("similar-word-button");
        this.hintButton = $("hint-button");
        this.quitButton = $("quit-button");
        this.clueButton = $("clue-button");
        this.clueNote = $("clue-note");
        this.cluesSection = $("clues");
        this.clueList = $("clue-list");
        this.clueBusy = false; // a clue request is on its way

        this.formEl.addEventListener("submit", (e) => this.handleGuessSubmit(e));
        this.similarWordButton.addEventListener("click", () => this.handleSimilarWordClick());
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
        this.setStatus("Server online. Start guessing!", "ok");
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

        this.resultSection.classList.add("hidden");
        this.nextPuzzleEl.classList.add("hidden");
        this.playPastButton.classList.add("hidden");
        if (this.gameOver) {
            this.showFinalResult();
        } else {
            this.enableControls();
            this.inputEl.value = "";
            this.inputEl.focus();
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
        if (!this.nextPuzzleEl.classList.contains("hidden")) {
            this.nextPuzzleEl.textContent = `Next puzzle in ${formatCountdown(msUntilNextPuzzle())}`;
        }
    }

    // --- Saved progress ---------------------------------------------------

    save() {
        this.progress.save(this.puzzle, this.game);
    }

    startClock() {
        if (this.game.startedAt === null) this.game.startedAt = Date.now();
    }

    recordRank(rank) {
        if (typeof rank !== "number") return;
        if (this.game.bestRank === null || rank < this.game.bestRank) this.game.bestRank = rank;
    }

    stats() {
        const g = this.game;
        return {
            elapsed_seconds: g.startedAt === null ? 0 : (Date.now() - g.startedAt) / 1000,
            hint_count: g.hintCount,
            similar_count: g.similarCount,
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
        this.renderClueButton(); // clears the clue note
        this.renderStreak();
        this.tick();
    }

    renderClues() {
        this.clueList.textContent = "";
        for (const clue of this.game.clues) {
            const li = document.createElement("li");
            li.textContent = clue;
            this.clueList.appendChild(li);
        }
        this.cluesSection.classList.toggle("hidden", this.game.clues.length === 0);
        this.renderClueButton();
    }

    renderClueButton() {
        const g = this.game;
        let note = "";
        let ready = false;
        if (!this.gameOver) {
            if (g.clueTotal === 0) {
                note = "This puzzle has no clues.";
            } else if (g.clueTotal !== null && g.clues.length >= g.clueTotal) {
                note = "That was the last clue.";
            } else {
                const needed = guessesUntilClue(g);
                ready = needed === 0;
                note = ready
                    ? "Stuck? A clue is ready."
                    : `Stuck? A clue unlocks after ${needed} more guess${needed === 1 ? "" : "es"} without a new best.`;
            }
        }
        this.clueButton.disabled = !ready || this.clueBusy;
        this.clueNote.textContent = note;
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
        this.renderClueButton();
    }

    // --- Actions ----------------------------------------------------------

    async handleGuessSubmit(event) {
        event.preventDefault();
        if (this.gameOver) return;

        const word = this.inputEl.value.trim();
        if (!word) return;

        const puzzle = this.puzzle;
        this.guessButton.disabled = true;
        this.startClock();

        try {
            const data = await this.api.makeGuess(puzzle, word, this.stats());
            if (puzzle !== this.puzzle) return; // the player moved to another puzzle

            if (data.valid) this.recordRank(data.rank);
            if (data.valid && data.is_correct) {
                this.game.status = "won";
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

    handleSimilarWordClick() {
        return this.showSuggestion("similar word", this.similarWordButton, "similarCount", (p, best, used) =>
            this.api.getSimilarWord(p, best, used),
        );
    }

    handleHintClick() {
        return this.showSuggestion("hint", this.hintButton, "hintCount", (p, best, used) =>
            this.api.getHint(p, best, used),
        );
    }

    // Shared by Similar Word and Hint: fetch a suggested word and show it.
    async showSuggestion(type, button, counter, fetchSuggestion) {
        if (this.gameOver) return;

        const puzzle = this.puzzle;
        const label = SUGGESTION_LABELS[type];
        button.disabled = true;
        this.startClock();
        try {
            const s = await fetchSuggestion(puzzle, this.game.bestRank, this.game[counter]);
            if (puzzle !== this.puzzle) return;

            this.game[counter] += 1;
            this.recordRank(s.rank);
            this.showResultLine(
                `${label}: try "${s.word}" — rank #${s.rank}/${s.total}, similarity=${s.similarity.toFixed(4)} (${s.percentile.toFixed(1)} percentile) — ${s.hotness}`,
            );
            this.applyHotnessColor(s.hotness);
            this.record({ ...s, type });
        } catch (err) {
            console.error(`${type} request failed:`, err);
            this.showResultLine(`Error fetching a ${type} from the server. Please try again.`, "result-text-error");
        } finally {
            if (!this.gameOver) button.disabled = false;
        }
    }

    async handleClueClick() {
        if (this.gameOver || this.clueBusy || guessesUntilClue(this.game) > 0) return;

        const puzzle = this.puzzle;
        this.clueBusy = true;
        this.renderClueButton();
        this.startClock();
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
            this.clueBusy = false;
            if (puzzle === this.puzzle) this.renderClueButton();
        }
    }

    async handleQuitClick() {
        if (this.gameOver) return;

        const puzzle = this.puzzle;
        this.disableControls();
        try {
            const data = await this.api.quitGame(puzzle, this.stats());
            if (puzzle !== this.puzzle) return;

            this.game.status = "quit";
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
        for (const el of [this.inputEl, this.guessButton, this.similarWordButton, this.hintButton, this.quitButton, this.clueButton]) {
            el.disabled = true;
        }
    }

    enableControls() {
        for (const el of [this.inputEl, this.guessButton, this.similarWordButton, this.hintButton, this.quitButton]) {
            el.disabled = false;
        }
        this.renderClueButton();
    }
}
