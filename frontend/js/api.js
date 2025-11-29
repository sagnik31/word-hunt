export class ApiClient {
    constructor(baseUrl) {
        this.baseUrl = baseUrl;
    }

    async checkHealth() {
        const res = await fetch(`${this.baseUrl}/health`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
    }

    async makeGuess(word) {
        const res = await fetch(`${this.baseUrl}/guess`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ word }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
    }

    async getHint() {
        const res = await fetch(`${this.baseUrl}/hint`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
    }

    async quitGame() {
        const res = await fetch(`${this.baseUrl}/quit`, { method: "POST" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
    }
}
