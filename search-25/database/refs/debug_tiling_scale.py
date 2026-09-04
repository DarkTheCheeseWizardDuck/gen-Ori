"""
Print a real tiling's actual vertex coordinates to see the true scale/range.
Run from search-25 root:
    python -m database.refs.debug_tiling_scale
Edit TILING_ID/N/SYMMETRY below to match the one you're testing.
"""
from database.tilings.inspect import pull_specific_tiling
from database.refs.cp_general_crease import vertex4d_to_aplusbsqrt2_xy

TILING_ID = 135701
N = 4
SYMMETRY = "diag"

results = pull_specific_tiling(TILING_ID, N, SYMMETRY)
result = results[0]
cp = result["cp"]

print(f"N={N}  symmetry={SYMMETRY}  tiling_id={TILING_ID}")
print(f"Total vertices: {len(cp.vertices)}")
print()

xs, ys = [], []
for i, v in enumerate(cp.vertices):
    x, y = vertex4d_to_aplusbsqrt2_xy(v)
    xf = float(x.A) + float(x.B) * (2 ** 0.5)
    yf = float(y.A) + float(y.B) * (2 ** 0.5)
    xs.append(xf); ys.append(yf)
    if i < 12:
        print(f"  v{i}: raw={v!r}  cartesian=({xf:.4f}, {yf:.4f})")

print(f"\nx range: [{min(xs):.4f}, {max(xs):.4f}]")
print(f"y range: [{min(ys):.4f}, {max(ys):.4f}]")
