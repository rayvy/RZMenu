"""
Element blacklist export.

The blacklist forces selected static values from ElementStaticMap back into the
draw instance after INI-side logic has run. It must follow the same canonical
packed draw data as ElementStaticMap.
"""

import struct
from pathlib import Path

from .element_draw_data import BL_COLOR, BL_IMAGE_ID, BL_TEXT_ID, build_element_draw_data

# Reserved for future draw slots.
BL_STYLE_ID = 0x008
BL_FN_TYPE = 0x010
BL_TEX_ID = 0x020
BL_DRAW_MODE = 0x040
BL_MIRROR = 0x080
BL_ROT = 0x100


def build_element_blacklist_map(elements, image_mapping=None, text_mapping=None, draw_data=None) -> dict:
    rows = draw_data or build_element_draw_data(elements, text_mapping, image_mapping)
    return {row.element_id: row.blacklist_mask for row in rows}


def build_element_blacklist(elements, image_mapping=None, text_mapping=None, draw_data=None) -> bytes:
    rows = draw_data or build_element_draw_data(elements, text_mapping, image_mapping)

    result = bytearray()
    for row in rows:
        if row.blacklist_mask:
            result += struct.pack("<IIII", row.element_id, row.blacklist_mask, 0, 0)

    result += struct.pack("<IIII", 0, 0, 0, 0)
    return bytes(result)


def export_element_blacklist(
    elements,
    output_path: str,
    image_mapping=None,
    text_mapping=None,
    draw_data=None,
) -> dict:
    rows = draw_data or build_element_draw_data(elements, text_mapping, image_mapping)
    data = build_element_blacklist(elements, image_mapping, text_mapping, rows)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    n = len(data) // 16 - 1
    print(f"[ElementBlackList v2] Written {len(data)} bytes ({n} entries) -> {path}")

    return build_element_blacklist_map(elements, image_mapping, text_mapping, rows)
