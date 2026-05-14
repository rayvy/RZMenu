"""
element_static_map.py
Phase 0.5.5: Static ImageID/TextID/Color Buffer (2x float4 per entry)

Generates res/element_static_map.buf — a compact sorted array of
(element_id, imageID, textID, has_color, R, G, B, A) for all rzm.elements.
The CS (draw_controller.hlsl) uses this buffer to resolve static IDs and
colors without INI lines when the appropriate flags in x111 are set.

Format change from Phase 0.5:
  Each entry is now 2x float4 (32 bytes):
    float4 A: { float(id), float(imageID), float(textID), float(has_color) }
    float4 B: { float(R),  float(G),       float(B),      float(A)         }
  CS loop step must be i += 2.
"""

import struct
from pathlib import Path


# ─── Flag constants (mirrors draw_controller.hlsl) ───────────────────────────

FLAG_USE_STATIC_IMG   = 0x01   # bit 0: read imageID from ElementStaticMap
FLAG_USE_STATIC_TEXT  = 0x02   # bit 1: read textID  from ElementStaticMap
FLAG_IS_ELEMENT       = 0x04   # bit 2: this is a main rzm.element (not preset/helper)
FLAG_USE_STATIC_COLOR = 0x08   # bit 3: read RGBA color from ElementStaticMap (Phase 0.5.5)


def _safe_id(val):
    """Convert image_id/text_id to int safely (can be None, str, or int)."""
    if val is None:
        return -1
    try:
        v = int(val)
        return v if v >= 0 else -1
    except (TypeError, ValueError):
        return -1


def _safe_color(val):
    """Return (R, G, B, A) floats from a color value safely."""
    if val is None:
        return (0.0, 0.0, 0.0, 0.5)
    try:
        if hasattr(val, '__iter__'):
            c = list(val)
            while len(c) < 4:
                c.append(0.0)
            return (float(c[0]), float(c[1]), float(c[2]), float(c[3]))
    except Exception:
        pass
    return (0.0, 0.0, 0.0, 0.5)


def build_element_static_map(elements, image_mapping=None) -> bytes:
    """
    Build the binary ElementStaticMap buffer (Phase 0.5.5 format: 2x float4).

    Format: compact sorted array of 2x float4 entries:
        float4 A: { float(id), float(imageID), float(textID), float(has_color) }
        float4 B: { float(R),  float(G),       float(B),      float(A)         }
    Entries are sorted ascending by element id.
    Terminated by two sentinel float4: {0,0,0,0} {0,0,0,0}

    Args:
        elements: iterable of element objects (Blender RNA or dicts).
        image_mapping: dict mapping element IDs to packed instance IDs.

    Returns:
        bytes — binary content of element_static_map.buf
    """
    entries = []
    for elem in elements:
        eid = _get(elem, 'id', 0)
        img = _safe_id(_get(elem, 'image_id'))
        txt = _safe_id(_get(elem, 'text_id'))
        color_is_formula = bool(_get(elem, 'color_is_formula'))
        color_raw = _get(elem, 'color')
        r, g, b, a = _safe_color(color_raw)
        has_color = 0.0 if color_is_formula else 1.0

        # Phase 0.5: Use mapped instance ID instead of raw image_id
        if image_mapping and 'elements' in image_mapping:
            inst_id = image_mapping['elements'].get(str(int(eid)))
            if inst_id is not None:
                img = inst_id

        entries.append((
            int(eid),
            max(0, img) if img >= 0 else 0,
            max(0, txt) if txt >= 0 else 0,
            has_color, r, g, b, a
        ))

    # Sort ascending by id — allows future binary search optimisation
    entries.sort(key=lambda e: e[0])

    result = bytearray()
    for eid, img, txt, hc, r, g, b, a in entries:
        # float4 A
        result += struct.pack('<ffff', float(eid), float(img), float(txt), hc)
        # float4 B
        result += struct.pack('<ffff', r, g, b, a)

    # Sentinel: two float4 with id==0 — CS stops linear scan
    result += struct.pack('<ffff', 0.0, 0.0, 0.0, 0.0)
    result += struct.pack('<ffff', 0.0, 0.0, 0.0, 0.0)
    return bytes(result)


def build_element_flags_map(elements) -> dict:
    """
    Build the {element_id -> x111_flags} mapping for use in j2 templates.

    Returns a dict mapping each element's string id to its x111 bitmask.
    All rzm.elements (non-preset, non-helper) receive FLAG_IS_ELEMENT (0x04).
    Additionally:
        FLAG_USE_STATIC_IMG  (0x01) if image_id > 0 and no conditional/hover images
        FLAG_USE_STATIC_TEXT (0x02) if text_id  > 0 and no conditional texts
        FLAG_USE_STATIC_COLOR(0x08) if not color_is_formula (Phase 0.5.5)
    Presets and helpers receive flags=0 (CS skips lookup for them).
    """
    flags_map = {}
    for elem in elements:
        eid       = int(_get(elem, 'id', 0))
        is_preset = bool(_get(elem, 'is_preset'))
        is_helper = bool(_get(elem, 'is_helper'))

        if is_preset or is_helper:
            flags_map[str(eid)] = 0
            continue

        flags = FLAG_IS_ELEMENT

        # imageID: static only if no conditional images AND no hover_image_id
        img = _safe_id(_get(elem, 'image_id'))
        hover_img = _safe_id(_get(elem, 'hover_image_id'))
        cond_imgs = _get(elem, 'conditional_images')
        has_cond_images = bool(cond_imgs) or (hover_img > 0)
        if img > 0 and not has_cond_images:
            flags |= FLAG_USE_STATIC_IMG

        # textID: static only if no conditional texts
        txt = _safe_id(_get(elem, 'text_id'))
        cond_txts = _get(elem, 'conditional_texts')
        has_cond_texts = bool(cond_txts)
        if txt > 0 and not has_cond_texts:
            flags |= FLAG_USE_STATIC_TEXT

        # color: static if not a formula (Phase 0.5.5)
        color_is_formula = bool(_get(elem, 'color_is_formula'))
        if not color_is_formula:
            flags |= FLAG_USE_STATIC_COLOR

        flags_map[str(eid)] = flags

    return flags_map


def export_element_static_map(elements, output_path: str, image_mapping=None) -> dict:
    """
    Write element_static_map.buf to disk and return flags_map.

    Args:
        elements: iterable of element objects
        output_path: full path to output file (e.g. 'path/to/res/element_static_map.buf')
        image_mapping: dict mapping element IDs to packed instance IDs.

    Returns:
        dict {element_id: x111_flags} for use in j2 template context as 'elem_static_flags'
    """
    data = build_element_static_map(elements, image_mapping)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    n = len(data) // 32 - 1  # 32 bytes per entry (2x float4), subtract sentinel
    print(f"[ElementStaticMap v2] Written {len(data)} bytes ({n} entries) -> {path}")

    return build_element_flags_map(elements)


def _get(obj, attr, default=None):
    """Unified getter for both Blender RNA objects and dicts."""
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)
