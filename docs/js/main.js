import { CONFIG } from "./config.js";
import { ApiClient } from "./api.js";
import { GameUI } from "./ui.js";

// Initialize
const apiClient = new ApiClient(CONFIG.API_BASE_URL);
const gameUI = new GameUI(apiClient);
gameUI.init();
