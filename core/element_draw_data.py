"""Canonical packed draw data for RZMenu elements.

This module is the single Python-side place that translates raw Blender UI
properties into runtime IDs used by the GPU buffers. Raw element fields such as
``text_id`` are authoring data, not draw-buffer IDs.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, asdict
from pathlib import Path


FLAG_USE_STATIC_IMG = 0x01
FLAG_USE_STATIC_TEXT = 0x02
FLAG_IS_ELEMENT = 0x04
FLAG_USE_STATIC_COLOR = 0x08
FLAG_USE_DEFAULT_STYLE = 0x100
FLAG_USE_DEFAULT_FONT = 0x200
FLAG_USE_DEFAULT_ROT = 0x400

BL_COLOR = 0x001
BL_IMAGE_ID = 0x002
BL_TEXT_ID = 0x004

CLASS_ID_MAP = {
    "CONTAINER": 0,
    "GRID_CONTAINER": 1,
    "ANCHOR": 2,
    "BUTTON": 3,
    "SLIDER": 4,
    "TEXT": 5,
    "VECTOR_BOX": 6,
}


@dataclass(frozen=True)
class ElementDrawData:
    element_id: int
    parent_id: int
    preset_id: int
    underlayer_preset_id: int
    helper_id: int
    class_id: int
    image_slot: int
    text_slot: int
    text_length: int
    flags: int
    blacklist_mask: int
    has_color: float
    color: tuple[float, float, float, float]
    style_id_plus_one: int
    font_slot: int
    rotation: float
    raw_text: str


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


def _safe_color(value):
    if value is None:
        return (0.0, 0.0, 0.0, 0.5)
    try:
        if hasattr(value, "__iter__"):
            color = list(value)
            while len(color) < 4:
                color.append(0.0)
            return tuple(float(color[i]) for i in range(4))
    except Exception:
        pass
    return (0.0, 0.0, 0.0, 0.5)


def _collection_first_id(collection, attr):
    try:
        if collection and len(collection) > 0:
            return _safe_int(_get(collection[0], attr, -1), -1)
    except Exception:
        pass
    return -1


def _collection_has_items(collection):
    try:
        return bool(collection) and len(collection) > 0
    except Exception:
        return bool(collection)


def _class_id(elem):
    raw = _get(elem, "elem_class", "CONTAINER")
    if isinstance(raw, (list, tuple)) and raw:
        raw = raw[0]
    if isinstance(raw, int):
        return raw
    raw_s = str(raw)
    if raw_s.isdigit():
        return _safe_int(raw_s, 0)
    return CLASS_ID_MAP.get(raw_s, 0)


def _lookup_text(text_mapping, elem_id, host_id=-1):
    if not text_mapping:
        return 0, 0
    single = text_mapping.get("single", {})
    value = single.get((elem_id, host_id))
    if value is None:
        value = single.get(f"{elem_id}:{host_id}", [0, 0])
    try:
        return _safe_int(value[0], 0), _safe_int(value[1], 0)
    except Exception:
        return 0, 0


def _lookup_image(image_mapping, elem_id):
    if not image_mapping:
        return 0
    elements = image_mapping.get("elements", {})
    return max(0, _safe_int(elements.get(str(elem_id), 0), 0))


def build_element_draw_data(elements, text_mapping=None, image_mapping=None):
    """Return canonical per-element packed draw data.

    ``text_mapping`` must be the output of ``text_packer``. ``image_mapping``
    must be the output of ``image_packer``. When either mapping is missing this
    function falls back to zero for that packed slot instead of guessing from raw
    authoring fields.
    """
    rows = []
    for elem in elements:
        eid = _safe_int(_get(elem, "id", 0), 0)
        if eid <= 0:
            continue

        is_preset = bool(_get(elem, "is_preset"))
        is_helper = bool(_get(elem, "is_helper"))
        is_main = not is_preset and not is_helper

        raw_text = str(_get(elem, "text_id", "") or "")
        text_is_data = bool(_get(elem, "text_id_is_data"))
        cond_texts = _get(elem, "conditional_texts")
        has_cond_texts = _collection_has_items(cond_texts)
        text_slot, text_length = (0, 0)
        if raw_text and not text_is_data and not has_cond_texts:
            text_slot, text_length = _lookup_text(text_mapping, eid, -1)

        image_id = _safe_int(_get(elem, "image_id", -1), -1)
        hover_image_id = _safe_int(_get(elem, "hover_image_id", -1), -1)
        cond_images = _get(elem, "conditional_images")
        has_cond_images = _collection_has_items(cond_images)
        image_slot = 0
        if image_id >= 0 and not has_cond_images and hover_image_id < 0:
            image_slot = _lookup_image(image_mapping, eid)

        color_is_formula = bool(_get(elem, "color_is_formula"))
        color = _safe_color(_get(elem, "color"))
        has_color = 0.0 if color_is_formula else 1.0

        flags = 0
        if is_main:
            flags |= FLAG_IS_ELEMENT
            if image_slot > 0:
                flags |= FLAG_USE_STATIC_IMG
            if text_slot > 0:
                flags |= FLAG_USE_STATIC_TEXT
            if has_color > 0.5:
                flags |= FLAG_USE_STATIC_COLOR
            if _safe_int(_get(elem, "style_id", -1), -1) >= 0:
                flags |= FLAG_USE_DEFAULT_STYLE
            if _safe_int(_get(elem, "font_slot", 0), 0) > 0:
                flags |= FLAG_USE_DEFAULT_FONT
            rotation = _safe_float(_get(elem, "rotation", 0.0), 0.0)
            rotation_is_formula = bool(_get(elem, "rotation_is_formula"))
            transform_is_formula = bool(_get(elem, "transform_is_formula"))
            if abs(rotation) > 0.000001 and not rotation_is_formula and not transform_is_formula:
                flags |= FLAG_USE_DEFAULT_ROT

        blacklist = 0
        if is_main:
            if has_color > 0.5:
                blacklist |= BL_COLOR
            if image_slot > 0:
                blacklist |= BL_IMAGE_ID
            if text_slot > 0:
                blacklist |= BL_TEXT_ID

        rows.append(
            ElementDrawData(
                element_id=eid,
                parent_id=_safe_int(_get(elem, "parent_id", -1), -1),
                preset_id=_collection_first_id(_get(elem, "preset_ids"), "preset_id"),
                underlayer_preset_id=_collection_first_id(_get(elem, "underlayer_preset_ids"), "preset_id"),
                helper_id=_collection_first_id(_get(elem, "helper_ids"), "helper_id"),
                class_id=_class_id(elem),
                image_slot=image_slot,
                text_slot=text_slot,
                text_length=text_length,
                flags=flags,
                blacklist_mask=blacklist,
                has_color=has_color,
                color=color,
                style_id_plus_one=max(0, _safe_int(_get(elem, "style_id", -1), -1) + 1),
                font_slot=max(0, _safe_int(_get(elem, "font_slot", 0), 0)),
                rotation=_safe_float(_get(elem, "rotation", 0.0), 0.0),
                raw_text=raw_text,
            )
        )

    rows.sort(key=lambda item: item.element_id)
    return rows


def write_element_draw_debug(rows, output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump([asdict(row) for row in rows], handle, indent=2, sort_keys=True)


DRAW_DATA_RECORDS_PER_ELEMENT = 5


def write_element_draw_data_buffer(rows, output_path):
    """Write an expanded reserve buffer for the next GPU-side migration.

    Layout is dense direct-indexed by element_id:
      base = element_id * DRAW_DATA_RECORDS_PER_ELEMENT

      record 0: { element_id, parent_id, preset_id, underlayer_preset_id }
      record 1: { helper_id, class_id, image_slot, text_slot }
      record 2: { text_length, style_id_plus_one, font_slot, rotation }
      record 3: { flags, blacklist_mask, color_r, color_g }
      record 4: { color_b, color_a, has_color, 0 }
    """
    max_id = max((row.element_id for row in rows), default=0)
    records = [(0.0, 0.0, 0.0, 0.0)] * ((max_id + 1) * DRAW_DATA_RECORDS_PER_ELEMENT)
    for row in rows:
        base = row.element_id * DRAW_DATA_RECORDS_PER_ELEMENT
        records[base + 0] = (
            float(row.element_id),
            float(row.parent_id),
            float(row.preset_id),
            float(row.underlayer_preset_id),
        )
        records[base + 1] = (
            float(row.helper_id),
            float(row.class_id),
            float(row.image_slot),
            float(row.text_slot),
        )
        records[base + 2] = (
            float(row.text_length),
            float(row.style_id_plus_one),
            float(row.font_slot),
            float(row.rotation),
        )
        records[base + 3] = (
            float(row.flags),
            float(row.blacklist_mask),
            row.color[0],
            row.color[1],
        )
        records[base + 4] = (
            row.color[2],
            row.color[3],
            row.has_color,
            0.0,
        )

    result = bytearray()
    for record in records:
        result += struct.pack("<ffff", *record)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(result)


def export_element_draw_data(rows, res_dir):
    res_path = Path(res_dir)
    write_element_draw_data_buffer(rows, res_path / "element_draw_data.buf")
    write_element_draw_debug(rows, res_path / "element_draw_debug.json")
