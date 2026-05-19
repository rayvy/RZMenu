import os
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

def tokenize_path(d_string):
    # Tokenizer supporting scientific notation and omitted separators
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
    """Approximates a cubic Bezier curve (p0, p1, p2, p3) with a sequence of quadratic Beziers."""
    quads = []
    def eval_cubic(t):
        mt = 1.0 - t
        return (
            mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0],
            mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
        )
    for i in range(num_segments):
        t0 = i / num_segments
        t1 = (i + 1) / num_segments
        t_mid = (t0 + t1) / 2.0
        a = eval_cubic(t0)
        b = eval_cubic(t1)
        m = eval_cubic(t_mid)
        # Midpoint interpolation formula: C = 2*M - (A + B)/2
        cx = 2 * m[0] - 0.5 * (a[0] + b[0])
        cy = 2 * m[1] - 0.5 * (a[1] + b[1])
        quads.append((a, (cx, cy), b))
    return quads

def parse_color(color_str):
    if not color_str:
        return (1.0, 1.0, 1.0)
    color_str = color_str.strip().lower()
    if color_str == 'none':
        return (1.0, 1.0, 1.0)
    if color_str.startswith('#'):
        hex_val = color_str[1:]
        if len(hex_val) == 3:
            r = int(hex_val[0]*2, 16) / 255.0
            g = int(hex_val[1]*2, 16) / 255.0
            b = int(hex_val[2]*2, 16) / 255.0
        elif len(hex_val) == 6:
            r = int(hex_val[0:2], 16) / 255.0
            g = int(hex_val[2:4], 16) / 255.0
            b = int(hex_val[4:6], 16) / 255.0
        else:
            return (1.0, 1.0, 1.0)
        return (r, g, b)
    if color_str.startswith('rgb'):
        matches = re.findall(r'\d+', color_str)
        if len(matches) >= 3:
            return (int(matches[0])/255.0, int(matches[1])/255.0, int(matches[2])/255.0)
    names = {
        'white': (1.0, 1.0, 1.0), 'black': (0.0, 0.0, 0.0), 'red': (1.0, 0.0, 0.0),
        'green': (0.0, 1.0, 0.0), 'blue': (0.0, 0.0, 1.0), 'yellow': (1.0, 1.0, 0.0),
        'cyan': (0.0, 1.0, 1.0), 'magenta': (1.0, 0.0, 1.0)
    }
    return names.get(color_str, (1.0, 1.0, 1.0))

def parse_style(style_str):
    styles = {}
    if not style_str:
        return styles
    for item in style_str.split(';'):
        if ':' in item:
            k, v = item.split(':', 1)
            styles[k.strip().lower()] = v.strip()
    return styles

def get_style_or_attr(elem, name, default=None):
    styles = parse_style(elem.get('style', ''))
    if name in styles:
        return styles[name]
    val = elem.get(name)
    if val is not None:
        return val
    return default

def parse_svg_path(d_str):
    tokens = tokenize_path(d_str)
    commands = []
    arg_counts = {
        'M': 2, 'm': 2, 'L': 2, 'l': 2, 'H': 1, 'h': 1, 'V': 1, 'v': 1,
        'C': 6, 'c': 6, 'S': 4, 's': 4, 'Q': 4, 'q': 4, 'T': 2, 't': 2, 'Z': 0, 'z': 0
    }
    curr_x, curr_y = 0.0, 0.0
    start_x, start_y = 0.0, 0.0
    last_control_x, last_control_y = 0.0, 0.0
    last_cmd = None
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if isinstance(token, str):
            cmd = token
            i += 1
        else:
            if last_cmd is None:
                i += 1
                continue
            cmd = last_cmd
            if cmd == 'M': cmd = 'L'
            elif cmd == 'm': cmd = 'l'
        cmd_upper = cmd.upper()
        if cmd_upper not in arg_counts:
            continue
        count = arg_counts[cmd_upper]
        if i + count > len(tokens):
            break
        args = tokens[i:i+count]
        i += count
        
        if cmd == 'M':
            curr_x, curr_y = args[0], args[1]
            start_x, start_y = curr_x, curr_y
            last_control_x, last_control_y = curr_x, curr_y
        elif cmd == 'm':
            curr_x += args[0]
            curr_y += args[1]
            start_x, start_y = curr_x, curr_y
            last_control_x, last_control_y = curr_x, curr_y
        elif cmd == 'L':
            next_x, next_y = args[0], args[1]
            commands.append(('LINE', curr_x, curr_y, next_x, next_y))
            curr_x, curr_y = next_x, next_y
            last_control_x, last_control_y = curr_x, curr_y
        elif cmd == 'l':
            next_x = curr_x + args[0]
            next_y = curr_y + args[1]
            commands.append(('LINE', curr_x, curr_y, next_x, next_y))
            curr_x, curr_y = next_x, next_y
            last_control_x, last_control_y = curr_x, curr_y
        elif cmd == 'H':
            next_x = args[0]
            commands.append(('LINE', curr_x, curr_y, next_x, curr_y))
            curr_x = next_x
            last_control_x, last_control_y = curr_x, curr_y
        elif cmd == 'h':
            next_x = curr_x + args[0]
            commands.append(('LINE', curr_x, curr_y, next_x, curr_y))
            curr_x = next_x
            last_control_x, last_control_y = curr_x, curr_y
        elif cmd == 'V':
            next_y = args[0]
            commands.append(('LINE', curr_x, curr_y, curr_x, next_y))
            curr_y = next_y
            last_control_x, last_control_y = curr_x, curr_y
        elif cmd == 'v':
            next_y = curr_y + args[0]
            commands.append(('LINE', curr_x, curr_y, curr_x, next_y))
            curr_y = next_y
            last_control_x, last_control_y = curr_x, curr_y
        elif cmd == 'C':
            p1x, p1y, p2x, p2y, p3x, p3y = args
            quads = cubic_to_quadratic((curr_x, curr_y), (p1x, p1y), (p2x, p2y), (p3x, p3y))
            for q_start, q_ctrl, q_end in quads:
                commands.append(('BEZIER', q_start[0], q_start[1], q_ctrl[0], q_ctrl[1], q_end[0], q_end[1]))
            curr_x, curr_y = p3x, p3y
            last_control_x, last_control_y = p2x, p2y
        elif cmd == 'c':
            p1x = curr_x + args[0]
            p1y = curr_y + args[1]
            p2x = curr_x + args[2]
            p2y = curr_y + args[3]
            p3x = curr_x + args[4]
            p3y = curr_y + args[5]
            quads = cubic_to_quadratic((curr_x, curr_y), (p1x, p1y), (p2x, p2y), (p3x, p3y))
            for q_start, q_ctrl, q_end in quads:
                commands.append(('BEZIER', q_start[0], q_start[1], q_ctrl[0], q_ctrl[1], q_end[0], q_end[1]))
            curr_x, curr_y = p3x, p3y
            last_control_x, last_control_y = p2x, p2y
        elif cmd == 'S':
            if last_cmd in ('C', 'c', 'S', 's'):
                p1x = 2 * curr_x - last_control_x
                p1y = 2 * curr_y - last_control_y
            else:
                p1x, p1y = curr_x, curr_y
            p2x, p2y, p3x, p3y = args
            quads = cubic_to_quadratic((curr_x, curr_y), (p1x, p1y), (p2x, p2y), (p3x, p3y))
            for q_start, q_ctrl, q_end in quads:
                commands.append(('BEZIER', q_start[0], q_start[1], q_ctrl[0], q_ctrl[1], q_end[0], q_end[1]))
            curr_x, curr_y = p3x, p3y
            last_control_x, last_control_y = p2x, p2y
        elif cmd == 's':
            if last_cmd in ('C', 'c', 'S', 's'):
                p1x = 2 * curr_x - last_control_x
                p1y = 2 * curr_y - last_control_y
            else:
                p1x, p1y = curr_x, curr_y
            p2x = curr_x + args[0]
            p2y = curr_y + args[1]
            p3x = curr_x + args[2]
            p3y = curr_y + args[3]
            quads = cubic_to_quadratic((curr_x, curr_y), (p1x, p1y), (p2x, p2y), (p3x, p3y))
            for q_start, q_ctrl, q_end in quads:
                commands.append(('BEZIER', q_start[0], q_start[1], q_ctrl[0], q_ctrl[1], q_end[0], q_end[1]))
            curr_x, curr_y = p3x, p3y
            last_control_x, last_control_y = p2x, p2y
        elif cmd == 'Q':
            p1x, p1y, p2x, p2y = args
            commands.append(('BEZIER', curr_x, curr_y, p1x, p1y, p2x, p2y))
            curr_x, curr_y = p2x, p2y
            last_control_x, last_control_y = p1x, p1y
        elif cmd == 'q':
            p1x = curr_x + args[0]
            p1y = curr_y + args[1]
            p2x = curr_x + args[2]
            p2y = curr_y + args[3]
            commands.append(('BEZIER', curr_x, curr_y, p1x, p1y, p2x, p2y))
            curr_x, curr_y = p2x, p2y
            last_control_x, last_control_y = p1x, p1y
        elif cmd == 'T':
            if last_cmd in ('Q', 'q', 'T', 't'):
                p1x = 2 * curr_x - last_control_x
                p1y = 2 * curr_y - last_control_y
            else:
                p1x, p1y = curr_x, curr_y
            p2x, p2y = args
            commands.append(('BEZIER', curr_x, curr_y, p1x, p1y, p2x, p2y))
            curr_x, curr_y = p2x, p2y
            last_control_x, last_control_y = p1x, p1y
        elif cmd == 't':
            if last_cmd in ('Q', 'q', 'T', 't'):
                p1x = 2 * curr_x - last_control_x
                p1y = 2 * curr_y - last_control_y
            else:
                p1x, p1y = curr_x, curr_y
            p2x = curr_x + args[0]
            p2y = curr_y + args[1]
            commands.append(('BEZIER', curr_x, curr_y, p1x, p1y, p2x, p2y))
            curr_x, curr_y = p2x, p2y
            last_control_x, last_control_y = p1x, p1y
        elif cmd in ('Z', 'z'):
            if curr_x != start_x or curr_y != start_y:
                commands.append(('LINE', curr_x, curr_y, start_x, start_y))
            curr_x, curr_y = start_x, start_y
            last_control_x, last_control_y = curr_x, curr_y
        last_cmd = cmd
    return commands

def compile_svg(input_svg, output_bin):
    tree = ET.parse(input_svg)
    root = tree.getroot()
    
    commands = []
    current_color = None
    current_thickness = 2.0
    
    # Walk tree in-order to find elements
    for elem in root.iter():
        tag = elem.tag
        # Strip namespace if present
        if '}' in tag:
            tag = tag.split('}', 1)[1]
            
        if tag == 'path':
            d_val = elem.get('d')
            if not d_val:
                continue
                
            color_val = get_style_or_attr(elem, 'stroke')
            if not color_val:
                color_val = get_style_or_attr(elem, 'fill')
            elem_color = parse_color(color_val) if color_val else (1.0, 1.0, 1.0)
            
            thick_val = get_style_or_attr(elem, 'stroke-width')
            elem_thick = float(re.findall(r'[\d\.]+', thick_val)[0]) if (thick_val and re.findall(r'[\d\.]+', thick_val)) else 2.0
            
            if elem_color != current_color:
                commands.append(('COLOR', elem_color[0], elem_color[1], elem_color[2]))
                current_color = elem_color
            if elem_thick != current_thickness:
                commands.append(('WIDTH', elem_thick))
                current_thickness = elem_thick
                
            path_cmds = parse_svg_path(d_val)
            commands.extend(path_cmds)
            
        elif tag == 'rect':
            x = float(elem.get('x', 0))
            y = float(elem.get('y', 0))
            w = float(elem.get('width', 0))
            h = float(elem.get('height', 0))
            commands.append(('LINE', x, y, x + w, y))
            commands.append(('LINE', x + w, y, x + w, y + h))
            commands.append(('LINE', x + w, y + h, x, y + h))
            commands.append(('LINE', x, y + h, x, y))
            
        elif tag == 'line':
            x1 = float(elem.get('x1', 0))
            y1 = float(elem.get('y1', 0))
            x2 = float(elem.get('x2', 0))
            y2 = float(elem.get('y2', 0))
            commands.append(('LINE', x1, y1, x2, y2))
            
        elif tag in ('polyline', 'polygon'):
            pts_str = elem.get('points', '')
            pts = [float(x) for x in re.findall(r'-?\d*\.?\d+', pts_str)]
            if len(pts) >= 4:
                for idx in range(0, len(pts) - 3, 2):
                    commands.append(('LINE', pts[idx], pts[idx+1], pts[idx+2], pts[idx+3]))
                if tag == 'polygon':
                    commands.append(('LINE', pts[-2], pts[-1], pts[0], pts[1]))
                    
        elif tag == 'circle':
            cx = float(elem.get('cx', 0))
            cy = float(elem.get('cy', 0))
            r = float(elem.get('r', 0))
            # 4 quadratic Beziers approximation for quadrant arcs
            commands.append(('BEZIER', cx + r, cy, cx + r, cy + r, cx, cy + r))
            commands.append(('BEZIER', cx, cy + r, cx - r, cy + r, cx - r, cy))
            commands.append(('BEZIER', cx - r, cy, cx - r, cy - r, cx, cy - r))
            commands.append(('BEZIER', cx, cy - r, cx + r, cy - r, cx + r, cy))
            
        elif tag == 'ellipse':
            cx = float(elem.get('cx', 0))
            cy = float(elem.get('cy', 0))
            rx = float(elem.get('rx', 0))
            ry = float(elem.get('ry', 0))
            commands.append(('BEZIER', cx + rx, cy, cx + rx, cy + ry, cx, cy + ry))
            commands.append(('BEZIER', cx, cy + ry, cx - rx, cy + ry, cx - rx, cy))
            commands.append(('BEZIER', cx - rx, cy, cx - rx, cy - ry, cx, cy - ry))
            commands.append(('BEZIER', cx, cy - ry, cx + rx, cy - ry, cx + rx, cy))

    # Calculate bounding box to normalize coordinates to 300x300 canvas
    all_pts = []
    for cmd in commands:
        if cmd[0] == 'LINE':
            all_pts.extend([(cmd[1], cmd[2]), (cmd[3], cmd[4])])
        elif cmd[0] == 'BEZIER':
            all_pts.extend([(cmd[1], cmd[2]), (cmd[3], cmd[4]), (cmd[5], cmd[6])])
            
    if not all_pts:
        print("No paths or geometry found in SVG.")
        return False
        
    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    
    w = max(max_x - min_x, 0.001)
    h = max(max_y - min_y, 0.001)
    
    # Target fitting box is 280x280 (10px padding on each side of the 300x300 canvas)
    target_size = 280.0
    margin = 10.0
    scale = min(target_size / w, target_size / h)
    
    dx = margin + (target_size - w * scale) / 2.0
    dy = margin + (target_size - h * scale) / 2.0
    
    # Write binary float4 instructions
    # Each instruction is 4 floats (16 bytes)
    with open(output_bin, 'wb') as f:
        for cmd in commands:
            if cmd[0] == 'COLOR':
                f.write(struct.pack('ffff', 1.0, cmd[1], cmd[2], cmd[3]))
            elif cmd[0] == 'WIDTH':
                # Clamp thickness scaled down, minimum 1.2px
                scaled_thick = max(cmd[1] * scale, 1.2)
                f.write(struct.pack('ffff', 2.0, scaled_thick, 0.0, 0.0))
            elif cmd[0] == 'LINE':
                x0 = (cmd[1] - min_x) * scale + dx
                y0 = target_size - ((cmd[2] - min_y) * scale) + dy
                x1 = (cmd[3] - min_x) * scale + dx
                y1 = target_size - ((cmd[4] - min_y) * scale) + dy
                f.write(struct.pack('ffff', 3.0, x0, y0, x1))
                f.write(struct.pack('ffff', y1, 0.0, 0.0, 0.0))
            elif cmd[0] == 'BEZIER':
                x0 = (cmd[1] - min_x) * scale + dx
                y0 = target_size - ((cmd[2] - min_y) * scale) + dy
                x1 = (cmd[3] - min_x) * scale + dx
                y1 = target_size - ((cmd[4] - min_y) * scale) + dy
                x2 = (cmd[5] - min_x) * scale + dx
                y2 = target_size - ((cmd[6] - min_y) * scale) + dy
                f.write(struct.pack('ffff', 4.0, x0, y0, x1))
                f.write(struct.pack('ffff', y1, x2, y2, 0.0))
        # EOF instruction
        f.write(struct.pack('ffff', 0.0, 0.0, 0.0, 0.0))
        
    print(f"Successfully compiled SVG into raw float4 buffer: {output_bin}")
    print(f"Original bounding box: ({min_x:.1f}, {min_y:.1f}) -> ({max_x:.1f}, {max_y:.1f})")
    print(f"Target fitting dimensions: {w*scale:.1f}x{h*scale:.1f} at offset ({dx:.1f}, {dy:.1f})")
    return True

if __name__ == '__main__':
    # Determine paths relative to this script
    script_dir = Path(__file__).parent
    addon_dir = script_dir.parent
    
    src_svg = addon_dir / "basic_pack" / "modules" / "keyboard.svg"
    dst_buf = addon_dir / "basic_pack" / "modules" / "svg.svgmigoto"
    
    print(f"Compiling: {src_svg} -> {dst_buf}")
    if src_svg.exists():
        compile_svg(src_svg, dst_buf)
        
        # Also copy directly to the active QA directory for testing
        compile_svg(src_svg, script_dir / "svg.svgmigoto")
        
        # Check active mod directory (e.g. YvonneCasualX)
        fallback_mod_dir = Path("g:/XXMI/EFMI/Mods/YvonneCasualX/modules")
        if fallback_mod_dir.exists():
            print(f"Copying also to fallback active mod modules: {fallback_mod_dir}")
            compile_svg(src_svg, fallback_mod_dir / "svg.svgmigoto")
    else:
        print(f"Error: Source SVG not found at {src_svg}")
