"""
gen-Ori local web interface -- HTTP server wrapper.

STEP 1 of 4 (web server wrapper -> front end -> back end -> docker).
This file only sets up routing + static file serving + stub endpoints.
The stub endpoints below return placeholder JSON; real logic (calling
run_from_text() and query_tilings()) gets wired in during the "back end"
step, once the front end that consumes them exists.

Routes:
    GET  /                      -> static/index.html
    GET  /styles.css            -> static/styles.css
    GET  /static/<path>         -> anything under static/ (js/, assets/, ...)
    POST /api/generate          -> [stub] NL prompt -> tree payload
    POST /api/search            -> [stub] tree payload -> matched crease patterns

No Google Sheets logging, no interface token/auth, no /about or /view pages --
intentionally left out, not part of what was asked for. This is meant to run
locally only for now (127.0.0.1); revisit before ever exposing it beyond that.

Usage:
    python -m interface.server
"""

from __future__ import annotations

import traceback

import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import networkx as nx

STATIC_DIR = Path(__file__).resolve().parent / "static"
SEARCH25_ROOT = Path(__file__).resolve().parent.parent
GEN_ORI_TGG = SEARCH25_ROOT.parent / "tree graph generator"

if not GEN_ORI_TGG.exists():
    raise FileNotFoundError(
        f"Expected folder not found: {GEN_ORI_TGG}\n"
        "Edit GEN_ORI_TGG near the top of interface/server.py if your local "
        "layout differs (expects gen-Ori/tree graph generator and gen-Ori/search-25 as siblings)."
    )
sys.path.insert(0, str(GEN_ORI_TGG))

# Importing run_from_prompt (unmodified) wires gen-Ori/structure onto sys.path
# as a side effect, and lets us reuse its already-imported building blocks
# directly -- without calling its run_from_text()/run_from_raw_parts()
# wrappers, since those use build_tree_payload() (no part names). We want
# build_tree_payload_with_parts() instead, so TAN-original edges carry a
# name for the hover tooltip.
from run_from_prompt import run_pipeline, predict, merge_tan_output, load_model, CHECKPOINT_PATH  # noqa: E402
from tree_adapter import build_tree_payload_with_parts, validate_connected  # noqa: E402

from database.tilings.query import query_tilings  # noqa: E402
try:
    from database.tilings.inspect import pull_specific_tiling  # noqa: E402
    _REFS_AVAILABLE = True
except Exception as _refs_import_error:  # noqa: E402
    # database/refs/query.py connects to database/refs/storage/cp_pruned.db
    # at import time -- if that file/folder doesn't exist, importing
    # pull_specific_tiling fails. This only affects the fold-guide feature
    # (/api/fetch_refs); Generate/Search don't touch this database at all,
    # so the whole server shouldn't go down over it.
    print(f"[startup] Fold guide unavailable -- {_refs_import_error}")
    pull_specific_tiling = None
    _REFS_AVAILABLE = False
from database.tilings.faiss_cache import DIMENSION, E_SWEEP, compute_wks_signature  # noqa: E402
from src.engine.tree import EIG_COUNT, RESOLUTION, extract_eigenvalues  # noqa: E402

from interface.serialization import (  # noqa: E402
    serialize_cp,
    serialize_fold,
    serialize_graph,
    serialize_query_tree,
)

_MODEL = None  # loaded once at server startup, see main()

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
}


def _content_type_for(path: Path) -> str:
    return CONTENT_TYPES.get(path.suffix, "application/octet-stream")


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    content_length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(content_length) if content_length else b"{}"
    return json.loads(raw.decode("utf-8"))


def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def _send_bytes(handler: BaseHTTPRequestHandler, content_type: str, body: bytes) -> None:
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _serve_static_file(handler: BaseHTTPRequestHandler, rel_path: str) -> bool:
    """Serves a file from STATIC_DIR given a path relative to it.
    Returns True if it handled the request (found + served, or blocked as
    unsafe), False if the caller should keep trying other routes."""
    file_path = (STATIC_DIR / rel_path).resolve()

    # Basic path-traversal guard -- refuse anything that resolves outside STATIC_DIR.
    if STATIC_DIR not in file_path.parents and file_path != STATIC_DIR:
        return False
    if not file_path.is_file():
        return False

    body = file_path.read_bytes()
    _send_bytes(handler, _content_type_for(file_path), body)
    return True


def _tree_payload_to_query_graph(tree: dict[str, Any]) -> nx.Graph:
    """Mirrors search-25's own tree_payload_to_query_graph (see run_full_loop.py) --
    duplicated here rather than imported since this file has no dependency on
    the CLI tool and shouldn't gain one just for this."""
    graph = nx.Graph()
    nodes_by_id = {int(n["id"]): n for n in tree["nodes"]}
    for node_id, node in nodes_by_id.items():
        graph.add_node(node_id, pos=[float(node["x"]), float(node["y"])])
    for edge in tree["edges"]:
        u, v = int(edge["u"]), int(edge["v"])
        x1, y1 = nodes_by_id[u]["x"], nodes_by_id[u]["y"]
        x2, y2 = nodes_by_id[v]["x"], nodes_by_id[v]["y"]
        length = float(edge.get("length", ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5))
        length = max(length, 1e-5)
        graph.add_edge(u, v, length=length, weight=1.0 / length)
    return graph


def _build_heat_profile(query_tree: nx.Graph, result_tree: nx.Graph, N: int, symmetry: str) -> dict[str, Any]:
    query_eigs = extract_eigenvalues(query_tree, eig_count=EIG_COUNT, resolution=RESOLUTION)
    query_wks = compute_wks_signature(query_eigs, dim=DIMENSION)
    result_eigs = extract_eigenvalues(result_tree, eig_count=EIG_COUNT, resolution=RESOLUTION)
    result_wks = compute_wks_signature(result_eigs, dim=DIMENSION)
    return {
        "t_scales": [float(v) for v in E_SWEEP],
        "query": [float(v) for v in query_wks.tolist()],
        "result": [float(v) for v in result_wks.tolist()],
    }


def _build_response_bundle(query_tree: nx.Graph, results: list[dict[str, Any]], db_configs: list[tuple[int, str]]) -> dict[str, Any]:
    ui_results = []
    for res in results:
        tree_graph = res["tree"]
        ui_results.append({
            "rank": res.get("rank"),
            "distance": float(res.get("distance", 0.0)),
            "N": res.get("N"),
            "symmetry": res.get("symmetry"),
            "topology_id": res.get("topology_id"),
            "tiling_id": res.get("tiling_id"),
            "cp": serialize_cp(res["cp"]),
            "fold": serialize_fold(res["fold"]),
            "tree": serialize_graph(tree_graph),
            "packing": serialize_cp(res["packing"]),
            "heat": _build_heat_profile(query_tree, tree_graph, res["N"], res["symmetry"]),
        })
    return {
        "db_configs": [{"N": N, "symmetry": sym} for N, sym in db_configs],
        "query_tree": serialize_query_tree(query_tree),
        "results": ui_results,
    }


class InterfaceHandler(BaseHTTPRequestHandler):
    server_version = "genOriInterface/0.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    # ------------------------------------------------------------------ GET
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path in {"/", "/index.html"}:
            if _serve_static_file(self, "index.html"):
                return
            self.send_error(HTTPStatus.NOT_FOUND, "index.html not found in static/")
            return

        if path == "/styles.css":
            if _serve_static_file(self, "styles.css"):
                return
            self.send_error(HTTPStatus.NOT_FOUND, "styles.css not found")
            return

        if path.startswith("/static/"):
            rel = path[len("/static/"):]
            if _serve_static_file(self, rel):
                return
            self.send_error(HTTPStatus.NOT_FOUND, f"Not found: {rel}")
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    # ----------------------------------------------------------------- POST
    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/generate":
            self._handle_generate()
            return

        if path == "/api/search":
            self._handle_search()
            return

        if path == "/api/fetch_refs":
            self._handle_fetch_refs()
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    # ------------------------------------------------------------- handlers
    def _handle_generate(self) -> None:
        payload = _read_json(self)
        prompt = payload.get("prompt", "")
        if not prompt:
            _send_json(self, HTTPStatus.BAD_REQUEST, {"error": "prompt is required"})
            return

        try:
            upstream_result = run_pipeline(prompt)  # structure/pipeline.py, untouched
            raw_parts = upstream_result["structure"]["parts"]
            print(f"[generate] upstream returned {len(raw_parts)} raw_parts")

            tan_output = predict(_MODEL, raw_parts)
            print(f"[generate] TAN predicted {len(tan_output)} edges")

            merged = merge_tan_output(tan_output, raw_parts)
            tree_payload, edge_part_ids = build_tree_payload_with_parts(merged, root_direction_deg=0.0)
            validate_connected(tree_payload)

            # Attach each edge's originating part name, for the hover
            # tooltip -- only TAN-original edges get one; edges the user
            # later draws in the browser simply won't have this field.
            name_by_id = {p["id"]: p.get("name", p["id"]) for p in raw_parts}
            for edge, part_id in zip(tree_payload["tree"]["edges"], edge_part_ids):
                edge["original"] = True
                edge["name"] = name_by_id.get(part_id, part_id)

            object_name = upstream_result.get("intent", {}).get("object", "unnamed")
            n_nodes = len(tree_payload["tree"]["nodes"])
            n_edges = len(tree_payload["tree"]["edges"])
            print(f"[generate] prompt={prompt!r} object={object_name!r} "
                  f"raw_parts={len(raw_parts)} nodes={n_nodes} edges={n_edges}")
            _send_json(self, HTTPStatus.OK, {"tree": tree_payload["tree"], "object_name": object_name})
        except Exception as e:
            print(f"[generate] FAILED for prompt={prompt!r}:")
            traceback.print_exc()
            _send_json(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})

    def _handle_search(self) -> None:
        payload = _read_json(self)
        tree = payload.get("tree")
        if not tree or not tree.get("nodes"):
            _send_json(self, HTTPStatus.BAD_REQUEST, {"error": "tree is required"})
            return

        raw_configs = payload.get("db_configs") or [{"N": 4, "symmetry": "diag"}]
        db_configs = [(c["N"], c["symmetry"]) for c in raw_configs]
        n = int(payload.get("n", 5))

        try:
            query_graph = _tree_payload_to_query_graph(tree)
            if not nx.is_connected(query_graph):
                _send_json(self, HTTPStatus.BAD_REQUEST, {"error": "tree is disconnected"})
                return

            results = query_tilings(query_graph, db_configs=db_configs, n=n)
            bundle = _build_response_bundle(query_graph, results, db_configs)
            _send_json(self, HTTPStatus.OK, bundle)
        except Exception as e:
            print(f"[search] FAILED:")
            traceback.print_exc()
            _send_json(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})

    def _handle_fetch_refs(self) -> None:
        """Lazily computes the per-vertex fold-reference data for exactly one
        tiling, on demand -- this is expensive (real geometric reconstruction
        per vertex), so it's deliberately NOT computed for every /api/search
        result up front, only when the user actually opens the fold guide
        for a specific one."""
        if not _REFS_AVAILABLE:
            _send_json(self, HTTPStatus.SERVICE_UNAVAILABLE, {
                "error": "Fold guide unavailable: database/refs/storage/cp_pruned.db is missing.",
            })
            return

        payload = _read_json(self)
        try:
            tiling_id = int(payload["tiling_id"])
            N = int(payload["N"])
            symmetry = str(payload["symmetry"])
        except (KeyError, ValueError, TypeError):
            _send_json(self, HTTPStatus.BAD_REQUEST, {"error": "tiling_id, N, and symmetry are required"})
            return

        try:
            results = pull_specific_tiling(tiling_id, N, symmetry)
            if not results:
                _send_json(self, HTTPStatus.NOT_FOUND, {"error": "tiling not found"})
                return
            result = results[0]
            _send_json(self, HTTPStatus.OK, {
                "refs": result.get("refs", {}),
                "cp": serialize_cp(result["cp"]),
            })
        except Exception as e:
            print(f"[fetch_refs] FAILED for tiling_id={tiling_id} N={N} sym={symmetry}:")
            traceback.print_exc()
            _send_json(self, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})


def main() -> None:
    global _MODEL

    if not CHECKPOINT_PATH.exists():
        print(f"No checkpoint found at {CHECKPOINT_PATH} -- run gen-Ori's run_pipeline.py first.")
        sys.exit(1)

    # query_tilings() resolves its FAISS/sqlite paths relative to the
    # search-25 root (same convention the original SEARCH-22.5 README used).
    os.chdir(SEARCH25_ROOT)

    print("Loading TAN checkpoint...")
    _MODEL = load_model()

    host = os.environ.get("GENORI_INTERFACE_HOST", "127.0.0.1")
    port = int(os.environ.get("GENORI_INTERFACE_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), InterfaceHandler)
    print(f"gen-Ori interface listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
