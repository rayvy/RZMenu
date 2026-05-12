"""
element_static_map.py
Phase 0.5: Static ImageID/TextID Buffer

Generates res/element_static_map.buf — a compact sorted array of
(element_id, imageID, textID) for all rzm.elements.
The CS (draw_controller.hlsl) uses this buffer to resolve static IDs
without INI lines when $isElement flag (x111 bit 2) is set.
"""

import struct
from pathlib import Path


# ─── Flag constants (mirrors draw_controller.hlsl) ───────────────────────────

FLAG_USE_STATIC_IMG  = 0x01   # bit 0: read imageID from ElementStaticMap
FLAG_USE_STATIC_TEXT = 0x02   # bit 1: read textID  from ElementStaticMap
FLAG_IS_ELEMENT      = 0x04   # bit 2: this is a main rzm.element (not preset/helper)


def _safe_id(val):
    """Convert image_id/text_id to int safely (can be None, str, or int)."""
    if val is None:
        return -1
    try:
        v = int(val)
        return v if v >= 0 else -1
    except (TypeError, ValueError):
        return -1


def build_element_static_map(elements, image_mapping=None) -> bytes:
    """
    Build the binary ElementStaticMap buffer.

    Format: compact sorted array of float4 entries:
        float4{ float(id), float(imageID), float(textID), 0.0 }
    Entries are sorted ascending by element id.
    Terminated by a sentinel entry: {0.0, 0.0, 0.0, 0.0}

    Args:
        elements: iterable of element objects (Blender RNA or dicts).
                  Must have .id (or ['id']), .image_id, .text_id attributes.
        image_mapping: dict mapping element IDs to packed instance IDs.

    Returns:
        bytes — binary content of element_static_map.buf
    """
    entries = []
    for elem in elements:
        eid = _get(elem, 'id', 0)
        img = _safe_id(_get(elem, 'image_id'))
        txt = _safe_id(_get(elem, 'text_id'))
        
        # Phase 0.5: Use mapped instance ID instead of raw image_id
        if image_mapping and 'elements' in image_mapping:
            inst_id = image_mapping['elements'].get(str(eid))
            if inst_id is not None:
                img = inst_id

        entries.append((int(eid), max(0, img) if img >= 0 else 0,
                                  max(0, txt) if txt >= 0 else 0))

    # Sort ascending by id — allows future binary search optimisation
    entries.sort(key=lambda e: e[0])

    result = bytearray()
    for eid, img, txt in entries:
        result += struct.pack('<ffff', float(eid), float(img), float(txt), 0.0)

    # Sentinel: CS stops linear scan when it encounters id == 0
    result += struct.pack('<ffff', 0.0, 0.0, 0.0, 0.0)
    return bytes(result)


def build_element_flags_map(elements) -> dict:
    """
    Build the {element_id -> x111_flags} mapping for use in j2 templates.

    Returns a dict mapping each element's id to its x111 bitmask.
    All rzm.elements receive FLAG_IS_ELEMENT (0x04).
    Additionally:
        FLAG_USE_STATIC_IMG (0x01) if image_id > 0 and no conditional_images
        FLAG_USE_STATIC_TEXT (0x02) if text_id > 0 and no conditional_texts
    """
    flags_map = {}
    for elem in elements:
        eid = int(_get(elem, 'id', 0))
        flags = FLAG_IS_ELEMENT  # always set for rzm.elements

        img = _safe_id(_get(elem, 'image_id'))
        txt = _safe_id(_get(elem, 'text_id'))

        # Check conditional collections (Blender RNA or list)
        has_cond_images = bool(_get(elem, 'conditional_images'))
        has_cond_texts  = bool(_get(elem, 'conditional_texts'))
        # Also consider hover_image_id as a dynamic override
        hover_img = _safe_id(_get(elem, 'hover_image_id'))
        if hover_img > 0:
            has_cond_images = True  # hover overrides make imageID dynamic

        flags_map[str(eid)] = flags

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

    n = len(data) // 16 - 1  # subtract sentinel
    print(f"[ElementStaticMap] Written {len(data)} bytes ({n} entries) -> {path}")

    return build_element_flags_map(elements)


def _get(obj, attr, default=None):
    """Unified getter for both Blender RNA objects and dicts."""
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)
