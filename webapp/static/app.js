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

function render() {
  document.body.dataset.theme = THEMES[state.themeIndex];
  elements.thinkingOverlay.classList.toggle("visible", state.thinking);
  elements.thinkingOverlay.setAttribute("aria-hidden", String(!state.thinking));
  elements.resignButton.disabled = !state.game || state.game.status !== "active" || state.thinking;
  renderBoard();
  renderStatus();
  renderMoves();
  renderPlayers();
  renderClocks();
}

function renderPlayers() {
  if (!state.game) {
    elements.humanCaptured.textContent = "";
    elements.botCaptured.textContent = "";
    return;
  }
  const humanIsWhite = state.game.humanColor === "w";
  elements.humanColorLabel.textContent = `Playing ${humanIsWhite ? "White" : "Black"}`;
  elements.botLevel.textContent = `${state.game.difficulty[0].toUpperCase() + state.game.difficulty.slice(1)} strength`;
  elements.humanCaptured.textContent = state.game.captured[humanIsWhite ? "white" : "black"].join("");
  elements.botCaptured.textContent = state.game.captured[humanIsWhite ? "black" : "white"].join("");
}

function formatElapsed(milliseconds) {
  const seconds = Math.max(0, Math.floor(milliseconds / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function renderClocks() {
  const elapsed = formatElapsed(Date.now() - state.turnStartedAt);
  const humanActive = Boolean(state.game?.humanTurn && state.game.status === "active" && !state.thinking);
  const botActive = Boolean(state.game && !state.game.humanTurn && state.game.status === "active") || state.thinking;
  elements.humanClock.textContent = humanActive ? elapsed : "—";
  elements.botClock.textContent = botActive ? elapsed : "—";
  elements.humanClock.classList.toggle("active", humanActive);
  elements.botClock.classList.toggle("active", botActive);
}

function renderMoves() {
  elements.moveList.replaceChildren();
  if (!state.game?.moves.length) {
    elements.moveList.className = "move-list empty";
    const empty = document.createElement("div");
    empty.className = "empty-moves";
    empty.innerHTML = '<span aria-hidden="true">♟</span><p>Your game notation will appear here.</p>';
    elements.moveList.append(empty);
    return;
  }
  elements.moveList.className = "move-list";
  for (let i = 0; i < state.game.moves.length; i += 2) {
    const row = document.createElement("div");
    row.className = "move-row";
    const number = document.createElement("span");
    number.className = "move-number";
    number.textContent = `${Math.floor(i / 2) + 1}.`;
    row.append(number);
    for (const move of state.game.moves.slice(i, i + 2)) {
      const notation = document.createElement("span");
      notation.className = "move-notation";
      notation.textContent = move.san;
      row.append(notation);
    }
    elements.moveList.append(row);
  }
  elements.moveList.scrollTop = elements.moveList.scrollHeight;
}

function renderStatus() {
  if (!state.game) {
    elements.gameStatus.textContent = "Choose your side to begin";
    elements.gameSubstatus.textContent = "Mero is ready when you are.";
    elements.gameResult.textContent = "*";
    elements.statusDot.className = "status-dot";
    return;
  }
  elements.gameResult.textContent = state.game.result;
  elements.statusDot.className = "status-dot active";
  if (state.game.status !== "active") {
    const won = (state.game.result === "1-0") === (state.game.humanColor === "w");
    elements.gameStatus.textContent = state.game.result === "1/2-1/2" ? "Game drawn" : won ? "You won" : "Mero won";
    elements.gameSubstatus.textContent = state.game.status[0].toUpperCase() + state.game.status.slice(1);
    elements.statusDot.className = "status-dot ended";
  } else if (state.thinking || !state.game.humanTurn) {
    elements.gameStatus.textContent = "Mero is thinking";
    elements.gameSubstatus.textContent = "Searching for the best reply…";
  } else {
    elements.gameStatus.textContent = state.game.inCheck ? "Your king is in check" : "Your move";
    elements.gameSubstatus.textContent = state.game.inCheck ? "Find a legal response." : "Select a piece to continue.";
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
  if (candidates.length > 1) choosePromotion(candidates);
}

function choosePromotion(candidates) {
  elements.promotionOptions.replaceChildren();
  for (const move of candidates) {
    const promoted = move.at(-1);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "promotion-piece";
    const piece = state.game.humanColor === "w" ? promoted.toUpperCase() : promoted;
    button.textContent = PIECES[piece];
    button.setAttribute("aria-label", `Promote to ${PIECE_NAMES[promoted]}`);
    button.addEventListener("click", () => {
      elements.promotionDialog.close();
      submitMove(move);
    });
    elements.promotionOptions.append(button);
  }
  elements.promotionDialog.showModal();
}

async function submitMove(move) {
  state.thinking = true;
  state.selected = null;
  render();
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
    render();
  }
}

async function startGame(color, difficulty) {
  state.thinking = true;
  render();
  try {
    const game = await api("/api/games", {
      method: "POST",
      body: JSON.stringify({ color, difficulty }),
    });
    state.game = game;
    state.orientation = game.humanColor;
    state.turnStartedAt = Date.now();
    localStorage.setItem("mero-game-id", game.id);
    elements.newGameDialog.close();
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    state.thinking = false;
    render();
  }
}

async function restoreGame() {
  const gameId = localStorage.getItem("mero-game-id");
  if (!gameId) return false;
  try {
    state.game = await api(`/api/games/${gameId}`);
    state.orientation = state.game.humanColor;
    state.turnStartedAt = Date.now();
    render();
    return true;
  } catch {
    localStorage.removeItem("mero-game-id");
    return false;
  }
}

async function checkEngineHealth() {
  try {
    const health = await api("/api/health");
    elements.engineLabel.textContent = health.engine || "Engine online";
    elements.engineLabel.closest(".engine-pill").classList.remove("offline");
  } catch {
    elements.engineLabel.textContent = "Engine offline";
    elements.engineLabel.closest(".engine-pill").classList.add("offline");
  }
}

elements.newGameButton.addEventListener("click", () => elements.newGameDialog.showModal());
elements.newGameForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const form = new FormData(elements.newGameForm);
  startGame(form.get("color"), form.get("difficulty"));
});
elements.flipButton.addEventListener("click", () => {
  state.orientation = state.orientation === "w" ? "b" : "w";
  state.selected = null;
  renderBoard();
});
elements.themeButton.addEventListener("click", () => {
  state.themeIndex = (state.themeIndex + 1) % THEMES.length;
  localStorage.setItem("mero-theme", String(state.themeIndex));
  document.body.dataset.theme = THEMES[state.themeIndex];
  showToast(`${THEMES[state.themeIndex][0].toUpperCase() + THEMES[state.themeIndex].slice(1)} board selected`);
});
elements.resignButton.addEventListener("click", async () => {
  if (!state.game || state.game.status !== "active") return;
  if (!window.confirm("Resign this game against Mero?")) return;
  try {
    state.game = await api(`/api/games/${state.game.id}/resign`, {
      method: "POST",
      body: "{}",
    });
    localStorage.removeItem("mero-game-id");
    render();
  } catch (error) {
    showToast(error.message, "error");
  }
});

elements.board.addEventListener("click", handleSquareClick);
elements.board.addEventListener("dragstart", (event) => {
  const square = event.target.closest(".square");
  if (!square || !event.target.matches(".piece")) return;
  state.draggedFrom = Number(square.dataset.index);
  state.selected = state.draggedFrom;
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", squareName(state.draggedFrom));
  window.requestAnimationFrame(renderBoard);
});
elements.board.addEventListener("dragover", (event) => {
  const square = event.target.closest(".square");
  if (square && legalTargets(state.draggedFrom).includes(Number(square.dataset.index))) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }
});
elements.board.addEventListener("drop", (event) => {
  event.preventDefault();
  const square = event.target.closest(".square");
  if (square && state.draggedFrom !== null) attemptMove(state.draggedFrom, Number(square.dataset.index));
  state.draggedFrom = null;
});
elements.board.addEventListener("dragend", () => {
  state.draggedFrom = null;
});

render();
checkEngineHealth();
restoreGame().then((restored) => {
  if (!restored) elements.newGameDialog.showModal();
});
window.setInterval(renderClocks, 1000);
