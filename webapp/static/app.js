"use strict";

const PIECES = Object.freeze({
  K: "♔", Q: "♕", R: "♖", B: "♗", N: "♘", P: "♙",
  k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟",
});

const FILES = "abcdefgh";
const THEMES = ["wood", "green", "slate"];

const elements = {
  board: document.querySelector("#chessboard"),
  newGameButton: document.querySelector("#new-game-button"),
  newGameDialog: document.querySelector("#new-game-dialog"),
  newGameForm: document.querySelector("#new-game-form"),
  resignButton: document.querySelector("#resign-button"),
  flipButton: document.querySelector("#flip-button"),
  themeButton: document.querySelector("#theme-button"),
  promotionDialog: document.querySelector("#promotion-dialog"),
  promotionOptions: document.querySelector("#promotion-options"),
  moveList: document.querySelector("#move-list"),
  gameStatus: document.querySelector("#game-status"),
  gameSubstatus: document.querySelector("#game-substatus"),
  gameResult: document.querySelector("#game-result"),
  statusDot: document.querySelector("#status-dot"),
  thinkingOverlay: document.querySelector("#thinking-overlay"),
  humanColorLabel: document.querySelector("#human-color-label"),
  botLevel: document.querySelector("#bot-level"),
  humanCaptured: document.querySelector("#human-captured"),
  botCaptured: document.querySelector("#bot-captured"),
  humanClock: document.querySelector("#human-clock"),
  botClock: document.querySelector("#bot-clock"),
  engineLabel: document.querySelector("#engine-label"),
  toast: document.querySelector("#toast"),
};

const state = {
  game: null,
  selected: null,
  orientation: "w",
  thinking: false,
  draggedFrom: null,
  turnStartedAt: Date.now(),
  themeIndex: Number(localStorage.getItem("mero-theme") || 0) % THEMES.length,
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error("The server returned an unreadable response.");
  }
  if (!response.ok) {
    throw new Error(payload.error || "The request failed.");
  }
  return payload;
}

let toastTimer;
function showToast(message, type = "info") {
  window.clearTimeout(toastTimer);
  elements.toast.textContent = message;
  elements.toast.className = `toast visible ${type}`;
  toastTimer = window.setTimeout(() => {
    elements.toast.className = "toast";
  }, 3200);
}
