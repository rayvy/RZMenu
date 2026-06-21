"""
ElementStaticMap export.

This compatibility buffer is still 2x float4 per element because
draw_controller.hlsl consumes that layout today. Values written here must be
runtime-packed IDs, not raw authoring fields from Blender.
"""

import struct
from pathlib import Path

from .element_draw_data import (
    FLAG_IS_ELEMENT,
    FLAG_USE_STATIC_COLOR,
    FLAG_USE_STATIC_IMG,
    FLAG_USE_STATIC_TEXT,
    build_element_draw_data,
)


def build_element_static_map(elements, image_mapping=None, text_mapping=None, draw_data=None) -> bytes:
    """
    Build the binary ElementStaticMap buffer.

    Current layout:
      float4 A: { element_id, packed_image_slot, packed_text_slot, has_color }
      float4 B: { color_r, color_g, color_b, color_a }
    """
    rows = draw_data or build_element_draw_data(elements, text_mapping, image_mapping)

    result = bytearray()
    for row in rows:
        r, g, b, a = row.color
        result += struct.pack(
            "<ffff",
            float(row.element_id),
            float(row.image_slot),
            float(row.text_slot),
            float(row.has_color),
        )
        result += struct.pack("<ffff", r, g, b, a)

    result += struct.pack("<ffff", 0.0, 0.0, 0.0, 0.0)
    result += struct.pack("<ffff", 0.0, 0.0, 0.0, 0.0)
    return bytes(result)


def build_element_flags_map(elements, image_mapping=None, text_mapping=None, draw_data=None) -> dict:
    """Return {element_id: x111_flags} using packed draw data."""
    rows = draw_data or build_element_draw_data(elements, text_mapping, image_mapping)
    return {str(row.element_id): row.flags for row in rows}


def export_element_static_map(
    elements,
    output_path: str,
    image_mapping=None,
    text_mapping=None,
    draw_data=None,
) -> dict:
    """
    Write element_static_map.buf and return flags for Jinja.

    ``text_mapping`` should come from text_packer and ``image_mapping`` from
    image_packer. This function intentionally does not infer packed IDs from raw
    element.image_id / element.text_id.
    """
    rows = draw_data or build_element_draw_data(elements, text_mapping, image_mapping)
    data = build_element_static_map(elements, image_mapping, text_mapping, rows)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    n = len(data) // 32 - 1
    print(f"[ElementStaticMap v3] Written {len(data)} bytes ({n} entries) -> {path}")

    return build_element_flags_map(elements, image_mapping, text_mapping, rows)
