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

const PIECE_NAMES = Object.freeze({
  k: "king", q: "queen", r: "rook", b: "bishop", n: "knight", p: "pawn",
});

function squareName(index) {
  return `${FILES[index % 8]}${8 - Math.floor(index / 8)}`;
}

function boardIndex(visualIndex) {
  return state.orientation === "w" ? visualIndex : 63 - visualIndex;
}

function pieceColor(piece) {
  return piece === piece.toUpperCase() ? "w" : "b";
}

function moveSquares(move) {
  if (!move) return [];
  const fromFile = FILES.indexOf(move[0]);
  const fromRank = 8 - Number(move[1]);
  const toFile = FILES.indexOf(move[2]);
  const toRank = 8 - Number(move[3]);
  return [fromRank * 8 + fromFile, toRank * 8 + toFile];
}

function legalTargets(fromIndex) {
  if (!state.game || fromIndex === null) return [];
  const source = squareName(fromIndex);
  return state.game.legalMoves
    .filter((move) => move.startsWith(source))
    .map((move) => moveSquares(move)[1]);
}

function renderBoard() {
  elements.board.replaceChildren();
  const lastMoveSquares = new Set(moveSquares(state.game?.lastMove));
  const targets = new Set(legalTargets(state.selected));
  for (let visualIndex = 0; visualIndex < 64; visualIndex += 1) {
    const index = boardIndex(visualIndex);
    const row = Math.floor(visualIndex / 8);
    const column = visualIndex % 8;
    const piece = state.game?.board[index] || null;
    const selectable = Boolean(
      piece && state.game?.humanTurn && pieceColor(piece) === state.game.humanColor && !state.thinking,
    );
    const square = document.createElement("button");
    square.type = "button";
    square.className = "square";
    if ((Math.floor(index / 8) + (index % 8)) % 2 === 1) square.classList.add("dark");
    if (selectable) square.classList.add("selectable");
    if (lastMoveSquares.has(index)) square.classList.add("last-move");
    if (state.selected === index) square.classList.add("selected");
    if (targets.has(index)) {
      square.classList.add("legal-target");
      if (piece) square.classList.add("capture");
    }
    if (state.game?.checkSquare === index) square.classList.add("in-check");
    square.dataset.index = String(index);
    square.setAttribute("role", "gridcell");
    const label = piece
      ? `${squareName(index)}, ${pieceColor(piece) === "w" ? "white" : "black"} ${PIECE_NAMES[piece.toLowerCase()]}`
      : `${squareName(index)}, empty`;
    square.setAttribute("aria-label", label);

    if (piece) {
      const token = document.createElement("span");
      token.className = `piece ${pieceColor(piece) === "b" ? "black-piece" : "white-piece"}`;
      token.textContent = PIECES[piece];
      token.dataset.piece = piece;
      token.draggable = selectable;
      square.append(token);
    }
    if (column === 0) {
      const rank = document.createElement("span");
      rank.className = "coordinate rank";
      rank.textContent = squareName(index)[1];
      square.append(rank);
    }
    if (row === 7) {
      const file = document.createElement("span");
      file.className = "coordinate file";
      file.textContent = squareName(index)[0];
      square.append(file);
    }
    elements.board.append(square);
  }
}

function handleSquareClick(event) {
  const square = event.target.closest(".square");
  if (!square || !state.game?.humanTurn || state.thinking) return;
  const index = Number(square.dataset.index);
  const targetIsLegal = legalTargets(state.selected).includes(index);
  if (state.selected !== null && targetIsLegal) {
    attemptMove(state.selected, index);
    return;
  }
  const piece = state.game.board[index];
  state.selected = piece && pieceColor(piece) === state.game.humanColor ? index : null;
  renderBoard();
}

function attemptMove(fromIndex, toIndex) {
  const prefix = `${squareName(fromIndex)}${squareName(toIndex)}`;
  const candidates = state.game.legalMoves.filter((move) => move.startsWith(prefix));
  if (candidates.length === 1) submitMove(candidates[0]);
}

async function submitMove(move) {
  state.thinking = true;
  state.selected = null;
  renderBoard();
  try {
    state.game = await api(`/api/games/${state.game.id}/moves`, {
      method: "POST",
      body: JSON.stringify({ move }),
    });
    state.turnStartedAt = Date.now();
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    state.thinking = false;
    renderBoard();
  }
}

elements.board.addEventListener("click", handleSquareClick);
