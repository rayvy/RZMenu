"""
SVG → Mesh Vertex Buffer Compiler v2
=====================================
Replaces the command-stream approach with actual GPU mesh triangles.

Vertex layout (2x float4 per vertex):
  float4[0] = (pos.x, pos.y, color.r, color.g)
  float4[1] = (color.b, color.a, edge_dist, mesh_type)

mesh_type:
  0.0 = static icon (keyboard) — positioned at fixed screen offset
  1.0 = cursor icon            — VS adds CursorPos offset at runtime

edge_dist:
  1.0 = interior vertex (opaque)
  0.0 = AA-strip outer vertex (transparent → smoothstep in PS)

Output file layout:
  float4[0] = header: (keyboard_vert_count, cursor_vert_count, total, 0)
  float4[1..] = vertices (2 float4 each)

Usage:
  python test_svg_compiler_v2.py
  → prints exact draw count for core.j2
"""

import re
import math
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

AA_WIDTH = 1.5   # pixels of anti-alias fringe
CANVAS   = 280.0 # usable canvas inside 300x300
MARGIN   = 10.0  # padding on each side
BEZIER_SUBDIVISIONS = 1  # segments per quadratic bezier when tessellating to polyline


# ---------------------------------------------------------------------------
# Shared SVG parsing helpers (reused from v1)
# ---------------------------------------------------------------------------

def tokenize_path(d_string):
    token_pattern = re.compile(r'([a-df-zA-DF-Z])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)')
    tokens = []
    for match in token_pattern.finditer(d_string):
        cmd, num = match.groups()
        if cmd:
            tokens.append(cmd)
        elif num:
            tokens.append(float(num))
    return tokens


def cubic_to_quadratic(p0, p1, p2, p3, num_segments=4):
    quads = []
    def eval_cubic(t):
        mt = 1.0 - t
        return (
            mt**3*p0[0] + 3*mt**2*t*p1[0] + 3*mt*t**2*p2[0] + t**3*p3[0],
            mt**3*p0[1] + 3*mt**2*t*p1[1] + 3*mt*t**2*p2[1] + t**3*p3[1]
        )
    for i in range(num_segments):
        t0, t1 = i/num_segments, (i+1)/num_segments
        tm = (t0+t1)/2.0
        a, b, m = eval_cubic(t0), eval_cubic(t1), eval_cubic(tm)
        cx = 2*m[0] - 0.5*(a[0]+b[0])
        cy = 2*m[1] - 0.5*(a[1]+b[1])
        quads.append((a, (cx, cy), b))
    return quads


def eval_quadratic(p0, p1, p2, t):
    mt = 1.0 - t
    return (mt*mt*p0[0] + 2*mt*t*p1[0] + t*t*p2[0],
            mt*mt*p0[1] + 2*mt*t*p1[1] + t*t*p2[1])


def bezier_to_polyline(p0, p1, p2, n=BEZIER_SUBDIVISIONS):
    pts = []
    for i in range(n + 1):
        pts.append(eval_quadratic(p0, p1, p2, i / n))
    return pts


def parse_color(color_str):
    if not color_str:
        return (1.0, 1.0, 1.0, 1.0)
    s = color_str.strip().lower()
    if s in ('none', 'transparent'):
        return None  # signal: no fill
    if s.startswith('#'):
        h = s[1:]
        if len(h) == 3:
            h = h[0]*2 + h[1]*2 + h[2]*2
        if len(h) == 6:
            return (int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255, 1.0)
    if s.startswith('rgb'):
        m = re.findall(r'\d+', s)
        if len(m) >= 3:
            return (int(m[0])/255, int(m[1])/255, int(m[2])/255, 1.0)
    names = {
        'white':(1,1,1,1), 'black':(0,0,0,1), 'red':(1,0,0,1),
        'green':(0,1,0,1), 'blue':(0,0,1,1), 'yellow':(1,1,0,1),
        'cyan':(0,1,1,1),  'magenta':(1,0,1,1)
    }
    return names.get(s, (1.0, 1.0, 1.0, 1.0))


def parse_style(style_str):
    styles = {}
    if not style_str:
        return styles
    for item in style_str.split(';'):
        if ':' in item:
            k, v = item.split(':', 1)
            styles[k.strip().lower()] = v.strip()
    return styles


def get_attr(elem, name, default=None):
    styles = parse_style(elem.get('style', ''))
    if name in styles:
        return styles[name]
    return elem.get(name, default)


# ---------------------------------------------------------------------------
# SVG path → list of closed polylines
# ---------------------------------------------------------------------------

def parse_svg_path_to_polylines(d_str):
    """Returns list of polylines. Each polyline is a list of (x,y) tuples (closed)."""
    tokens = tokenize_path(d_str)
    polylines = []
    current_poly = []
    curr_x = curr_y = 0.0
    start_x = start_y = 0.0
    last_ctrl_x = last_ctrl_y = 0.0
    last_cmd = None

    arg_counts = {
        'M':2,'m':2,'L':2,'l':2,'H':1,'h':1,'V':1,'v':1,
        'C':6,'c':6,'S':4,'s':4,'Q':4,'q':4,'T':2,'t':2,'Z':0,'z':0
    }

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if isinstance(tok, str):
            cmd = tok; i += 1
        else:
            if last_cmd is None: i += 1; continue
            cmd = last_cmd
            if cmd == 'M': cmd = 'L'
            elif cmd == 'm': cmd = 'l'

        cu = cmd.upper()
        if cu not in arg_counts: continue
        cnt = arg_counts[cu]
        if i + cnt > len(tokens): break
        args = tokens[i:i+cnt]; i += cnt

        if cmd == 'M':
            if current_poly: polylines.append(current_poly); current_poly = []
            curr_x, curr_y = args[0], args[1]
            start_x, start_y = curr_x, curr_y
            current_poly.append((curr_x, curr_y))
            last_ctrl_x, last_ctrl_y = curr_x, curr_y
        elif cmd == 'm':
            if current_poly: polylines.append(current_poly); current_poly = []
            curr_x += args[0]; curr_y += args[1]
            start_x, start_y = curr_x, curr_y
            current_poly.append((curr_x, curr_y))
            last_ctrl_x, last_ctrl_y = curr_x, curr_y
        elif cmd == 'L':
            curr_x, curr_y = args[0], args[1]
            current_poly.append((curr_x, curr_y))
            last_ctrl_x, last_ctrl_y = curr_x, curr_y
        elif cmd == 'l':
            curr_x += args[0]; curr_y += args[1]
            current_poly.append((curr_x, curr_y))
            last_ctrl_x, last_ctrl_y = curr_x, curr_y
        elif cmd == 'H':
            curr_x = args[0]
            current_poly.append((curr_x, curr_y))
            last_ctrl_x, last_ctrl_y = curr_x, curr_y
        elif cmd == 'h':
            curr_x += args[0]
            current_poly.append((curr_x, curr_y))
            last_ctrl_x, last_ctrl_y = curr_x, curr_y
        elif cmd == 'V':
            curr_y = args[0]
            current_poly.append((curr_x, curr_y))
            last_ctrl_x, last_ctrl_y = curr_x, curr_y
        elif cmd == 'v':
            curr_y += args[0]
            current_poly.append((curr_x, curr_y))
            last_ctrl_x, last_ctrl_y = curr_x, curr_y
        elif cmd in ('C', 'c'):
            if cmd == 'c':
                p1 = (curr_x+args[0], curr_y+args[1])
                p2 = (curr_x+args[2], curr_y+args[3])
                p3 = (curr_x+args[4], curr_y+args[5])
            else:
                p1 = (args[0], args[1]); p2 = (args[2], args[3]); p3 = (args[4], args[5])
            quads = cubic_to_quadratic((curr_x, curr_y), p1, p2, p3)
            for qa, qc, qb in quads:
                pts = bezier_to_polyline(qa, qc, qb)
                current_poly.extend(pts[1:])
            curr_x, curr_y = p3; last_ctrl_x, last_ctrl_y = p2
        elif cmd in ('S', 's'):
            if last_cmd in ('C','c','S','s'):
                p1 = (2*curr_x - last_ctrl_x, 2*curr_y - last_ctrl_y)
            else:
                p1 = (curr_x, curr_y)
            if cmd == 's':
                p2 = (curr_x+args[0], curr_y+args[1]); p3 = (curr_x+args[2], curr_y+args[3])
            else:
                p2 = (args[0], args[1]); p3 = (args[2], args[3])
            quads = cubic_to_quadratic((curr_x, curr_y), p1, p2, p3)
            for qa, qc, qb in quads:
                pts = bezier_to_polyline(qa, qc, qb)
                current_poly.extend(pts[1:])
            curr_x, curr_y = p3; last_ctrl_x, last_ctrl_y = p2
        elif cmd in ('Q', 'q'):
            if cmd == 'q':
                p1 = (curr_x+args[0], curr_y+args[1]); p2 = (curr_x+args[2], curr_y+args[3])
            else:
                p1 = (args[0], args[1]); p2 = (args[2], args[3])
            pts = bezier_to_polyline((curr_x, curr_y), p1, p2)
            current_poly.extend(pts[1:])
            curr_x, curr_y = p2; last_ctrl_x, last_ctrl_y = p1
        elif cmd in ('T', 't'):
            if last_cmd in ('Q','q','T','t'):
                p1 = (2*curr_x - last_ctrl_x, 2*curr_y - last_ctrl_y)
            else:
                p1 = (curr_x, curr_y)
            if cmd == 't':
                p2 = (curr_x+args[0], curr_y+args[1])
            else:
                p2 = (args[0], args[1])
            pts = bezier_to_polyline((curr_x, curr_y), p1, p2)
            current_poly.extend(pts[1:])
            curr_x, curr_y = p2; last_ctrl_x, last_ctrl_y = p1
        elif cmd in ('Z', 'z'):
            current_poly.append((start_x, start_y))
            polylines.append(current_poly)
            current_poly = []
            curr_x, curr_y = start_x, start_y
            last_ctrl_x, last_ctrl_y = curr_x, curr_y

        last_cmd = cmd

    if current_poly:
        polylines.append(current_poly)

    return polylines


# ---------------------------------------------------------------------------
# Winding number — determine if a polyline is CW or CCW
# ---------------------------------------------------------------------------

def signed_area(pts):
    """Positive = CCW, Negative = CW (SVG Y-down: CW means hole in evenodd)."""
    n = len(pts)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1]
        area -= pts[j][0] * pts[i][1]
    return area / 2.0


def centroid(pts):
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return (cx, cy)


def point_in_polygon(pt, poly):
    """Ray casting — returns True if pt is inside poly."""
    x, y = pt
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]; xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-10) + xi):
            inside = not inside
        j = i
    return inside


# ---------------------------------------------------------------------------
# Tessellator: polyline → mesh triangles
# ---------------------------------------------------------------------------

def tessellate_fan(pts, color, mesh_type):
    """
    Simple triangle fan from centroid.
    Returns list of vertex tuples: (x, y, r, g, b, a, edge, mesh_type)
    """
    if len(pts) < 3:
        return []
    c = centroid(pts)
    verts = []
    n = len(pts)
    for i in range(n - 1):
        p0 = pts[i]
        p1 = pts[i + 1]
        verts.append((c[0],  c[1],  *color, 1.0, mesh_type))
        verts.append((p0[0], p0[1], *color, 1.0, mesh_type))
        verts.append((p1[0], p1[1], *color, 1.0, mesh_type))
    return verts


def tessellate_aa_strip(pts, color, mesh_type):
    """
    Generates a thin quad strip along each edge with alpha falloff for AA.
    Inner verts: edge=1.0 (opaque), outer verts: edge=0.0 (transparent).
    """
    verts = []
    n = len(pts)
    for i in range(n - 1):
        a = pts[i]; b = pts[i + 1]
        dx = b[0] - a[0]; dy = b[1] - a[1]
        length = math.sqrt(dx*dx + dy*dy)
        if length < 1e-6:
            continue
        # outward normal
        nx = -dy / length * AA_WIDTH
        ny =  dx / length * AA_WIDTH

        ai  = (a[0],      a[1],      *color, 1.0, mesh_type)  # inner a
        bi  = (b[0],      b[1],      *color, 1.0, mesh_type)  # inner b
        ao  = (a[0] + nx, a[1] + ny, color[0], color[1], color[2], 0.0, 0.0, mesh_type)  # outer a
        bo  = (b[0] + nx, b[1] + ny, color[0], color[1], color[2], 0.0, 0.0, mesh_type)  # outer b

        # quad → 2 triangles
        verts += [ai, bi, ao,
                  bi, bo, ao]
    return verts


# ---------------------------------------------------------------------------
# SVG element → polylines collector
# ---------------------------------------------------------------------------

def collect_polylines_from_elem(elem):
    """Returns list of (polyline_pts, color_rgba, is_hole) tuples."""
    result = []
    tag = elem.tag
    if '}' in tag:
        tag = tag.split('}', 1)[1]

    fill_str = get_attr(elem, 'fill', 'black')
    color = parse_color(fill_str) or (1.0, 1.0, 1.0, 1.0)

    if tag == 'path':
        d = elem.get('d', '')
        if not d:
            return result
        polylines = parse_svg_path_to_polylines(d)
        for poly in polylines:
            if len(poly) < 3:
                continue
            area = signed_area(poly)
            # Store winding, but don't decide is_hole here —
            # containment logic in tessellate_svg is more reliable for evenodd paths.
            is_hole = False  # placeholder; real detection done below
            result.append((poly, color, area))  # pass raw area instead of is_hole

    elif tag == 'rect':
        x = float(elem.get('x', 0)); y = float(elem.get('y', 0))
        w = float(elem.get('width', 0)); h = float(elem.get('height', 0))
        poly = [(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)]
        result.append((poly, color, False))

    elif tag == 'circle':
        cx = float(elem.get('cx', 0)); cy = float(elem.get('cy', 0))
        r  = float(elem.get('r', 0))
        poly = [(cx + r*math.cos(2*math.pi*i/32), cy + r*math.sin(2*math.pi*i/32))
                for i in range(32)]
        poly.append(poly[0])
        result.append((poly, color, False))

    elif tag == 'ellipse':
        cx = float(elem.get('cx', 0)); cy = float(elem.get('cy', 0))
        rx = float(elem.get('rx', 0)); ry = float(elem.get('ry', 0))
        poly = [(cx + rx*math.cos(2*math.pi*i/32), cy + ry*math.sin(2*math.pi*i/32))
                for i in range(32)]
        poly.append(poly[0])
        result.append((poly, color, False))

    elif tag == 'line':
        # lines have no fill; skip tessellated fill, add thin rect
        pass

    return result


# ---------------------------------------------------------------------------
# Bridge edge: merges a hole polygon into the outer polygon,
# creating one simply-connected polygon that tessellates correctly.
# ---------------------------------------------------------------------------

def bridge_hole_into_outer(outer, hole):
    """
    Finds the closest pair of vertices between outer and hole,
    then splices hole into outer via a duplicated bridge edge.
    Returns a new merged polygon list.
    """
    best_dist = float('inf')
    bi, bj = 0, 0
    for i, op in enumerate(outer):
        for j, hp in enumerate(hole):
            d = (op[0]-hp[0])**2 + (op[1]-hp[1])**2
            if d < best_dist:
                best_dist = d
                bi, bj = i, j

    # Splice: outer[0..bi] → bridge → hole[bj..end]+hole[0..bj] → bridge back → outer[bi..end]
    merged = (outer[:bi+1]
              + hole[bj:] + hole[:bj+1]  # traverse hole, return to bj
              + [outer[bi]]               # bridge back
              + outer[bi:])               # continue outer
    return merged


# ---------------------------------------------------------------------------
# Coordinate transform helper
# ---------------------------------------------------------------------------

def make_transform(all_polylines, canvas=CANVAS, margin=MARGIN):
    all_pts = [pt for poly, _, _area in all_polylines for pt in poly]
    if not all_pts:
        return None, None, None, None, None
    xs = [p[0] for p in all_pts]; ys = [p[1] for p in all_pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    w = max(max_x - min_x, 0.001); h = max(max_y - min_y, 0.001)
    scale = min(canvas / w, canvas / h)
    dx = margin + (canvas - w * scale) / 2.0
    dy = margin + (canvas - h * scale) / 2.0
    return min_x, min_y, scale, dx, dy


def transform_pt(pt, min_x, min_y, scale, dx, dy, flip_y=True, canvas=CANVAS, margin=MARGIN):
    x = (pt[0] - min_x) * scale + dx
    if flip_y:
        y = canvas + 2*margin - ((pt[1] - min_y) * scale + dy)
    else:
        y = (pt[1] - min_y) * scale + dy
    return (x, y)


def transform_polyline(poly, min_x, min_y, scale, dx, dy):
    return [transform_pt(p, min_x, min_y, scale, dx, dy) for p in poly]


# ---------------------------------------------------------------------------
# Main tessellation pass for one SVG
# ---------------------------------------------------------------------------

def tessellate_svg(input_svg, mesh_type=0.0):
    """
    Returns flat list of vertex tuples:
      (x, y, r, g, b, a, edge_dist, mesh_type)
    Uses containment-based evenodd rule + bridge edges for holes.
    """
    tree = ET.parse(input_svg)
    root = tree.getroot()

    raw_polys = []
    for elem in root.iter():
        raw_polys.extend(collect_polylines_from_elem(elem))

    if not raw_polys:
        print(f"  [WARN] No geometry in {input_svg}")
        return []

    min_x, min_y, scale, dx, dy = make_transform(raw_polys)
    if scale is None:
        return []

    # Transform all polylines to screen space first
    t_shapes = []
    for poly, color, area in raw_polys:
        if len(poly) < 3:
            continue
        tpoly = transform_polyline(poly, min_x, min_y, scale, dx, dy)
        t_shapes.append((tpoly, color, area))

    print(f"  Scale={scale:.4f}  Offset=({dx:.1f},{dy:.1f})  Shapes={len(t_shapes)}")

    # --- Evenodd containment: a shape is a hole if its centroid is inside
    # an ODD number of other shapes (regardless of winding direction).
    def count_containing(idx):
        c = centroid(t_shapes[idx][0])
        count = 0
        for j, (opoly, _, _) in enumerate(t_shapes):
            if j != idx and point_in_polygon(c, opoly):
                count += 1
        return count

    outers = []  # (tpoly, color)
    holes  = []  # (tpoly, color)
    for i, (tpoly, color, _) in enumerate(t_shapes):
        depth = count_containing(i)
        if depth % 2 == 0:
            outers.append((tpoly, color))
        else:
            holes.append((tpoly, color))

    print(f"  Outers={len(outers)}  Holes={len(holes)}")

    all_verts = []

    for tpoly, color in outers:
        # Find holes that belong inside this outer shape
        relevant_holes = []
        for hpoly, _ in holes:
            hc = centroid(hpoly)
            if point_in_polygon(hc, tpoly):
                relevant_holes.append(hpoly)

        if relevant_holes:
            # Bridge each hole into the outer polygon one by one
            merged = tpoly
            for hpoly in relevant_holes:
                merged = bridge_hole_into_outer(merged, hpoly)
            all_verts += tessellate_fan(merged, color, mesh_type)
            all_verts += tessellate_aa_strip(merged, color, mesh_type)
        else:
            all_verts += tessellate_fan(tpoly, color, mesh_type)
            all_verts += tessellate_aa_strip(tpoly, color, mesh_type)

    return all_verts


# ---------------------------------------------------------------------------
# Binary serializer
# ---------------------------------------------------------------------------

def write_combined_buffer(keyboard_verts, cursor_verts, output_path):
    """
    Writes combined buffer:
      float4[0] = header (keyboard_count, cursor_count, total, 0)
      float4[1..] = vertices, 2 float4 each
    """
    total = len(keyboard_verts) + len(cursor_verts)

    with open(output_path, 'wb') as f:
        # Header
        f.write(struct.pack('ffff',
                            float(len(keyboard_verts)),
                            float(len(cursor_verts)),
                            float(total), 0.0))
        # All vertices
        for vx, vy, r, g, b, a, edge, mtype in (keyboard_verts + cursor_verts):
            f.write(struct.pack('ffff', vx, vy, r, g))
            f.write(struct.pack('ffff', b, a, edge, mtype))

    size_kb = output_path.stat().st_size / 1024
    print(f"  Written: {output_path}  ({size_kb:.1f} KB)")
    print(f"  Keyboard verts : {len(keyboard_verts)}")
    print(f"  Cursor verts   : {len(cursor_verts)}")
    print(f"  Total verts    : {total}")
    print()
    print("=" * 50)
    print(f"  Add to core.j2 [CustomShaderDI2D.PASS.SYSTEM]:")
    print(f"    draw = {total}, 0")
    print("=" * 50)

    return total


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    script_dir = Path(__file__).parent
    addon_dir  = script_dir.parent
    modules    = addon_dir / "basic_pack" / "modules"

    keyboard_svg = modules / "keyboard.svg"
    cursor_svg   = modules / "cursor.svg"
    output_buf   = modules / "svg.svgmigoto"

    print(f"[SVG Compiler v2 — Mesh Mode]")
    print()

    keyboard_verts = []
    if keyboard_svg.exists():
        print(f"-> Tessellating keyboard: {keyboard_svg}")
        keyboard_verts = tessellate_svg(keyboard_svg, mesh_type=0.0)
    else:
        print(f"  [SKIP] keyboard.svg not found at {keyboard_svg}")

    cursor_verts = []
    if cursor_svg.exists():
        print(f"→ Tessellating cursor: {cursor_svg}")
        cursor_verts = tessellate_svg(cursor_svg, mesh_type=1.0)
    else:
        print(f"  [SKIP] cursor.svg not found — cursor will use procedural PS fallback")

    print()
    print(f"→ Writing combined buffer: {output_buf}")
    total = write_combined_buffer(keyboard_verts, cursor_verts, output_buf)

    # Copy to QA dir
    qa_out = script_dir / "svg.svgmigoto"
    import shutil
    shutil.copy2(output_buf, qa_out)
    print(f"  Copied to QA: {qa_out}")

    # Copy to active mod
    mod_modules = Path("g:/XXMI/EFMI/Mods/YvonneCasualX/modules")
    if mod_modules.exists():
        shutil.copy2(output_buf, mod_modules / "svg.svgmigoto")
        print(f"  Copied to mod: {mod_modules / 'svg.svgmigoto'}")
