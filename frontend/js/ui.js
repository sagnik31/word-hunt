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
        this.historySection = document.getElementById("history");
        this.historyList = document.getElementById("history-list");
        this.guessButton = document.getElementById("guess-button");
        this.hintButton = document.getElementById("hint-button");
        this.quitButton = document.getElementById("quit-button");

        // Bind events
        this.formEl.addEventListener("submit", (e) => this.handleGuessSubmit(e));
        this.hintButton.addEventListener("click", () => this.handleHintClick());
        this.quitButton.addEventListener("click", () => this.handleQuitClick());
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

        if (!result.valid) {
            this.resultText.textContent = `Invalid guess: ${result.error}`;
            this.resultText.classList.add("result-text-error");
            return;
        }

        if (result.is_correct) {
            this.resultText.textContent = `🎉 Correct! "${result.guess}" is the target word.`;
            this.resultText.classList.add("result-text-success");
            return;
        }

        const { guess, rank, total, similarity, percentile, hotness } = result;
        this.resultText.textContent = `Guess "${guess}": rank #${rank}/${total - 1}, similarity=${similarity.toFixed(
            4
        )} (${percentile.toFixed(1)} percentile) — ${hotness}`;

        this.applyHotnessColor(hotness);
    }

    applyHotnessColor(hotness) {
        if (["Boiling", "Very hot", "Hot"].includes(hotness)) {
            this.resultText.classList.add("result-text-warm");
        } else if (["Warm", "Cool"].includes(hotness)) {
            this.resultText.classList.add("result-text-cold");
        } else if (["Cold", "Freezing"].includes(hotness)) {
            this.resultText.classList.add("result-text-cold");
        }
    }

    addToHistory(result) {
        this.historySection.classList.remove("hidden");
        const li = document.createElement("li");

        if (result.type === "hint") {
            li.textContent = `💡 Hint: try "${result.word}" — rank #${result.rank}/${result.total - 1
                }, sim=${result.similarity.toFixed(3)}, ${result.hotness}`;
        } else if (result.type === "quit") {
            li.textContent = `🚪 You quit. The answer was "${result.answer}".`;
        } else if (!result.valid) {
            li.textContent = `❌ "${result.guess}" — invalid (${result.error})`;
        } else if (result.is_correct) {
            li.textContent = `✅ "${result.guess}" — CORRECT!`;
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

    async handleHintClick() {
        if (this.gameOver) return;

        this.hintButton.disabled = true;
        try {
            const hint = await this.api.getHint();

            this.resultSection.classList.remove("hidden");
            this.resultText.className = "";
            this.resultText.textContent = `💡 Hint: try "${hint.word}" — rank #${hint.rank}/${hint.total - 1
                }, similarity=${hint.similarity.toFixed(4)} (${hint.percentile.toFixed(
                    1
                )} percentile) — ${hint.hotness}`;

            this.applyHotnessColor(hint.hotness);
            this.addToHistory({ ...hint, type: "hint" });
        } catch (err) {
            console.error("Hint request failed:", err);
            this.showError("Error fetching a hint from the server. Please try again.");
        } finally {
            this.hintButton.disabled = false;
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

            this.addToHistory({ ...data, type: "quit" });
        } catch (err) {
            console.error("Quit request failed:", err);
            this.showError("Error quitting the game. Please try again or reload the page.");
            this.enableControls();
        }
    }

    endGame() {
        this.gameOver = true;
        this.disableControls();
        this.inputEl.disabled = true;
    }

    disableControls() {
        this.guessButton.disabled = true;
        this.hintButton.disabled = true;
        this.quitButton.disabled = true;
    }

    enableControls() {
        this.guessButton.disabled = false;
        this.hintButton.disabled = false;
        this.quitButton.disabled = false;
    }

    showError(msg) {
        this.resultSection.classList.remove("hidden");
        this.resultText.textContent = msg;
        this.resultText.className = "result-text-error";
    }
}
