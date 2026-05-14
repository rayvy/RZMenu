"""
element_blacklist.py
Phase 0.5.5: BlackList Buffer

Generates res/element_blacklist.buf — a compact sorted array of
(element_id, blacklist_mask) for all rzm.elements.

The CS (draw_controller.hlsl) uses this buffer to FORCE static values
from ElementStaticMap onto DataBuffer slots, regardless of what INI wrote.

This is the GPU-side evolution of the $rayvich_back_values_* pattern:
instead of INI restoring a value after a risky operation, CS always
writes the correct static value directly, guaranteeing no bleed-through
between elements.

Format: compact sorted array of uint4 entries:
    uint4{ uint(id), uint(mask), 0, 0 }
Entries sorted ascending by id. Terminated by sentinel {0, 0, 0, 0}.

Bitmask constants (mirror draw_controller.hlsl BL_* defines):
    BL_COLOR     = 0x001  -> Slot 2 (RGBA) forced from StaticMap
    BL_IMAGE_ID  = 0x002  -> Slot 3.x (imageID) forced from StaticMap
    BL_TEXT_ID   = 0x004  -> Slot 3.x (textID)  forced from StaticMap
    BL_STYLE_ID  = 0x008  -> Slot 6.y (style_id) — reserved for Phase 0.6
    BL_FN_TYPE   = 0x010  -> Slot 6.x (fn_type)  — reserved for Phase 0.6
    BL_TEX_ID    = 0x020  -> Slot 6.z (tex_id)   — reserved for Phase 0.6
    BL_DRAW_MODE = 0x040  -> Slot 6.w (draw_mode) — reserved for Phase 0.6
    BL_MIRROR    = 0x080  -> Slot 4.xy (mirror+font) — reserved for Phase 0.6
    BL_ROT       = 0x100  -> Slot 4.w (rotation)  — reserved for Phase 0.6
"""

import struct
from pathlib import Path


# ─── BlackList bit constants (mirrors draw_controller.hlsl) ──────────────────

BL_COLOR     = 0x001   # Phase 0.5.5: RGBA from StaticMap
BL_IMAGE_ID  = 0x002   # Phase 0.5.5: imageID from StaticMap
BL_TEXT_ID   = 0x004   # Phase 0.5.5: textID from StaticMap
# Reserved for Phase 0.6:
BL_STYLE_ID  = 0x008
BL_FN_TYPE   = 0x010
BL_TEX_ID    = 0x020
BL_DRAW_MODE = 0x040
BL_MIRROR    = 0x080
BL_ROT       = 0x100


def _get(obj, attr, default=None):
    """Unified getter for both Blender RNA objects and dicts."""
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _safe_id(val):
    if val is None:
        return -1
    try:
        v = int(val)
        return v if v >= 0 else -1
    except (TypeError, ValueError):
        return -1


def build_element_blacklist_map(elements) -> dict:
    """
    Returns {element_id (int): blacklist_mask (int)} for Python use.
    Presets and helpers get mask=0 (no blacklist, they manage their own data).
    """
    bl_map = {}
    for elem in elements:
        eid       = int(_get(elem, 'id', 0))
        is_preset = bool(_get(elem, 'is_preset'))
        is_helper = bool(_get(elem, 'is_helper'))

        if is_preset or is_helper:
            bl_map[eid] = 0
            continue

        mask = 0

        # COLOR: blacklist if not a formula — static color must not be overwritten
        # by residual $colorR/G/B/A from a previous element's CommandList
        color_is_formula = bool(_get(elem, 'color_is_formula'))
        if not color_is_formula:
            mask |= BL_COLOR

        # IMAGE_ID: blacklist if static (no conditional/hover overrides)
        img = _safe_id(_get(elem, 'image_id'))
        hover_img = _safe_id(_get(elem, 'hover_image_id'))
        cond_imgs = _get(elem, 'conditional_images')
        if img > 0 and not cond_imgs and hover_img <= 0:
            mask |= BL_IMAGE_ID

        # TEXT_ID: blacklist if static (no conditional texts)
        txt = _safe_id(_get(elem, 'text_id'))
        cond_txts = _get(elem, 'conditional_texts')
        if txt > 0 and not cond_txts:
            mask |= BL_TEXT_ID

        # Phase 0.6 slots (style_id, fn_type, etc.) will be added here later.
        # BL_STYLE_ID, BL_FN_TYPE, BL_TEX_ID, BL_DRAW_MODE, BL_MIRROR, BL_ROT

        bl_map[eid] = mask

    return bl_map


def build_element_blacklist(elements) -> bytes:
    """
    Build the binary ElementBlackList buffer.

    Format: compact sorted array of uint4:
        uint4{ uint(id), uint(mask), 0, 0 }
    Sorted ascending by id.
    Terminated by sentinel {0, 0, 0, 0}.
    """
    bl_map = build_element_blacklist_map(elements)

    # Include only elements with a non-zero mask (saves space)
    entries = [(eid, mask) for eid, mask in bl_map.items() if mask != 0]
    entries.sort(key=lambda e: e[0])

    result = bytearray()
    for eid, mask in entries:
        result += struct.pack('<IIII', eid, mask, 0, 0)

    # Sentinel
    result += struct.pack('<IIII', 0, 0, 0, 0)
    return bytes(result)


def export_element_blacklist(elements, output_path: str) -> dict:
    """
    Write element_blacklist.buf to disk and return the blacklist map.

    Args:
        elements: iterable of element objects
        output_path: full path to output file (e.g. 'path/to/res/element_blacklist.buf')

    Returns:
        dict {element_id (int): blacklist_mask (int)}
    """
    data = build_element_blacklist(elements)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    n = len(data) // 16 - 1  # 16 bytes per uint4, subtract sentinel
    print(f"[ElementBlackList] Written {len(data)} bytes ({n} entries) -> {path}")

    return build_element_blacklist_map(elements)
