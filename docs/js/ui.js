const SUGGESTION_LABELS = {
    "similar word": "💡 Similar Word",
    hint: "🧠 Hint",
};

export class GameUI {
    constructor(apiClient) {
        this.api = apiClient;
        this.gameOver = false;

        // Elements
        this.statusEl = document.getElementById("status");
        this.formEl = document.getElementById("guess-form");
        this.inputEl = document.getElementById("guess-input");
        this.resultSection = document.getElementById("result");
        this.resultText = document.getElementById("result-text");
        this.scoreText = document.getElementById("score-text");
        this.playAgainButton = document.getElementById("play-again-button");
        this.historySection = document.getElementById("history");
        this.historyList = document.getElementById("history-list");
        this.guessButton = document.getElementById("guess-button");
        this.similarWordButton = document.getElementById("similar-word-button");
        this.hintButton = document.getElementById("hint-button");
        this.quitButton = document.getElementById("quit-button");

        // Bind events
        this.formEl.addEventListener("submit", (e) => this.handleGuessSubmit(e));
        this.similarWordButton.addEventListener("click", () => this.handleSimilarWordClick());
        this.hintButton.addEventListener("click", () => this.handleHintClick());
        this.quitButton.addEventListener("click", () => this.handleQuitClick());
        if (this.playAgainButton) {
            this.playAgainButton.addEventListener("click", () => this.handlePlayAgainClick());
        }
    }

    setStatus(message, type = "info") {
        this.statusEl.textContent = message;
        this.statusEl.classList.remove("status--ok", "status--error");
        if (type === "ok") this.statusEl.classList.add("status--ok");
        if (type === "error") this.statusEl.classList.add("status--error");
    }

    async init() {
        try {
            const data = await this.api.checkHealth();
            if (data.status === "ok") {
                this.setStatus("Server online. Start guessing!", "ok");
            } else {
                this.setStatus("Server reachable but engine not initialized.", "error");
            }
        } catch (err) {
            console.error("Health check failed:", err);
            this.setStatus("Cannot reach server. Check your backend URL.", "error");
        }
    }

    renderResult(result) {
        this.resultSection.classList.remove("hidden");
        this.resultText.className = "";
        if (this.scoreText) {
            this.scoreText.textContent = "";
        }

        if (!result.valid) {
            this.resultText.textContent = `Invalid guess: ${result.error}`;
            this.resultText.classList.add("result-text-error");
            return;
        }

        if (result.is_correct) {
            this.resultText.textContent = `🎉 Correct! "${result.guess}" is the target word.`;
            this.resultText.classList.add("result-text-success");

            if (this.scoreText && typeof result.score === "number") {
                this.scoreText.textContent = `Final score: ${result.score} points`;
            }
            return;
        }

        const { guess, rank, total, similarity, percentile, hotness } = result;
        this.resultText.textContent = `Guess "${guess}": rank #${rank}/${total - 1
            }, similarity=${similarity.toFixed(4)} (${percentile.toFixed(1)} percentile) — ${hotness}`;

        this.applyHotnessColor(hotness);
    }

    applyHotnessColor(hotness) {
        if (["Boiling", "Very hot", "Hot", "Warm"].includes(hotness)) {
            this.resultText.classList.add("result-text-warm");
        } else if (["Cool", "Cold", "Freezing"].includes(hotness)) {
            this.resultText.classList.add("result-text-cold");
        }
    }

    addToHistory(result) {
        this.historySection.classList.remove("hidden");
        const li = document.createElement("li");

        if (result.type in SUGGESTION_LABELS) {
            li.textContent = `${SUGGESTION_LABELS[result.type]}: try "${result.word}" — rank #${result.rank}/${result.total - 1
                }, sim=${result.similarity.toFixed(3)}, ${result.hotness}`;
        } else if (result.type === "quit") {
            if (typeof result.score === "number") {
                li.textContent = `🚪 You quit. The answer was "${result.answer}". Final score: ${result.score} points.`;
            } else {
                li.textContent = `🚪 You quit. The answer was "${result.answer}".`;
            }
        } else if (!result.valid) {
            li.textContent = `❌ "${result.guess}" — invalid (${result.error})`;
        } else if (result.is_correct) {
            if (typeof result.score === "number") {
                li.textContent = `✅ "${result.guess}" — CORRECT! Final score: ${result.score} points.`;
            } else {
                li.textContent = `✅ "${result.guess}" — CORRECT!`;
            }
        } else {
            li.textContent = `⭐ "${result.guess}" — rank #${result.rank}/${result.total - 1
                }, sim=${result.similarity.toFixed(3)}, ${result.hotness}`;
        }

        this.historyList.prepend(li);
    }

    async handleGuessSubmit(event) {
        event.preventDefault();
        if (this.gameOver) return;

        const word = this.inputEl.value.trim();
        if (!word) return;

        this.guessButton.disabled = true;

        try {
            const data = await this.api.makeGuess(word);
            this.renderResult(data);
            this.addToHistory(data);

            if (data.valid && data.is_correct) {
                this.endGame();
            }
        } catch (err) {
            console.error("Guess request failed:", err);
            this.showError("Error communicating with the server. Please try again.");
        } finally {
            this.guessButton.disabled = false;
            this.inputEl.value = "";
            this.inputEl.focus();
        }
    }

    handleSimilarWordClick() {
        return this.showSuggestion("similar word", this.similarWordButton, () => this.api.getSimilarWord());
    }

    handleHintClick() {
        return this.showSuggestion("hint", this.hintButton, () => this.api.getHint());
    }

    // Shared by Similar Word and Hint: fetch a suggested word and show it.
    async showSuggestion(type, button, fetchSuggestion) {
        if (this.gameOver) return;

        const label = SUGGESTION_LABELS[type];
        button.disabled = true;
        try {
            const s = await fetchSuggestion();

            this.resultSection.classList.remove("hidden");
            this.resultText.className = "";
            if (this.scoreText) {
                this.scoreText.textContent = "";
            }
            this.resultText.textContent = `${label}: try "${s.word}" — rank #${s.rank}/${s.total - 1
                }, similarity=${s.similarity.toFixed(4)} (${s.percentile.toFixed(1)} percentile) — ${s.hotness}`;

            this.applyHotnessColor(s.hotness);
            this.addToHistory({ ...s, type });
        } catch (err) {
            console.error(`${type} request failed:`, err);
            this.showError(`Error fetching a ${type} from the server. Please try again.`);
        } finally {
            button.disabled = false;
        }
    }

    async handleQuitClick() {
        if (this.gameOver) return;

        this.disableControls();

        try {
            const data = await this.api.quitGame();
            this.gameOver = true;
            this.inputEl.disabled = true;

            this.resultSection.classList.remove("hidden");
            this.resultText.className = "result-text-error";
            this.resultText.textContent = `🚪 You quit. The answer was "${data.answer}".`;

            if (this.scoreText && typeof data.score === "number") {
                this.scoreText.textContent = `Final score: ${data.score} points`;
            }

            this.addToHistory({ ...data, type: "quit" });
            this.showPlayAgainButton();
        } catch (err) {
            console.error("Quit request failed:", err);
            this.showError("Error quitting the game. Please try again or reload the page.");
            this.enableControls();
        }
    }

    handlePlayAgainClick() {
        // Frontend-only reset. Backend target has already been reset on
        // correct/quit via the API layer.
        this.gameOver = false;
        this.enableControls();
        this.inputEl.disabled = false;
        this.inputEl.value = "";
        this.inputEl.focus();

        // Clear current result display but keep history
        this.resultText.textContent = "";
        this.resultText.className = "";
        if (this.scoreText) {
            this.scoreText.textContent = "";
        }
        this.resultSection.classList.add("hidden");

        // Hide the Play Again button
        if (this.playAgainButton) {
            this.playAgainButton.classList.add("hidden");
        }

        this.setStatus("New round started. Make a guess!", "ok");
    }

    endGame() {
        this.gameOver = true;
        this.disableControls();
        this.inputEl.disabled = true;
        this.showPlayAgainButton();
    }

    showPlayAgainButton() {
        if (this.playAgainButton) {
            this.playAgainButton.classList.remove("hidden");
        }
    }

    disableControls() {
        this.guessButton.disabled = true;
        this.similarWordButton.disabled = true;
        this.hintButton.disabled = true;
        this.quitButton.disabled = true;
    }

    enableControls() {
        this.guessButton.disabled = false;
        this.similarWordButton.disabled = false;
        this.hintButton.disabled = false;
        this.quitButton.disabled = false;
    }

    showError(msg) {
        this.resultSection.classList.remove("hidden");
        this.resultText.textContent = msg;
        this.resultText.className = "result-text-error";
        if (this.scoreText) {
            this.scoreText.textContent = "";
        }
    }
}
