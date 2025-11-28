// app.js

// TODO: replace this with your actual Render API base URL
// e.g. "https://word-hunt-backend.onrender.com"
const API_BASE_URL = "https://word-hunt-cevi.onrender.com";

const healthUrl = `${API_BASE_URL}/health`;
const guessUrl = `${API_BASE_URL}/guess`;
const hintUrl = `${API_BASE_URL}/hint`;
const quitUrl = `${API_BASE_URL}/quit`;

const statusEl = document.getElementById("status");
const formEl = document.getElementById("guess-form");
const inputEl = document.getElementById("guess-input");
const resultSection = document.getElementById("result");
const resultText = document.getElementById("result-text");
const historySection = document.getElementById("history");
const historyList = document.getElementById("history-list");
const guessButton = document.getElementById("guess-button");
const hintButton = document.getElementById("hint-button");
const quitButton = document.getElementById("quit-button");

let gameOver = false;

function setStatus(message, type = "info") {
  statusEl.textContent = message;
  statusEl.classList.remove("status--ok", "status--error");
  if (type === "ok") statusEl.classList.add("status--ok");
  if (type === "error") statusEl.classList.add("status--error");
}

async function checkHealth() {
  try {
    const res = await fetch(healthUrl);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();
    if (data.status === "ok") {
      setStatus("Server online. Start guessing!", "ok");
    } else {
      setStatus("Server reachable but engine not initialized.", "error");
    }
  } catch (err) {
    console.error("Health check failed:", err);
    setStatus("Cannot reach server. Check your backend URL.", "error");
  }
}

function renderResult(result) {
  resultSection.classList.remove("hidden");
  resultText.className = "";

  if (!result.valid) {
    resultText.textContent = `Invalid guess: ${result.error}`;
    resultText.classList.add("result-text-error");
    return;
  }

  if (result.is_correct) {
    resultText.textContent = `🎉 Correct! "${result.guess}" is the target word.`;
    resultText.classList.add("result-text-success");
    return;
  }

  const { guess, rank, total, similarity, percentile, hotness } = result;
  resultText.textContent = `Guess "${guess}": rank #${rank}/${total - 1}, similarity=${similarity.toFixed(
    4
  )} (${percentile.toFixed(1)} percentile) — ${hotness}`;

  if (hotness === "Boiling" || hotness === "Very hot" || hotness === "Hot") {
    resultText.classList.add("result-text-warm");
  } else if (hotness === "Warm" || hotness === "Cool") {
    resultText.classList.add("result-text-cold");
  } else if (hotness === "Cold" || hotness === "Freezing") {
    resultText.classList.add("result-text-cold");
  }
}

function addToHistory(result) {
  historySection.classList.remove("hidden");

  const li = document.createElement("li");

  if (result.type === "hint") {
    li.textContent = `💡 Hint: try "${result.word}" — rank #${result.rank}/${
      result.total - 1
    }, sim=${result.similarity.toFixed(3)}, ${result.hotness}`;
    historyList.prepend(li);
    return;
  }

  if (result.type === "quit") {
    li.textContent = `🚪 You quit. The answer was "${result.answer}".`;
    historyList.prepend(li);
    return;
  }

  // Regular guess
  if (!result.valid) {
    li.textContent = `❌ "${result.guess}" — invalid (${result.error})`;
  } else if (result.is_correct) {
    li.textContent = `✅ "${result.guess}" — CORRECT!`;
  } else {
    li.textContent = `⭐ "${result.guess}" — rank #${result.rank}/${
      result.total - 1
    }, sim=${result.similarity.toFixed(3)}, ${result.hotness}`;
  }

  historyList.prepend(li);
}

async function handleGuessSubmit(event) {
  event.preventDefault();
  if (gameOver) return;

  const word = inputEl.value.trim();
  if (!word) return;

  const payload = { word };

  guessButton.disabled = true;

  try {
    const res = await fetch(guessUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    const data = await res.json();
    renderResult(data);
    addToHistory(data);

    if (data.valid && data.is_correct) {
      gameOver = true;
      hintButton.disabled = true;
      quitButton.disabled = true;
      inputEl.disabled = true;
    }
  } catch (err) {
    console.error("Guess request failed:", err);
    resultSection.classList.remove("hidden");
    resultText.textContent =
      "Error communicating with the server. Please try again.";
    resultText.className = "result-text-error";
  } finally {
    guessButton.disabled = false;
    inputEl.value = "";
    inputEl.focus();
  }
}

async function handleHintClick() {
  if (gameOver) return;

  hintButton.disabled = true;
  try {
    const res = await fetch(hintUrl);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const hint = await res.json();

    // Show hint in main result area
    resultSection.classList.remove("hidden");
    resultText.className = "";
    resultText.textContent = `💡 Hint: try "${hint.word}" — rank #${hint.rank}/${
      hint.total - 1
    }, similarity=${hint.similarity.toFixed(4)} (${hint.percentile.toFixed(
      1
    )} percentile) — ${hint.hotness}`;

    if (
      hint.hotness === "Boiling" ||
      hint.hotness === "Very hot" ||
      hint.hotness === "Hot"
    ) {
      resultText.classList.add("result-text-warm");
    } else {
      resultText.classList.add("result-text-cold");
    }

    addToHistory({ ...hint, type: "hint" });
  } catch (err) {
    console.error("Hint request failed:", err);
    resultSection.classList.remove("hidden");
    resultText.textContent =
      "Error fetching a hint from the server. Please try again.";
    resultText.className = "result-text-error";
  } finally {
    hintButton.disabled = false;
  }
}

async function handleQuitClick() {
  if (gameOver) return;

  quitButton.disabled = true;
  guessButton.disabled = true;
  hintButton.disabled = true;

  try {
    const res = await fetch(quitUrl, {
      method: "POST",
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    const data = await res.json();
    gameOver = true;
    inputEl.disabled = true;

    resultSection.classList.remove("hidden");
    resultText.className = "result-text-error";
    resultText.textContent = `🚪 You quit. The answer was "${data.answer}".`;

    addToHistory({ ...data, type: "quit" });
  } catch (err) {
    console.error("Quit request failed:", err);
    resultSection.classList.remove("hidden");
    resultText.textContent =
      "Error quitting the game. Please try again or reload the page.";
    resultText.className = "result-text-error";
    // Allow another attempt
    quitButton.disabled = false;
    guessButton.disabled = false;
    hintButton.disabled = false;
  }
}

// Attach handlers
formEl.addEventListener("submit", handleGuessSubmit);
hintButton.addEventListener("click", handleHintClick);
quitButton.addEventListener("click", handleQuitClick);

// On load, check health
checkHealth();
