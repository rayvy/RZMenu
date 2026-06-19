import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.element_default_props import (  # noqa: E402
    FLAG_USE_DEFAULT_FONT,
    FLAG_USE_DEFAULT_ROT,
    FLAG_USE_DEFAULT_STYLE,
    build_element_default_flags,
    build_element_default_props,
)


def unpack_float4s(data):
    return [
        struct.unpack_from('<ffff', data, offset)
        for offset in range(0, len(data), 16)
    ]


def test_buffer_layout_and_sorting():
    elements = [
        {'id': 20, 'style_id': 2, 'font_slot': 1, 'rotation': 0.25},
        {'id': 10, 'style_id': -1, 'font_slot': 0, 'rotation': 0.0},
    ]

    records = unpack_float4s(build_element_default_props(elements))

    assert records[0] == (10.0, 0.0, 0.0, 0.0)
    assert records[1] == (0.0, 0.0, 0.0, 0.0)
    assert records[2] == (20.0, 3.0, 1.0, 0.25)
    assert records[3] == (0.0, 0.0, 0.0, 0.0)
    assert records[-2] == (0.0, 0.0, 0.0, 0.0)
    assert records[-1] == (0.0, 0.0, 0.0, 0.0)


def test_default_flags_are_granular():
    elements = [
        {'id': 1, 'style_id': 0, 'font_slot': 2, 'rotation': 0.5},
        {'id': 2, 'style_id': -1, 'font_slot': 0, 'rotation': 0.5, 'rotation_is_formula': True},
        {'id': 3, 'style_id': 1, 'font_slot': 0, 'rotation': 0.25, 'transform_is_formula': True},
        {'id': 4, 'style_id': 1, 'is_preset': True},
    ]

    flags = build_element_default_flags(elements)

    assert flags['1'] == (FLAG_USE_DEFAULT_STYLE | FLAG_USE_DEFAULT_FONT | FLAG_USE_DEFAULT_ROT)
    assert flags['2'] == 0
    assert flags['3'] == FLAG_USE_DEFAULT_STYLE
    assert flags['4'] == 0


if __name__ == '__main__':
    test_buffer_layout_and_sorting()
    test_default_flags_are_granular()
    print('[PASS] element_default_props')
