// app.js

// TODO: replace this with your actual Render API base URL
// e.g. "https://word-hunt-backend.onrender.com"
const API_BASE_URL = "https://word-hunt-cevi.onrender.com";

const healthUrl = `${API_BASE_URL}/health`;
const guessUrl = `${API_BASE_URL}/guess`;

const statusEl = document.getElementById("status");
const formEl = document.getElementById("guess-form");
const inputEl = document.getElementById("guess-input");
const resultSection = document.getElementById("result");
const resultText = document.getElementById("result-text");
const historySection = document.getElementById("history");
const historyList = document.getElementById("history-list");

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
  resultText.className = ""; // reset classes

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

  const word = inputEl.value.trim();
  if (!word) return;

  const payload = { word };

  formEl.querySelector("button").disabled = true;

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
  } catch (err) {
    console.error("Guess request failed:", err);
    resultSection.classList.remove("hidden");
    resultText.textContent =
      "Error communicating with the server. Please try again.";
    resultText.className = "result-text-error";
  } finally {
    formEl.querySelector("button").disabled = false;
    inputEl.value = "";
    inputEl.focus();
  }
}

// Attach handlers
formEl.addEventListener("submit", handleGuessSubmit);

// On load, check health
checkHealth();
