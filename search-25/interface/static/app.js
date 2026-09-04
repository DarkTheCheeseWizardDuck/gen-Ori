import { state } from './js/state.js';
import * as Editor from './js/editor.js';
import { History } from './js/editor.js';
import * as TreeActions from './js/treeActions.js';
import * as Results from './js/results.js';
import * as Detail from './js/detail.js';
import { setStatus } from './js/utils.js';

// ---------------------------------------------------------------------------
// DOM refs
// ---------------------------------------------------------------------------
const promptInput = document.getElementById('promptInput');
const actionBtn = document.getElementById('actionBtn');
const newRequestBtn = document.getElementById('newRequestBtn');
const requestPill = document.getElementById('requestPill');
const uploadInitialBtn = document.getElementById('uploadInitialBtn');
const uploadInitialInput = document.getElementById('uploadInitialInput');

const editBox = document.getElementById('editBox');
const settingsBox = document.getElementById('settingsBox');
const treeBox = document.getElementById('treeBox');
const projectTitle = document.getElementById('projectTitle');

const undoBtn = document.getElementById('undoBtn');
const redoBtn = document.getElementById('redoBtn');
const deleteNodeBtn = document.getElementById('deleteNodeBtn');
const downloadTreeBtn = document.getElementById('downloadTreeBtn');
const uploadTreeBtn = document.getElementById('uploadTreeBtn');
const uploadTreeInput = document.getElementById('uploadTreeInput');

const symDiag = document.getElementById('symDiag');
const symBook = document.getElementById('symBook');
const symNone = document.getElementById('symNone');
const searchSize = document.getElementById('searchSize');

const detailCloseBtn = document.getElementById('detailCloseBtn');
const detailPrevBtn = document.getElementById('detailPrevBtn');
const detailNextBtn = document.getElementById('detailNextBtn');

// ---------------------------------------------------------------------------
// Phase state machine: 'idle' -> 'tree' -> 'results'
// ---------------------------------------------------------------------------
let phase = 'idle';
let actionLocked = false; // debounce guard for the relabeling Generate/Search button

function setActionLocked(locked) {
  actionLocked = locked;
  actionBtn.disabled = locked;
}

// ---------------------------------------------------------------------------
// Loading a /api/generate response into the editor, preserving which edges
// are TAN-original (get a hover name) vs user-added later (don't).
// ---------------------------------------------------------------------------
function fitTreeToView() {
  const nodeList = Object.values(state.nodes);
  if (nodeList.length === 0) return;

  const xs = nodeList.map((n) => n.x);
  const ys = nodeList.map((n) => n.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  // Only clamp for the true single-node case (zero-width bbox) -- gen-Ori's
  // tree coordinates are small fractional units, not pixels, so a real
  // multi-node tree can legitimately be < 1 unit wide/tall and must not be
  // clamped up to 1, or the fit calculation below silently thinks the tree
  // is much bigger than it is and under-zooms drastically.
  const contentW = Math.max(maxX - minX, 1e-6);
  const contentH = Math.max(maxY - minY, 1e-6);
  const contentCx = (minX + maxX) / 2;
  const contentCy = (minY + maxY) / 2;

  const svgEl = document.getElementById('editorSvg');
  const boxW = svgEl.clientWidth || 600;
  const boxH = svgEl.clientHeight || 600;
  const padding = 60; // px of breathing room around the tree
  const DEFAULT_SHRINK = 0.5; // back off a bit from an edge-to-edge fit by default

  let fitZoom = Math.min(
    (boxW - padding * 2) / contentW,
    (boxH - padding * 2) / contentH
  ) * DEFAULT_SHRINK;

  // Only a true single-node tree (contentW/H hit the 1e-6 floor above)
  // should fall back to a fixed zoom -- anything with real spatial extent
  // must be free to zoom in as far as it needs to, since these coordinates
  // run roughly 0-1, not 0-hundreds like on-screen pixels.
  if (nodeList.length <= 1 || !isFinite(fitZoom)) fitZoom = 1;

  state.zoom = Math.max(fitZoom, 0.01);
  state.panOffset.x = boxW / 2 - contentCx * state.zoom;
  state.panOffset.y = boxH / 2 - contentCy * state.zoom;

  // MIN_ZOOM/MAX_ZOOM in editor.js were calibrated for pixel-scale content;
  // gen-Ori's coordinates are tiny fractional units, so the meaningful zoom
  // range has to scale relative to this tree's own fitted baseline instead
  // of using fixed absolute numbers (which would clamp almost immediately).
  Editor.setZoomBounds(state.zoom * 0.15, state.zoom * 15);
}

function loadGeneratedTree(tree) {
  History.saveState();

  const newNodes = {};
  let maxId = 0;
  for (const n of tree.nodes) {
    newNodes[n.id] = { id: n.id, x: n.x, y: n.y };
    if (n.id > maxId) maxId = n.id;
  }

  const newEdges = tree.edges.map((e) => ({
    u: e.u,
    v: e.v,
    length: e.length || 1,
    original: true,
    name: e.name || null,
  }));

  state.nodes = newNodes;
  state.edges = newEdges;
  state.nextNodeId = maxId + 1;
  state.selectedNode = null;
  state.draggingNode = null;
  state.isPanning = false;
  state.backgroundGesture = null;
  fitTreeToView();

  Editor.renderEditor();
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------
async function callGenerate(prompt) {
  const res = await fetch('/api/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
  });
  if (!res.ok) throw new Error(`generate failed: ${res.status}`);
  return res.json();
}

async function callSearch(tree, dbConfigs, n) {
  const res = await fetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tree, db_configs: dbConfigs, n }),
  });
  if (!res.ok) throw new Error(`search failed: ${res.status}`);
  return res.json();
}

function collectDbConfigs() {
  const configs = [];
  if (symDiag.checked) configs.push({ N: 4, symmetry: 'diag' });
  if (symBook.checked) configs.push({ N: 4, symmetry: 'book' });
  if (symNone.checked) configs.push({ N: 3, symmetry: 'none' });
  return configs;
}

// ---------------------------------------------------------------------------
// Phase transitions
// ---------------------------------------------------------------------------
function showTreeReadyUI() {
  editBox.classList.add('visible');
  settingsBox.classList.add('visible');
  treeBox.classList.add('visible');
  projectTitle.classList.add('hidden-title');
  uploadInitialBtn.classList.add('hidden');

  actionBtn.textContent = 'Search';
  phase = 'tree';
}

async function handleGenerate() {
  const prompt = promptInput.value.trim();
  if (!prompt) return;

  setActionLocked(true);
  setStatus('Generating tree...');

  try {
    const data = await callGenerate(prompt);

    // Lock the request into the bar as a physical, non-editable pill.
    requestPill.textContent = prompt;
    requestPill.classList.remove('hidden');
    promptInput.value = '';
    promptInput.classList.add('hidden');

    if (data.tree) {
      loadGeneratedTree(data.tree);
    }

    showTreeReadyUI();
    setActionLocked(false);
    setStatus('Tree ready. Edit it, or click Search.');
  } catch (err) {
    setActionLocked(false);
    setStatus('Generate failed: ' + err.message, true);
  }
}

function handleInitialUpload() {
  const file = uploadInitialInput.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = () => {
    try {
      Editor.loadTreeState(reader.result);
      fitTreeToView();
      Editor.renderEditor();
    } catch (err) {
      setStatus('Could not load that file: ' + err.message, true);
      return;
    }

    // Case 2: uploaded a tree directly, skipping Generate entirely --
    // the prompt bar is no longer relevant, so lock it out rather than
    // leave it sitting there implying it still does something.
    promptInput.disabled = true;
    promptInput.placeholder = 'Tree uploaded -- click Search, or start a new request.';

    showTreeReadyUI();
    setStatus('Tree uploaded. Edit it, or click Search.');
  };
  reader.readAsText(file);
  uploadInitialInput.value = '';
}

async function handleSearch() {
  setActionLocked(true);
  setStatus('Searching...');
  state.isQueryLoading = true;
  Results.renderResults();

  try {
    const tree = Editor.serializeTree();
    const dbConfigs = collectDbConfigs();
    const n = parseInt(searchSize.value, 10) || 5;

    const data = await callSearch(tree, dbConfigs, n);
    state.isQueryLoading = false;
    state.queryResult = data;
    Results.renderResults();

    phase = 'results';
    setActionLocked(false);
    setStatus(`Found ${data.results ? data.results.length : 0} result(s).`);
  } catch (err) {
    state.isQueryLoading = false;
    Results.renderResults();
    setActionLocked(false);
    setStatus('Search failed: ' + err.message, true);
  }
}

function handleActionClick() {
  if (actionLocked) return;
  if (phase === 'idle') {
    handleGenerate();
  } else {
    handleSearch();
  }
}

function handleNewRequest() {
  editBox.classList.remove('visible');
  settingsBox.classList.remove('visible');
  treeBox.classList.remove('visible');
  projectTitle.classList.remove('hidden-title');

  // Let the pop-out animation play before actually clearing content underneath.
  setTimeout(() => {
    Editor.resetTree();
    requestPill.textContent = '';
    requestPill.classList.add('hidden');
    promptInput.classList.remove('hidden');
    promptInput.disabled = false;
    promptInput.placeholder = 'Describe what you want to fold...';
    promptInput.value = '';
    uploadInitialBtn.classList.remove('hidden');
    actionBtn.textContent = 'Generate';
    state.queryResult = null;
    Results.renderResults();
    phase = 'idle';
    setStatus('Ready for a new request.');
  }, 250);
}

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------
actionBtn.addEventListener('click', handleActionClick);
newRequestBtn.addEventListener('click', handleNewRequest);
uploadInitialBtn.addEventListener('click', () => uploadInitialInput.click());
uploadInitialInput.addEventListener('change', handleInitialUpload);

promptInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleActionClick();
  }
});

undoBtn.addEventListener('click', () => { History.undo(); fitTreeToView(); Editor.renderEditor(); });
redoBtn.addEventListener('click', () => { History.redo(); fitTreeToView(); Editor.renderEditor(); });
deleteNodeBtn.addEventListener('click', () => TreeActions.deleteSelectedNode());
downloadTreeBtn.addEventListener('click', () => Editor.downloadTree());
uploadTreeBtn.addEventListener('click', () => uploadTreeInput.click());
uploadTreeInput.addEventListener('change', () => {
  const file = uploadTreeInput.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    Editor.loadTreeState(reader.result);
    fitTreeToView();
    Editor.renderEditor();
  };
  reader.readAsText(file);
  uploadTreeInput.value = '';
});

detailCloseBtn.addEventListener('click', () => Detail.closeDetailModal());
detailPrevBtn.addEventListener('click', () => Detail.navigateDetail(-1));
detailNextBtn.addEventListener('click', () => Detail.navigateDetail(1));

document.getElementById('editorSvg').addEventListener('mousedown', Editor.onEditorMouseDown);
window.addEventListener('mousemove', Editor.onEditorMouseMove);
window.addEventListener('mouseup', Editor.onEditorMouseUp);
document.getElementById('editorSvg').addEventListener('wheel', Editor.onEditorWheel, { passive: false });

const resultsThumbInput = document.getElementById('resultsThumbMode');
const thumbModeBtns = document.querySelectorAll('.thumb-mode-btn');
thumbModeBtns.forEach((btn) => {
  btn.addEventListener('click', () => {
    thumbModeBtns.forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    resultsThumbInput.value = btn.dataset.mode;
    if (state.queryResult) Results.renderResults();
  });
});

// ---------------------------------------------------------------------------
// Initial render
// ---------------------------------------------------------------------------
Editor.renderEditor();
Results.renderResults();
