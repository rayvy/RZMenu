"""
element_default_props.py
Phase 0.6: default visual property buffer.

Generates res/element_default_props.buf as a compact sorted array of
static visual defaults that are safe to restore in draw_controller.hlsl
when the INI side intentionally leaves the matching register at zero.

Format:
  2x float4 per entry:
    float4 A: { float(id), float(style_id_plus_one), float(font_slot), float(rotation) }
    float4 B: { 0, 0, 0, 0 }  # reserved for future defaults
  Sentinel:
    two zero float4 records.
"""

import struct
from pathlib import Path


FLAG_USE_DEFAULT_STYLE = 0x100
FLAG_USE_DEFAULT_FONT = 0x200
FLAG_USE_DEFAULT_ROT = 0x400


def _get(obj, attr, default=None):
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_preset_or_helper(elem):
    return bool(_get(elem, 'is_preset')) or bool(_get(elem, 'is_helper'))


def build_element_default_props(elements) -> bytes:
    """
    Build ElementDefaultProps as bytes.

    Entries are sorted by element id so the shader can binary-search them.
    """
    entries = []
    for elem in elements:
        eid = _safe_int(_get(elem, 'id', 0))
        if eid <= 0:
            continue

        style_id = _safe_int(_get(elem, 'style_id', -1), -1) + 1
        font_slot = _safe_int(_get(elem, 'font_slot', 0), 0)
        rotation = _safe_float(_get(elem, 'rotation', 0.0), 0.0)

        entries.append((eid, style_id, font_slot, rotation))

    entries.sort(key=lambda e: e[0])

    result = bytearray()
    for eid, style_id, font_slot, rotation in entries:
        result += struct.pack(
            '<ffff',
            float(eid),
            float(max(0, style_id)),
            float(max(0, font_slot)),
            float(rotation),
        )
        result += struct.pack('<ffff', 0.0, 0.0, 0.0, 0.0)

    result += struct.pack('<ffff', 0.0, 0.0, 0.0, 0.0)
    result += struct.pack('<ffff', 0.0, 0.0, 0.0, 0.0)
    return bytes(result)


def build_element_default_flags(elements) -> dict:
    """
    Return {element_id: flag_bits} for defaults safe to source from the buffer.

    Presets/helpers are excluded: their visual calls are often host-routed and
    should stay explicit until the preset/helper instancer migration lands.
    """
    flags_map = {}
    for elem in elements:
        eid = _safe_int(_get(elem, 'id', 0))
        if eid <= 0:
            continue

        if _is_preset_or_helper(elem):
            flags_map[str(eid)] = 0
            continue

        flags = 0

        if _safe_int(_get(elem, 'style_id', -1), -1) >= 0:
            flags |= FLAG_USE_DEFAULT_STYLE

        if _safe_int(_get(elem, 'font_slot', 0), 0) > 0:
            flags |= FLAG_USE_DEFAULT_FONT

        rotation = _safe_float(_get(elem, 'rotation', 0.0), 0.0)
        rotation_is_formula = bool(_get(elem, 'rotation_is_formula'))
        transform_is_formula = bool(_get(elem, 'transform_is_formula'))
        if abs(rotation) > 0.000001 and not rotation_is_formula and not transform_is_formula:
            flags |= FLAG_USE_DEFAULT_ROT

        flags_map[str(eid)] = flags

    return flags_map


def export_element_default_props(elements, output_path: str) -> dict:
    data = build_element_default_props(elements)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    n = len(data) // 32 - 1
    print(f"[ElementDefaultProps] Written {len(data)} bytes ({n} entries) -> {path}")

    return build_element_default_flags(elements)
