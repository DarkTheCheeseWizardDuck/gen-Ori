"""
Diagnostic for why even trivial corner vertices return "no fold reference found".
Run from search-25 root:
    python -m database.refs.debug_lookup
"""
import sqlite3
from src.engine.math225_core import Vertex4D
from database.refs.cp_tree import v4d_to_z2, make_root_cp

CONN = sqlite3.connect("database/refs/storage/cp_pruned.db")

print("--- What's actually in vertex_index at depth 0? ---")
rows = CONN.execute(
    "SELECT node_id, depth, px, qx, dx, py, qy, dy FROM vertex_index WHERE depth = 0"
).fetchall()
for r in rows:
    print(r)
print(f"Total depth-0 entries: {len(rows)}")

print("\n--- What does the root's own BL corner convert to? ---")
root_cp = make_root_cp()
bl = root_cp.vertices[0]
print(f"BL vertex: {bl!r}")
z2 = v4d_to_z2(bl)
print(f"v4d_to_z2(BL) -> {z2}")

print("\n--- Does that exact tuple appear in vertex_index at all (any depth)? ---")
px, qx, dx, py, qy, dy = z2
match = CONN.execute(
    "SELECT node_id, depth FROM vertex_index WHERE px=? AND qx=? AND dx=? AND py=? AND qy=? AND dy=?",
    (px, qx, dx, py, qy, dy),
).fetchall()
print(f"Matches: {match}")

print("\n--- Sanity: total rows in vertex_index overall ---")
total = CONN.execute("SELECT COUNT(*) FROM vertex_index").fetchone()
print(f"Total vertex_index rows: {total[0]}")

print("\n--- Table schema, in case column meanings differ from assumption ---")
schema = CONN.execute("SELECT sql FROM sqlite_master WHERE name='vertex_index'").fetchone()
print(schema[0] if schema else "vertex_index table not found!")
