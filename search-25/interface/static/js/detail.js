import { state } from './state.js';
import { makeSvg, renderCpSvg, renderPackingSvg, renderFoldSvg, renderGraphSvg, computeRadialTreeLayout, parseCp4D, boundsFromSegments, fitScale, transformX, transformY } from './renderers.js';
import { renderReferenceWorkspace } from './refs.js';
import { persistDetailView, getMatchQuality, symmetry_abbr } from './utils.js';
import { registerDetailRenderer } from './results.js';
import { Locales } from './locales.js';

const detailModal = document.getElementById("detailModal");
const modalGrid = document.getElementById("modalGrid");
const modalTitle = document.getElementById("modalTitle");
const modalMeta = document.getElementById("modalMeta");
const detailPrevBtn = document.getElementById("detailPrevBtn");
const detailNextBtn = document.getElementById("detailNextBtn");

// --- Fold guide ("Show fold guide") state -----------------------------
// Kept as plain module state rather than in state.js since it's transient,
// modal-scoped UI state, not part of the app's shared data model.
let selectedRefsVertexIndex = null;
let refsResultKey = null; // identifies which result the above index belongs to
const refsCache = {};        // "N_sym_tilingId" -> { refs, cp }
const refsFetchInFlight = {}; // "N_sym_tilingId" -> Promise, avoids duplicate fetches

function resultKey(result) {
  return `${result.N}_${result.symmetry}_${result.tiling_id}`;
}

export function closeDetailModal() {
  detailModal.classList.add("hidden");
  detailModal.setAttribute("aria-hidden", "true");
  state.currentDetailResult = null;
  state.currentDetailIndex = null;
}

export function updateDetailView(side, value) {
  if (state.detailViewModes[side] === value) return;
  state.detailViewModes[side] = value;
  persistDetailView(side, value);
  if (state.currentDetailResult && state.currentDetailIndex !== null) {
    renderDetail(state.currentDetailResult, state.currentDetailIndex);
  }
}

export function navigateDetail(step) {
  if (!state.queryResult?.results?.length || state.currentDetailIndex === null) return;
  const nextIndex = state.currentDetailIndex + step;
  if (nextIndex < 0 || nextIndex >= state.queryResult.results.length) return;
  renderDetail(state.queryResult.results[nextIndex], nextIndex);
}

export function updateDetailNavButtons() {
  if (!detailPrevBtn || !detailNextBtn) return;
  const total = state.queryResult?.results?.length || 0;
  detailPrevBtn.disabled = state.currentDetailIndex === null || state.currentDetailIndex <= 0;
  detailNextBtn.disabled = state.currentDetailIndex === null || state.currentDetailIndex >= total - 1;
}

function buildDetailPane({ side, activeValue, options, renderActive, extraToggleElement, customBody }) {
  const panel = document.createElement("section");
  panel.className = "detail-panel";
  const toggleGroup = document.createElement("div");
  toggleGroup.className = "detail-toggle-group";
  options.forEach((option) => {
    const label = document.createElement("label");
    label.className = "detail-toggle-option";
    const input = document.createElement("input");
    input.type = "radio";
    input.name = `detail-${side}-mode`;
    input.value = option.value;
    input.checked = option.value === activeValue;
    input.addEventListener("change", () => { if (input.checked) updateDetailView(side, option.value); });
    const span = document.createElement("span");
    span.textContent = option.label;
    label.appendChild(input);
    label.appendChild(span);
    toggleGroup.appendChild(label);
  });
  if (extraToggleElement) {
    toggleGroup.appendChild(extraToggleElement);
  }

  const body = document.createElement("div");
  body.className = "detail-panel-body";

  if (customBody) {
    body.appendChild(customBody);
  } else {
    // UPDATE: Change viewBox to a square 400x400
    const svg = makeSvg("svg", { viewBox: "0 0 400 400", class: "detail-svg" });
    renderActive(svg, activeValue);
    body.appendChild(svg);
  }

  panel.appendChild(body);
  panel.appendChild(toggleGroup);
  return panel;
}

function downloadResultTree(result) {
  if (!result || !result.tree) return;

  // result.tree comes from the server with no x/y (only topology) -- reuse
  // the same radial layout the Tree panel renders with, so the download
  // matches what's on screen and every node gets real coordinates.
  computeRadialTreeLayout(result.tree);

  const nodes = result.tree.nodes.map((n) => ({ id: n.id, x: n.pos[0], y: n.pos[1] }));
  const edges = result.tree.edges.map((e) => ({ u: e.u, v: e.v, length: e.length }));
  const treeData = { nodes, edges };

  const symAbbr = symmetry_abbr[result.symmetry] || result.symmetry || '';
  const filename = `gen-ori_tiling_${result.N}${symAbbr}.${result.tiling_id}.json`;

  const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(treeData, null, 2));
  const a = document.createElement('a');
  a.setAttribute('href', dataStr);
  a.setAttribute('download', filename);
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function computeCartesianVertices(cp) {
  // Same formula parseCp4D uses internally for edge endpoints, applied here
  // directly to every vertex so we can place a clickable circle at each one.
  const SQRT2_2 = Math.SQRT2 / 2;
  return (cp.vertices || []).map((v) => {
    const x = v[0] / v[1], y = v[2] / v[3], z = v[4] / v[5], w = v[6] / v[7];
    return [x + SQRT2_2 * (y - w), z + SQRT2_2 * (y + w)];
  });
}

function renderClickableCp(svg, result) {
  const key = resultKey(result);
  const cached = refsCache[key];
  // Once refs data has loaded, vertex indices MUST come from that same
  // fetch's own cp reconstruction -- result.cp is a separate, independently
  // reconstructed object from the original /api/search call, and nothing
  // guarantees the two put vertices in the same order. Using result.cp here
  // after data is cached was the actual bug: clicks would set an index that
  // silently pointed at the wrong vertex in cached.refs.
  const cp = cached ? cached.cp : result.cp;

  const segments = parseCp4D(cp);
  const bounds = boundsFromSegments(segments);
  const scale = fitScale(bounds, 400, 400);

  for (const segment of segments) {
    const mv = (segment.type == null) ? "" : String(segment.type).trim().toLowerCase();
    const line = makeSvg("line", {
      x1: transformX(segment.x1, bounds, scale, 400),
      y1: transformY(segment.y1, bounds, scale, 400),
      x2: transformX(segment.x2, bounds, scale, 400),
      y2: transformY(segment.y2, bounds, scale, 400),
      class: `cp-segment cp-${mv}`,
    });
    svg.appendChild(line);
  }

  if (!cached) {
    // Refs data (and its aligned cp) hasn't loaded yet -- show the pattern
    // but don't offer clickable vertices until indices are guaranteed correct.
    return;
  }

  const cartesianVertices = computeCartesianVertices(cp);
  cartesianVertices.forEach((pt, idx) => {
    const selected = idx === selectedRefsVertexIndex && refsResultKey === key;
    const circle = makeSvg("circle", {
      cx: transformX(pt[0], bounds, scale, 400),
      cy: transformY(pt[1], bounds, scale, 400),
      r: selected ? 7 : 5,
      class: "refs-vertex" + (selected ? " refs-vertex-selected" : ""),
    });
    circle.addEventListener("click", () => {
      selectedRefsVertexIndex = idx;
      refsResultKey = key;
      renderDetail(result, state.currentDetailIndex);
    });
    svg.appendChild(circle);
  });
}

async function fetchRefsData(result) {
  const res = await fetch('/api/fetch_refs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tiling_id: result.tiling_id, N: result.N, symmetry: result.symmetry }),
  });
  if (!res.ok) {
    let message = `fetch_refs failed: ${res.status}`;
    try {
      const body = await res.json();
      if (body.error) message = body.error;
    } catch {}
    throw new Error(message);
  }
  return res.json();
}

function ensureRefsDataLoaded(result) {
  const key = resultKey(result);
  if (refsCache[key] || refsFetchInFlight[key]) return;

  refsFetchInFlight[key] = fetchRefsData(result)
    .then((data) => {
      refsCache[key] = data;
      delete refsFetchInFlight[key];
      if (state.currentDetailResult === result && state.detailViewModes.right === "refs") {
        renderDetail(result, state.currentDetailIndex);
      }
    })
    .catch((err) => {
      delete refsFetchInFlight[key];
      if (state.currentDetailResult === result && state.detailViewModes.right === "refs") {
        const el = document.getElementById("refsWorkspace");
        if (el) {
          el.classList.add("refs-placeholder");
          el.textContent = 'Fold guide unavailable: ' + err.message;
        }
      }
    });
}

function populateRefsWorkspace(container, result) {
  const key = resultKey(result);
  const cached = refsCache[key];

  if (!cached) {
    container.classList.add("refs-placeholder");
    container.textContent = "Loading fold guide...";
    return;
  }

  if (selectedRefsVertexIndex === null || refsResultKey !== key) {
    container.classList.add("refs-placeholder");
    container.textContent = "Click a vertex on the crease pattern to see its fold sequence.";
    return;
  }

  const ancestry = cached.refs ? cached.refs[selectedRefsVertexIndex] : null;
  if (!ancestry || ancestry.length === 0) {
    container.classList.add("refs-placeholder");
    container.textContent = "No fold reference found for this vertex.";
    return;
  }

  container.classList.remove("refs-placeholder");
  const targetXY = computeCartesianVertices(cached.cp)[selectedRefsVertexIndex];
  renderReferenceWorkspace(ancestry, targetXY); // looks up #refsWorkspace itself, must already be attached
}

export function renderDetail(result, index) {
  const lang = localStorage.getItem('explori_lang') || 'en';
  const dict = Locales[lang] || Locales['en'];

  state.currentDetailResult = result;
  state.currentDetailIndex = index;
  modalGrid.replaceChildren();
  if (!result) return;
  const norm = (Math.sqrt(result.heat.query.reduce((sum, val) => sum + val * val, 0)));
  const quality = getMatchQuality(result.distance/norm, state.queryNodeCount);
  
  // Use the universal English key for the CSS styling
  modalMeta.dataset.quality = quality.key; 
  modalMeta.classList.add("match-quality");
  
  // Use the translated label for the display text
  // modalMeta.textContent = `${dict.matchQuality}: ${quality.label} • ${dict.distance}: ${(result.distance/norm).toFixed(4)} • ${dict.tilingId}: ${result.N}${symmetry_abbr[result.symmetry]}.${result.tiling_id}`;
  modalMeta.textContent = `${dict.tilingId}: ${result.N}${symmetry_abbr[result.symmetry]}.${result.tiling_id} • ${dict.matchQuality}: ${quality.label}`;
  
  const showingRefs = state.detailViewModes.right === "refs";
  if (showingRefs) {
    ensureRefsDataLoaded(result);
  }

  const leftPane = buildDetailPane({
    side: "left",
    activeValue: state.detailViewModes.left,
    // Note: Reusing the dict.thumbCp and dict.thumbPacking translations here!
    options: [ { value: "cp", label: dict.thumbCp }, { value: "packing", label: dict.thumbPacking } ],
    renderActive: (svg, currentValue) => {
      if (showingRefs) {
        // Fold guide needs a clickable crease pattern specifically -- the
        // left toggle is left as-is visually, but its choice doesn't apply
        // while picking a target vertex.
        renderClickableCp(svg, result);
      } else if (currentValue === "packing" && result.packing) {
        renderPackingSvg(svg, result.packing, 400, 400);
      } else {
        renderCpSvg(svg, result.cp, 400, 400);
      }
    },
  });

  const downloadBtn = document.createElement("button");
  downloadBtn.type = "button";
  downloadBtn.className = "detail-toggle-option detail-download-btn";
  downloadBtn.textContent = "Download tree";
  downloadBtn.addEventListener("click", () => downloadResultTree(result));

  const rightPane = buildDetailPane({
    side: "right",
    activeValue: state.detailViewModes.right,
    options: [
      { value: "tree", label: dict.thumbTree },
      { value: "fold", label: dict.thumbFold },
      { value: "refs", label: "Show fold guide" },
    ],
    extraToggleElement: downloadBtn,
    customBody: showingRefs ? (() => {
      const div = document.createElement("div");
      div.id = "refsWorkspace";
      div.className = "refs-workspace";
      return div;
    })() : null,
    renderActive: (svg, currentValue) => {
      if (currentValue === "fold" && result.fold) {
        // Pass 400, 400 so it matches the viewBox square
        renderFoldSvg(svg, result.fold, 400, 400); 
      } else {
        renderGraphSvg(svg, result.tree, { nodeFill: "#8cffc1", width: 400, height: 400 });
      }
    },
  });

  modalGrid.appendChild(leftPane);
  modalGrid.appendChild(rightPane);

  // #refsWorkspace must be attached to the live document before
  // renderReferenceWorkspace() (which looks it up by that id) can populate
  // it -- so this only happens after both panes are appended above.
  if (showingRefs) {
    const refsWorkspaceEl = document.getElementById("refsWorkspace");
    if (refsWorkspaceEl) populateRefsWorkspace(refsWorkspaceEl, result);
  }

  updateDetailNavButtons();
  const viewLink = document.getElementById("viewPatternLink");
  if (viewLink) {
    const N = result.N || "4";
    const sym = result.symmetry || "none";
    const symChar = sym === "diag" ? "d" : sym === "book" ? "b" : "n";
    const tilingId = result.tiling_id || "0";
    viewLink.href = `/view?id=${N}${symChar}${tilingId}`;
  }
  detailModal.classList.remove("hidden");
  detailModal.setAttribute("aria-hidden", "false");
}

registerDetailRenderer(renderDetail);
