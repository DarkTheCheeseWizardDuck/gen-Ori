"""
Rigid, hover-only debug viewer for a single object's tree.

Uses the EXACT SAME layout tree_adapter.py produces for the PNG and for
the real engine payload -- no separate layout algorithm. Hover an edge,
see its name. Nothing here is editable; this shows you what TAN actually
predicted, unmodified.
"""

from __future__ import annotations
from pathlib import Path

NODE_R = 5


def render_html(object_name: str, raw_parts: list[dict], payload: dict, edge_part_ids: list[str], out_path: Path):
    name_by_id = {p["id"]: p["name"] for p in raw_parts}

    nodes = payload["tree"]["nodes"]
    edges = payload["tree"]["edges"]
    pos = {n["id"]: (n["x"], n["y"]) for n in nodes}

    xs = [n["x"] for n in nodes]
    ys = [n["y"] for n in nodes]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    data_w = max(max_x - min_x, 1e-6)
    data_h = max(max_y - min_y, 1e-6)

    target = 600  # aim for a canvas roughly this size regardless of the object's raw coordinate scale
    scale = target / max(data_w, data_h)
    pad = 50
    width = data_w * scale + 2 * pad
    height = data_h * scale + 2 * pad
    ox, oy = pad - min_x * scale, pad - min_y * scale

    def sx(x): return x * scale + ox
    def sy(y): return y * scale + oy

    svg_parts = []
    for edge, part_id in zip(edges, edge_part_ids):
        x1, y1 = pos[edge["u"]]
        x2, y2 = pos[edge["v"]]
        name = name_by_id.get(part_id, "?")
        svg_parts.append(
            f'<g class="edge-group">'
            f'<line x1="{sx(x1):.1f}" y1="{sy(y1):.1f}" x2="{sx(x2):.1f}" y2="{sy(y2):.1f}" '
            f'stroke="#1C2541" stroke-width="2.5"/>'
            f'<line x1="{sx(x1):.1f}" y1="{sy(y1):.1f}" x2="{sx(x2):.1f}" y2="{sy(y2):.1f}" '
            f'stroke="#1C2541" stroke-width="14" opacity="0" '
            f'onmouseenter="showTip(event, \'{name}\')" onmouseleave="hideTip()"/>'
            f'</g>'
        )
    for n in nodes:
        svg_parts.append(f'<circle cx="{sx(n["x"]):.1f}" cy="{sy(n["y"]):.1f}" r="{NODE_R}" fill="#E8871E"/>')

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{object_name}</title>
<style>
  body {{ font-family: -apple-system, sans-serif; margin: 0; background: #fff; }}
  h1 {{ font-size: 15px; padding: 12px 16px; margin: 0; color: #1C2541; border-bottom: 1px solid #eee; }}
  #tooltip {{
    position: fixed; display: none; background: #1C2541; color: #fff;
    padding: 6px 10px; border-radius: 6px; font-size: 12px;
    pointer-events: none; z-index: 10;
  }}
  line {{ cursor: pointer; }}
</style>
</head>
<body>
<h1>{object_name} &mdash; hover an edge to see its name</h1>
<div id="tooltip"></div>
<svg width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">
{''.join(svg_parts)}
</svg>
<script>
function showTip(evt, text) {{
  const t = document.getElementById('tooltip');
  t.textContent = text;
  t.style.left = (evt.clientX + 14) + 'px';
  t.style.top = (evt.clientY + 14) + 'px';
  t.style.display = 'block';
}}
function hideTip() {{
  document.getElementById('tooltip').style.display = 'none';
}}
</script>
</body>
</html>
"""
    out_path.write_text(html, encoding="utf-8")


def build_index_html(names: list[str], out_path: Path):
    items = "\n".join(f'<li><a href="{n}.html">{n}</a></li>' for n in sorted(names))
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>TAN dataset viewer</title>
<style>
  body {{ font-family: -apple-system, sans-serif; padding: 20px; }}
  li {{ margin: 4px 0; }}
  a {{ color: #1C2541; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
</style></head>
<body>
<h2>Dataset viewer ({len(names)} objects)</h2>
<ul>{items}</ul>
</body></html>
"""
    out_path.write_text(html, encoding="utf-8")