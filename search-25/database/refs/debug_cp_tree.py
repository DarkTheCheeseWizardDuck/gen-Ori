"""
Diagnostic for cp_tree.py producing zero candidates at the root.
Run from the search-25 root:
    python -m database.refs.debug_cp_tree
"""
from database.refs.cp_tree import (
    make_root_cp,
    generate_vertex_pair_children,
    generate_angle_bisector_children,
    generate_perpendicular_children,
    generate_parallel_bisector_children,
)

root_cp = make_root_cp()
print(f"Root has {len(root_cp.vertices)} vertices, {len(root_cp.edges)} edges")
print(f"Vertices: {root_cp.vertices}")
print(f"Edges: {root_cp.edges}")

new_vertex_indices = set(range(len(root_cp.vertices)))

print("\n--- generate_vertex_pair_children ---")
try:
    kids = generate_vertex_pair_children(root_cp, new_vertex_indices)
    print(f"-> {len(kids)} children")
except Exception as e:
    print(f"-> RAISED: {e!r}")

print("\n--- generate_angle_bisector_children ---")
try:
    kids = generate_angle_bisector_children(root_cp, new_vertex_indices, depth=0)
    print(f"-> {len(kids)} children")
except Exception as e:
    print(f"-> RAISED: {e!r}")

print("\n--- generate_perpendicular_children ---")
try:
    kids = generate_perpendicular_children(root_cp, new_vertex_indices)
    print(f"-> {len(kids)} children")
except Exception as e:
    print(f"-> RAISED: {e!r}")

print("\n--- generate_parallel_bisector_children (new_crease_line=None, as root passes) ---")
try:
    kids = generate_parallel_bisector_children(root_cp, new_vertex_indices, None)
    print(f"-> {len(kids)} children")
except Exception as e:
    print(f"-> RAISED: {e!r}")

print("\n--- Deeper probe: first angle-bisector spec, step by step ---")
from database.refs.cp_tree import _BISECTOR_SPECS, _edge_exists_between, add_general_crease, _find_crease_boundary_endpoints, _copy_cp

spec = _BISECTOR_SPECS[0]
d_v1, d_v2 = spec['diagonal']
print(f"spec diagonal: {d_v1}, {d_v2}")
print(f"root vertices: {root_cp.vertices}")
exists = _edge_exists_between(root_cp, d_v1, d_v2)
print(f"_edge_exists_between(root_cp, d_v1, d_v2) -> {exists}")

if exists:
    new_cp = _copy_cp(root_cp)
    corner, target = spec['corner'], spec['target']
    print(f"corner={corner}  target={target}")
    result = add_general_crease(new_cp, corner, target, line_type='m')
    print(f"add_general_crease(...) -> {result!r}")
    if result is not None:
        bpts = _find_crease_boundary_endpoints(new_cp, corner, target, neighbors_fresh=True)
        print(f"_find_crease_boundary_endpoints(...) -> {bpts!r}")
else:
    print("Vertex identity mismatch confirmed: spec's diagonal vertices don't match root_cp's actual vertex objects.")
    try:
        ia = root_cp.vertices.index(d_v1)
        print(f"d_v1 found at index {ia}")
    except ValueError:
        print(f"d_v1 {d_v1} NOT found in root_cp.vertices at all (== comparison failing)")
    try:
        ib = root_cp.vertices.index(d_v2)
        print(f"d_v2 found at index {ib}")
    except ValueError:
        print(f"d_v2 {d_v2} NOT found in root_cp.vertices at all (== comparison failing)")

print("\n--- Probing why add_general_crease found < 2 hit points ---")
from database.refs.cp_general_crease import (
    line_segment_intersection_exact,
    _vertex_on_infinite_line,
    vertex4d_to_aplusbsqrt2_xy,
    aplusbsqrt2_xy_to_vertex4d,
    point_on_segment_exact,
    _fxy,
)

corner, target = spec['corner'], spec['target']
cx, cy = vertex4d_to_aplusbsqrt2_xy(corner)
tx, ty = vertex4d_to_aplusbsqrt2_xy(target)
print(f"corner cartesian: ({cx}, {cy})")
print(f"target cartesian: ({tx}, {ty})")

for ei, (v1i, v2i, etype) in enumerate(root_cp.edges):
    v1, v2 = root_cp.vertices[v1i], root_cp.vertices[v2i]
    on_line_1 = _vertex_on_infinite_line(corner, target, v1)
    on_line_2 = _vertex_on_infinite_line(corner, target, v2)
    pt = line_segment_intersection_exact(corner, target, v1, v2)
    print(f"edge {ei} ({v1i}->{v2i}, {etype}): v1_on_line={on_line_1} v2_on_line={on_line_2} intersection={pt!r}")

print("\n--- Fully instrumented re-trace of edge 1 (BR->TR) intersection ---")
lp1, lp2 = corner, target
sp1, sp2 = root_cp.vertices[1], root_cp.vertices[2]  # BR, TR

lp1x, lp1y = vertex4d_to_aplusbsqrt2_xy(lp1)
lp2x, lp2y = vertex4d_to_aplusbsqrt2_xy(lp2)
sp1x, sp1y = vertex4d_to_aplusbsqrt2_xy(sp1)
sp2x, sp2y = vertex4d_to_aplusbsqrt2_xy(sp2)
print(f"lp1=({lp1x!r},{lp1y!r})  lp2=({lp2x!r},{lp2y!r})")
print(f"sp1=({sp1x!r},{sp1y!r})  sp2=({sp2x!r},{sp2y!r})")

dlx = lp2x - lp1x;  dly = lp2y - lp1y
dsx = sp2x - sp1x;  dsy = sp2y - sp1y
rx  = sp1x - lp1x;  ry  = sp1y - lp1y
print(f"dlx={dlx!r} dly={dly!r} dsx={dsx!r} dsy={dsy!r} rx={rx!r} ry={ry!r}")

det = dly * dsx - dlx * dsy
print(f"det={det!r}  (det == 0) -> {det == 0}")

if det != 0:
    t_num = dsx * ry - dsy * rx
    print(f"t_num={t_num!r}")
    px = lp1x + t_num * dlx / det
    py = lp1y + t_num * dly / det
    print(f"px={px!r} py={py!r}")
    pt2 = aplusbsqrt2_xy_to_vertex4d(px, py)
    print(f"pt (reconstructed Vertex4D)={pt2!r}")
    print(f"pt == target -> {pt2 == target}")

    on_seg = point_on_segment_exact(sp1, sp2, pt2)
    print(f"point_on_segment_exact(sp1, sp2, pt2) -> {on_seg}")

    print("\n--- Testing AplusBsqrt2.sign() correctness on a known-positive mixed-sign value ---")
    dx = sp2x - sp1x
    dy = sp2y - sp1y
    ex = px - sp1x
    ey = py - sp1y
    dot = dx * ex + dy * ey
    len2 = dx * dx + dy * dy
    print(f"dot={dot!r}")
    print(f"dir(dot) = {[a for a in dir(dot) if not a.startswith('_')]}")
    # Try common attribute-name patterns to get the rational/irrational parts.
    a_val = b_val = None
    for name_a, name_b in [("A", "B"), ("a", "b"), ("rational", "irrational"), ("real", "sqrt2")]:
        if hasattr(dot, name_a) and hasattr(dot, name_b):
            a_val, b_val = getattr(dot, name_a), getattr(dot, name_b)
            print(f"Found components via .{name_a}/.{name_b}: a={a_val} b={b_val}")
            break
    if a_val is not None:
        true_val = float(a_val) + float(b_val) * (2 ** 0.5)
        print(f"dot true numeric value ~ {true_val:.6f} (should be POSITIVE)")
    print(f"dot.sign()={dot.sign()}")
    diff = len2 - dot
    print(f"(len2 - dot)={diff!r}")
    print(f"(len2-dot).sign()={diff.sign()}")

    print("\n--- Instrumented copy of point_on_segment_exact's own logic ---")
    import numpy as np

    def instrumented_point_on_segment(p1, p2, pt):
        if p1 == pt or p2 == pt:
            print("  RETURN True: p1==pt or p2==pt")
            return True
        EPS = 1e-9
        ax_f, ay_f = _fxy(p1); bx_f, by_f = _fxy(p2); px_f, py_f = _fxy(pt)
        print(f"  float coords: p1=({ax_f},{ay_f}) p2=({bx_f},{by_f}) pt=({px_f},{py_f})")
        if (px_f < min(ax_f, bx_f) - EPS or px_f > max(ax_f, bx_f) + EPS or
            py_f < min(ay_f, by_f) - EPS or py_f > max(ay_f, by_f) + EPS):
            print("  RETURN False: bounding box reject")
            return False
        dx_f = bx_f - ax_f; dy_f = by_f - ay_f
        cross_f = dx_f * (py_f - ay_f) - dy_f * (px_f - ax_f)
        print(f"  cross_f={cross_f}  threshold={EPS * (np.hypot(dx_f, dy_f) + EPS)}")
        if abs(cross_f) > EPS * (np.hypot(dx_f, dy_f) + EPS):
            print("  RETURN False: float cross-product reject")
            return False
        ax, ay = vertex4d_to_aplusbsqrt2_xy(p1)
        bx, by = vertex4d_to_aplusbsqrt2_xy(p2)
        px2, py2 = vertex4d_to_aplusbsqrt2_xy(pt)
        dx = bx - ax; dy = by - ay
        ex = px2 - ax; ey = py2 - ay
        cross = dx * ey - dy * ex
        print(f"  exact cross={cross!r}  (cross == 0) -> {cross == 0}")
        if not cross == 0:
            print("  RETURN False: exact cross != 0")
            return False
        dot2 = dx * ex + dy * ey
        len2b = dx * dx + dy * dy
        print(f"  dot={dot2!r} sign={dot2.sign()}  len2={len2b!r}")
        if dot2.sign() < 0:
            print("  RETURN False: dot.sign() < 0")
            return False
        diff2 = len2b - dot2
        print(f"  (len2-dot)={diff2!r} sign={diff2.sign()}")
        if diff2.sign() < 0:
            print("  RETURN False: (len2-dot).sign() < 0")
            return False
        print("  RETURN True: fell through")
        return True

    result = instrumented_point_on_segment(sp1, sp2, pt2)
    print(f"instrumented result: {result}")

    print("\n--- Confirming the fix: does .sign() correctly detect true zero? ---")
    ax3, ay3 = vertex4d_to_aplusbsqrt2_xy(sp1)
    bx3, by3 = vertex4d_to_aplusbsqrt2_xy(sp2)
    px3, py3 = vertex4d_to_aplusbsqrt2_xy(pt2)
    dx3 = bx3 - ax3; dy3 = by3 - ay3
    ex3 = px3 - ax3; ey3 = py3 - ay3
    cross3 = dx3 * ey3 - dy3 * ex3
    print(f"cross3={cross3!r}")
    print(f"cross3 == 0 -> {cross3 == 0}  (known broken)")
    print(f"cross3.sign() -> {cross3.sign()}  (should be 0 for true zero)")
    print(f"cross3.sign() == 0 -> {cross3.sign() == 0}  (this is the fix)")