"""
The biggest loop: a natural-language request goes in one end, matched
crease patterns come out the other.

    user input -> gen-Ori/tree graph generator/run_from_prompt.py::run_from_text()
                  [UNCHANGED, imported as-is -- this itself wraps:
                     structure/pipeline.py (smallest loop: NL -> JSON)
                     -> TAN -> tree_adapter.build_tree_payload()
                     (middle loop: NL -> rendered tree)]
               -> tree payload {"tree": {"nodes": [...], "edges": [...]}}
               -> tree_payload_to_query_graph()  [new, ~15 lines, see below]
               -> search-25/database/tilings/query.py::query_tilings()
                  [HKT/FAISS federated search across the tiling databases]
               -> top-N crease patterns rendered to PNG (+ optional megaplot)

This is the biggest loop. Nesting, smallest to largest:
    structure/pipeline.py            NL -> parts JSON
    run_from_prompt.py               NL -> rendered tree (calls the above)
    run_full_loop.py (this file)     NL -> matched, renderable crease patterns
                                      (calls the above, then queries search-25)

Neither structure/pipeline.py nor run_from_prompt.py is modified by this file
-- both are imported and called exactly as they already run standalone.

Expected layout (this file sits directly inside gen-Ori, alongside its other
subfolders -- adjust GEN_ORI_TGG / SEARCH25_ROOT below if yours differs):

    gen-Ori/
      structure/                       (upstream, untouched)
      tree graph generator/            run_from_prompt.py lives here
      search-25/                       offline+online subset of SEARCH-22.5
        database/
        src/
      run_full_loop.py                 <- this file

Requires:
    - tree graph generator/tan_checkpoint.pt to already exist
      (run gen-Ori's run_pipeline.py at least once first)
    - search-25's FAISS caches + tiling databases to already be built
      (run search-25's offline steps first -- see search-25/README notes)

Usage:
    python run_full_loop.py
    python run_full_loop.py "a reindeer with antlers and four legs"
    python run_full_loop.py "a reindeer with antlers and four legs" --n 8 --dbs 4:none 4:diag 3:none
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
from pathlib import Path

import networkx as nx
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Path wiring. Both sub-projects are imported as-is; nothing inside either
# one is edited by this script.
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
GEN_ORI_TGG = ROOT / "tree graph generator"
SEARCH25_ROOT = ROOT / "search-25"

for _p in (GEN_ORI_TGG, SEARCH25_ROOT):
    if not _p.exists():
        raise FileNotFoundError(
            f"Expected folder not found: {_p}\n"
            "Edit GEN_ORI_TGG / SEARCH25_ROOT near the top of run_full_loop.py "
            "if your local layout differs from the one described in this file's "
            "docstring."
        )
sys.path.insert(0, str(GEN_ORI_TGG))
sys.path.insert(0, str(SEARCH25_ROOT))

# run_from_prompt.py inserts gen-Ori/structure onto sys.path itself when
# imported, which is what wires up structure/pipeline.py -- so importing it
# here transitively pulls in the smallest loop too.
from run_from_prompt import run_from_text, load_model, CHECKPOINT_PATH  # noqa: E402

from database.tilings.query import query_tilings, draw_cp_ax, plot_query_megaplot  # noqa: E402


@contextlib.contextmanager
def _cwd(path: Path):
    """query_tilings() resolves its FAISS cache / sqlite paths relative to
    the search-25 root (same convention as the original SEARCH-22.5 README:
    everything is run from the project root). Temporarily chdir there so
    those relative paths resolve, then restore the previous cwd."""
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


# ---------------------------------------------------------------------------
# tree payload -> nx.Graph. This mirrors interface/server.py::_build_query_graph
# from the original SEARCH-22.5 -- but server.py itself isn't part of search-25
# (web deployment was intentionally left out), so this small equivalent lives
# here instead of being imported.
# ---------------------------------------------------------------------------
def tree_payload_to_query_graph(payload: dict) -> nx.Graph:
    tree = payload["tree"]
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


def parse_db_configs(raw: list[str]) -> list[tuple[int, str]]:
    """['4:none', '4:diag', '3:none'] -> [(4,'none'), (4,'diag'), (3,'none')]"""
    configs = []
    for item in raw:
        n_str, sym = item.split(":")
        configs.append((int(n_str), sym))
    return configs


def run_full_loop(
    user_input: str,
    model,
    n: int,
    db_configs: list[tuple[int, str]],
    out_dir: Path,
    show_megaplot: bool = False,
) -> list[dict]:
    # ---- smallest + middle loop (unchanged): NL -> rendered tree ----
    payload = run_from_text(user_input, model)

    # ---- bridge: tree payload -> query graph ----
    query_tree = tree_payload_to_query_graph(payload)
    if not nx.is_connected(query_tree):
        raise ValueError(
            "The tree produced by run_from_prompt.py is disconnected -- "
            "cannot query search-25 with it."
        )

    # ---- biggest loop's new part: query graph -> matched crease patterns ----
    print(f"\n=== Querying search-25 (n={n}, dbs={db_configs}) ===")
    with _cwd(SEARCH25_ROOT):
        results = query_tilings(query_tree, db_configs=db_configs, n=n)

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n=== {len(results)} result(s) ===")
    for res in results:
        print(
            f"  rank={res['rank']} dist={res['distance']:.5f} "
            f"N={res['N']} sym={res['symmetry']} tiling_id={res['tiling_id']}"
        )
        fig, ax = plt.subplots(figsize=(5, 5))
        draw_cp_ax(ax, res["cp"])
        png_path = out_dir / f"rank{res['rank']}_N{res['N']}_{res['symmetry']}_{res['tiling_id']}.png"
        fig.savefig(png_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"    -> {png_path.relative_to(ROOT)}")

    if show_megaplot and results:
        plot_query_megaplot(results, query_tree=query_tree)

    return results


def main():
    parser = argparse.ArgumentParser(description="Full loop: NL request -> matched crease patterns.")
    parser.add_argument("prompt", nargs="?", help="Natural language origami request")
    parser.add_argument("--n", type=int, default=5, help="Number of results to return")
    parser.add_argument(
        "--dbs",
        nargs="*",
        default=["4:none", "4:diag", "3:none"],
        help="Databases to search, as N:symmetry pairs (e.g. --dbs 4:none 4:diag 3:none)",
    )
    parser.add_argument("--out", default=None, help="Output folder for rendered CP PNGs")
    parser.add_argument("--megaplot", action="store_true", help="Also show the full diagnostic megaplot")
    args = parser.parse_args()

    if not CHECKPOINT_PATH.exists():
        print(f"No checkpoint found at {CHECKPOINT_PATH} -- run gen-Ori's run_pipeline.py first.")
        sys.exit(1)

    model = load_model()
    user_input = args.prompt if args.prompt else input("Origami request: ")
    db_configs = parse_db_configs(args.dbs)
    out_dir = Path(args.out) if args.out else (ROOT / "renders_full_loop")

    run_full_loop(user_input, model, args.n, db_configs, out_dir, args.megaplot)


if __name__ == "__main__":
    main()