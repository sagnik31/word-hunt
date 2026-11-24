// Tests of docs/js with a stub page, run by test_frontend.py:
//   node --test frontend.test.mjs   (JS_DIR = a copy of docs/js)
import assert from "node:assert/strict";
import test from "node:test";
import { pathToFileURL } from "node:url";
import path from "node:path";

const load = (name) => import(pathToFileURL(path.join(process.env.JS_DIR, name)));

const LAUNCH = "2026-01-01";
const KEY = "wordhunt:v1";
const store = new Map();
let failWrites = false;
let maxKeys = null; // how many keys fit, when storage is full
globalThis.localStorage = {
    getItem: (k) => store.get(k) ?? null,
    setItem: (k, v) => {
        if (failWrites) throw new Error("quota");
        if (maxKeys !== null && !store.has(k) && store.size >= maxKeys) throw new Error("quota");
        store.set(k, v);
    },
    removeItem: (k) => store.delete(k),
};

function element() {
    const classes = new Set(["hidden"]);
    return {
        value: "", textContent: "", disabled: false, style: {},
        classList: {
            add: (c) => classes.add(c), remove: (c) => classes.delete(c), contains: (c) => classes.has(c),
            toggle: (c, on) => (on ? classes.add(c) : classes.delete(c)),
        },
        addEventListener() {}, appendChild() {}, append() {}, prepend() {}, focus() {},
    };
}
const elements = new Map();
globalThis.document = {
    hidden: false,
    addEventListener() {},
    createElement: element,
    getElementById: (id) => elements.get(id) ?? elements.set(id, element()).get(id),
};
globalThis.window = { addEventListener() {} };
globalThis.location = { hash: "", reload() {} };
globalThis.setInterval = () => 0;
console.error = console.warn = () => {};

const { Progress, deviceId } = await load("storage.js");
const { GameUI } = await load("ui.js");

function deferred() {
    const d = {};
    d.promise = new Promise((resolve, reject) => Object.assign(d, { resolve, reject }));
    return d;
}

const today = (puzzle, seconds = 3600) => ({
    puzzle, latest: puzzle, launch_date: LAUNCH, seconds_until_next: seconds,
    date: new Date(Date.parse(`${LAUNCH}T00:00:00Z`) + (puzzle - 1) * 86400000).toISOString().slice(0, 10),
});
const miss = (guess, rank) => ({
    guess, valid: true, is_correct: false, rank, total: 100, similarity: 0.1, percentile: 50, hotness: "Cold",
});
const win = (guess) => ({ ...miss(guess, 1), is_correct: true, score: 90 });

// A started puzzle #2 (today), with every request under the test's control.
async function start({ todayReply = today(2), hash = "" } = {}) {
    store.clear();
    elements.clear();
    failWrites = false;
    location.hash = hash;
    const api = {
        calls: [],
        getToday: async () => {
            api.calls.push("today");
            return todayReply;
        },
        getPuzzle: async () => ({ clue_total: 3 }),
        getResults: async () => {
            throw new Error("off");
        },
    };
    for (const name of ["makeGuess", "getClue", "getHint", "quitGame"]) {
        api[name] = (...args) => {
            api.calls.push(name);
            api.args = args;
            api.reply = deferred();
            return api.reply.promise;
        };
    }
    const ui = new GameUI(api);
    await ui.init();
    if (ui.puzzle !== null) ui.handlePlayClick();
    return { ui, api };
}

function guess(ui, word) {
    ui.inputEl.value = word;
    return ui.handleGuessSubmit({ preventDefault() {} });
}

test("tabs saving different puzzles keep each other's games", () => {
    store.clear();
    const a = new Progress();
    const b = new Progress();
    a.useLaunch(LAUNCH);
    b.useLaunch(LAUNCH);
    a.save(1, a.game(1));
    b.save(2, b.game(2));
    assert.deepEqual(Object.keys(new Progress().data.games), ["1", "2"]);
});

test("a finish saved in one tab isn't replaced by another tab's game", () => {
    store.clear();
    const a = new Progress();
    const b = new Progress();
    const stale = b.game(1);
    a.save(1, { ...a.game(1), status: "won", score: 80 });
    assert.equal(b.save(1, stale), false);
    assert.equal(new Progress().game(1).status, "won");
});

test("a tab from before a relaunch doesn't write over the new saves", () => {
    store.clear();
    const old = new Progress();
    old.useLaunch(LAUNCH);
    old.save(1, old.game(1));
    new Progress().useLaunch("2026-02-01");
    assert.equal(old.save(1, old.game(1)), false);
    assert.deepEqual(new Progress().data, { launch: "2026-02-01", games: {} });
});

test("a relaunch keeps the old games even when there's no room for a copy", () => {
    store.clear();
    const old = new Progress();
    old.useLaunch(LAUNCH);
    old.save(1, old.game(1));
    const saved = store.get(KEY);
    maxKeys = 1;
    new Progress().useLaunch("2026-02-01");
    maxKeys = null;
    assert.equal(store.get(`wordhunt:old:${LAUNCH}`), saved);
});

test("progress survives in memory when storage can't be written", () => {
    store.clear();
    const p = new Progress();
    p.useLaunch(LAUNCH);
    failWrites = true;
    p.save(1, { ...p.game(1), startedAt: 5 });
    p.save(2, { ...p.game(2), startedAt: 6 });
    failWrites = false;
    assert.equal(p.game(1).startedAt, 5);
    p.save(2, p.game(2));
    assert.equal(new Progress().game(1).startedAt, 5);
});

test("damaged games load, and good ones are untouched", () => {
    const good = { ...miss("cat", 5), type: "guess" };
    store.set(KEY, JSON.stringify({
        launch: LAUNCH,
        games: {
            1: null, 2: { entries: null, clues: {}, status: "x", startedAt: "soon" }, 3: [],
            4: { entries: [null, 7, { type: "guess", valid: true }, good], similarCount: 2 },
        },
    }));
    const p = new Progress();
    for (const n of [1, 2, 3]) {
        assert.deepEqual(p.game(n).entries, []);
        assert.equal(p.game(n).status, "playing");
        assert.equal(p.game(n).startedAt, null);
    }
    assert.deepEqual(p.game(4).entries, [good]);
    assert.equal(p.game(4).hintCount, 2);
});

test("an invalid stored device ID is replaced", () => {
    store.clear();
    store.set("wordhunt:device", "not valid!");
    const id = deviceId();
    assert.match(id, /^[0-9a-f-]{36}$/);
    assert.equal(deviceId(), id);
});

test("a solve is saved after moving to another puzzle, and the draft there stays", async () => {
    const { ui, api } = await start();
    const done = guess(ui, "apple");
    ui.openPuzzle(1);
    ui.handlePlayClick();
    ui.inputEl.value = "draft";
    api.reply.resolve(win("apple"));
    await done;
    const saved = new Progress().game(2);
    assert.equal(saved.status, "won");
    assert.equal(saved.onTheDay, true);
    assert.equal(ui.game.status, "playing");
    assert.equal(ui.inputEl.value, "draft");
    assert.equal(ui.guessButton.disabled, false);
});

test("a reply reaches the game after leaving the puzzle and coming back", async () => {
    const { ui, api } = await start();
    const done = guess(ui, "pear");
    ui.openPuzzle(1);
    ui.openPuzzle(2);
    assert.equal(ui.guessButton.disabled, true);
    api.reply.resolve(miss("pear", 9));
    await done;
    assert.equal(ui.game.entries.length, 1);
    assert.equal(ui.game.bestRank, 9);
    assert.equal(ui.guessButton.disabled, false);
});

test("an error on a puzzle you left isn't shown on the one you're on", async () => {
    const { ui, api } = await start();
    const done = guess(ui, "pear");
    ui.openPuzzle(1);
    ui.resultText.textContent = "";
    api.reply.reject(new Error("down"));
    await done;
    assert.equal(ui.resultText.textContent, "");
});

test("a quit is saved after moving to another puzzle", async () => {
    const { ui, api } = await start();
    const done = ui.handleQuitClick();
    ui.openPuzzle(1);
    api.reply.resolve({ answer: "apple", score: 3 });
    await done;
    assert.equal(new Progress().game(2).status, "quit");
    assert.equal(ui.game.status, "playing");
});

async function unlockHelp(ui, api) {
    for (let i = 0; i < 12; i += 1) {
        const done = guess(ui, `word${i}`);
        api.reply.resolve(miss(`word${i}`, 10 + i));
        await done;
    }
}

test("a clue and a guess can't overlap, in either order", async () => {
    const { ui, api } = await start();
    await unlockHelp(ui, api);
    const clue = ui.handleClueClick();
    const sent = api.calls.length;
    await guess(ui, "apple");
    await ui.handleQuitClick();
    assert.equal(api.calls.length, sent);
    api.reply.resolve({ clue: "A clue.", number: 1, total: 3 });
    await clue;
    const done = guess(ui, "apple");
    assert.equal(api.args[2].clue_count, 1);
    const during = api.calls.length;
    await ui.handleClueClick();
    assert.equal(api.calls.length, during);
    api.reply.resolve(win("apple"));
    await done;
    assert.equal(ui.game.status, "won");
});

test("a hint the server can't give isn't offered again at the same rank", async () => {
    const { ui, api } = await start();
    await unlockHelp(ui, api);
    ui.game.clueTotal = 0;
    ui.renderHelp();
    assert.equal(ui.hintButton.disabled, false);
    const done = ui.handleHintClick();
    api.reply.reject(Object.assign(new Error(), { status: 409 }));
    await done;
    assert.equal(ui.hintButton.disabled, true);
});

test("a clock moved back never sends a negative time", async () => {
    const { ui } = await start();
    ui.game.startedAt = Date.now() + 60_000;
    assert.equal(ui.stats().elapsed_seconds, 0);
});

test("only the server moves the page to the next day", async () => {
    const { ui, api } = await start();
    ui.tick();
    assert.equal(api.calls.filter((c) => c === "today").length, 1);
    ui.nextAt = Date.now() - 1;
    await ui.refreshToday(); // the server says it's still day 2
    assert.equal(ui.today, 2);
    assert.ok(ui.nextAt > Date.now());

    api.getToday = async () => today(3);
    await ui.refreshToday();
    assert.equal(ui.today, 3);
    assert.equal(ui.puzzle, 2);
    assert.match(ui.statusEl.textContent, /new puzzle is out/);
});

test("a solve sent before midnight counts for its day", async () => {
    const { ui, api } = await start();
    const done = guess(ui, "apple");
    api.getToday = async () => today(3);
    await ui.refreshToday();
    api.reply.resolve(win("apple"));
    await done;
    assert.equal(ui.game.onTheDay, true);
});

test("past puzzles open when the schedule has run out", async () => {
    const reply = { ...today(9), puzzle: null, latest: 3 };
    const { ui } = await start({ todayReply: reply });
    assert.equal(ui.puzzle, null);
    assert.equal(ui.archiveSection.classList.contains("hidden"), false);
    ui.openPuzzle(3);
    assert.match(ui.playButton.textContent, /#3/);
});

test("the page still works with a backend that sends no `latest`", async () => {
    const { latest, ...reply } = today(2);
    const { ui } = await start({ todayReply: reply });
    assert.equal(latest, 2);
    assert.equal(ui.latest, 2);
    assert.equal(ui.puzzle, 2);
});

test("a tab shows what another tab saved, keeping the draft", async () => {
    const { ui } = await start();
    ui.inputEl.value = "draft";
    const other = new Progress();
    const game = other.game(2);
    game.entries.push({ ...miss("pear", 9), type: "guess" });
    other.save(2, game);
    ui.syncTabs();
    assert.equal(ui.game.entries.length, 1);
    assert.equal(ui.inputEl.value, "draft");
});
