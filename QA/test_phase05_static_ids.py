# QA/test_phase05_static_ids.py
# Tests for Phase 0.5: Static ImageID/TextID Buffer
# Run: python QA/test_phase05_static_ids.py

import json, struct
from pathlib import Path

SCENE_PATH = Path(__file__).parent / "test_scene.json"

FLAG_STATIC_IMAGE = 0x01
FLAG_STATIC_TEXT  = 0x02


# ─────────────────────────────────────────────────────────────────────────────
# Reuse topo sort from phase 0 tests
# ─────────────────────────────────────────────────────────────────────────────

def topo_sort_elements(elements):
    id_to_elem = {e['id']: e for e in elements}
    visited, result = set(), []
    def visit(eid):
        stack, in_stack = [eid], set()
        while stack:
            curr = stack[-1]
            if curr in visited: stack.pop(); continue
            e = id_to_elem.get(curr)
            if e is None: stack.pop(); continue
            pid = e['parent_id']
            if pid >= 0 and pid not in visited and pid not in in_stack:
                in_stack.add(pid); stack.append(pid)
            else:
                stack.pop(); in_stack.discard(curr)
                if curr not in visited:
                    visited.add(curr); result.append(e)
    for e in elements: visit(e['id'])
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Core logic (mirrors core/static_id_exporter.py)
# ─────────────────────────────────────────────────────────────────────────────

def _safe_id(val):
    """Convert image_id/text_id to int safely (can be None, str, or int in JSON)."""
    if val is None: return -1
    try: v = int(val); return v if v >= 0 else -1
    except (TypeError, ValueError): return -1

def build_static_id_map(elements, topo_order=None):
    ordered = topo_order if topo_order else elements
    result = bytearray()
    for elem in ordered:
        img_val = max(0, _safe_id(elem.get('image_id')))
        txt_val = max(0, _safe_id(elem.get('text_id')))
        if _safe_id(elem.get('image_id')) < 0: img_val = 0
        if _safe_id(elem.get('text_id'))  < 0: txt_val = 0
        result += struct.pack('<HH', img_val, txt_val)
    return bytes(result)


def build_id_flags_map(elements, topo_order=None):
    ordered = topo_order if topo_order else elements
    flags_map = {}
    for elem in ordered:
        flags = 0
        img = _safe_id(elem.get('image_id'))
        txt = _safe_id(elem.get('text_id'))
        has_cond_images = bool(elem.get('conditional_images'))
        has_cond_texts  = bool(elem.get('conditional_texts'))
        if img >= 0 and not has_cond_images:
            flags |= FLAG_STATIC_IMAGE
        if txt >= 0 and not has_cond_texts:
            flags |= FLAG_STATIC_TEXT
        flags_map[elem['id']] = flags
    return flags_map


def simulate_controller(ini_image_id, static_image_id, flags):
    """
    Python simulation of the draw_controller.hlsl resolution logic.
    Returns the final imageID that would be written to DataBuffer slot 3.
    """
    tile_x = ini_image_id
    if flags & FLAG_STATIC_IMAGE:
        if static_image_id > 0:
            tile_x = float(static_image_id)
        if ini_image_id > 0.5:
            tile_x = ini_image_id   # conditional INI override wins
    return tile_x


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def load_scene():
    with open(SCENE_PATH, encoding='utf-8') as f:
        return json.load(f)['elements']


def test_buf_size_correct():
    """Buffer must be exactly 4 bytes per element."""
    elems = load_scene()
    topo  = topo_sort_elements(elems)
    data  = build_static_id_map(elems, topo)
    expected = len(topo) * 4
    assert len(data) == expected, f"Expected {expected} bytes, got {len(data)}"
    print(f"[PASS] buf_size_correct: {len(data)} bytes for {len(topo)} elements")


def test_image_id_roundtrip():
    """Every element's imageID must be recoverable from the buffer."""
    elems = load_scene()
    topo  = topo_sort_elements(elems)
    data  = build_static_id_map(elems, topo)

    mismatches = []
    for i, elem in enumerate(topo):
        img_id, _ = struct.unpack_from('<HH', data, i * 4)
        raw = _safe_id(elem.get('image_id'))
        expected = max(0, raw) if raw >= 0 else 0
        if img_id != expected:
            mismatches.append(
                f"  elem {elem['id']} ({elem['element_name']}): "
                f"got {img_id}, expected {expected}"
            )
    assert not mismatches, "imageID mismatches:\n" + "\n".join(mismatches)
    print(f"[PASS] image_id_roundtrip: all {len(topo)} elements verified")


def test_text_id_roundtrip():
    """Every element's textID must be recoverable from the buffer."""
    elems = load_scene()
    topo  = topo_sort_elements(elems)
    data  = build_static_id_map(elems, topo)

    mismatches = []
    for i, elem in enumerate(topo):
        _, txt_id = struct.unpack_from('<HH', data, i * 4)
        raw = _safe_id(elem.get('text_id'))
        expected = max(0, raw) if raw >= 0 else 0
        if txt_id != expected:
            mismatches.append(f"  elem {elem['id']}: got {txt_id}, expected {expected}")
    assert not mismatches, "textID mismatches:\n" + "\n".join(mismatches)
    print(f"[PASS] text_id_roundtrip: all {len(topo)} elements verified")


def test_uint16_range():
    """All imageID and textID values must fit in uint16 (< 65536)."""
    elems = load_scene()
    overflow = []
    for e in elems:
        img = _safe_id(e.get('image_id'))
        txt = _safe_id(e.get('text_id'))
        if img >= 65536:
            overflow.append(f"  id={e['id']} imageID={img} > 65535")
        if txt >= 65536:
            overflow.append(f"  id={e['id']} textID={txt} > 65535")
    assert not overflow, "uint16 overflow:\n" + "\n".join(overflow)
    print("[PASS] uint16_range: all IDs fit in uint16")


def test_conditional_elements_not_static():
    """Elements with conditional_images must NOT have FLAG_STATIC_IMAGE."""
    elems  = load_scene()
    topo   = topo_sort_elements(elems)
    flags  = build_id_flags_map(elems, topo)
    cond_with_static = []
    for elem in elems:
        if elem.get('conditional_images') and (flags[elem['id']] & FLAG_STATIC_IMAGE):
            cond_with_static.append(f"  id={elem['id']} {elem['element_name']}")
    assert not cond_with_static, \
        "Conditional image elements should not be static:\n" + "\n".join(cond_with_static)
    print("[PASS] conditional_elements_not_static")


def test_controller_static_wins():
    """Shader sim: INI x102=0 (commented), FLAG set -> static buffer wins."""
    result = simulate_controller(
        ini_image_id=0.0,       # $imageID закомментировано
        static_image_id=47,     # из static_id_map.buf
        flags=FLAG_STATIC_IMAGE
    )
    assert abs(result - 47.0) < 0.001, f"Expected 47, got {result}"
    print("[PASS] controller_static_wins: static buffer fills missing imageID")


def test_controller_conditional_override():
    """Shader sim: INI x102=46 (conditional set), FLAG set -> INI wins."""
    result = simulate_controller(
        ini_image_id=46.0,      # условие установило другой image
        static_image_id=47,     # дефолт из буфера
        flags=FLAG_STATIC_IMAGE
    )
    assert abs(result - 46.0) < 0.001, f"Expected 46 (INI override), got {result}"
    print("[PASS] controller_conditional_override: conditional INI wins over buffer")


def test_controller_no_flag():
    """Shader sim: FLAG not set -> INI value used as-is (legacy mode)."""
    result = simulate_controller(
        ini_image_id=33.0,
        static_image_id=99,     # должен быть проигнорирован
        flags=0                 # нет флага
    )
    assert abs(result - 33.0) < 0.001, f"Expected 33 (INI), got {result}"
    print("[PASS] controller_no_flag: without flag, INI value used (legacy mode)")


def test_ini_reduction_estimate():
    """Count how many $imageID/$TextID lines become static (removable)."""
    elems = load_scene()
    topo  = topo_sort_elements(elems)
    flags = build_id_flags_map(elems, topo)

    static_img = sum(1 for e in elems if flags[e['id']] & FLAG_STATIC_IMAGE)
    static_txt = sum(1 for e in elems if flags[e['id']] & FLAG_STATIC_TEXT)
    cond_img   = sum(1 for e in elems if e.get('conditional_images'))
    cond_txt   = sum(1 for e in elems if e.get('conditional_texts'))
    total = len(elems)

    print(f"[INFO] imageID breakdown:")
    print(f"  Static (removable from INI): {static_img} ({100*static_img//total}%)")
    print(f"  Conditional (stay in INI):   {cond_img}   ({100*cond_img//total}%)")
    print(f"  No imageID:                  {total-static_img-cond_img}")
    print(f"[INFO] textID breakdown:")
    print(f"  Static (removable):          {static_txt} ({100*static_txt//total}%)")
    print(f"  Conditional (stay):          {cond_txt}   ({100*cond_txt//total}%)")
    print(f"  No textID:                   {total-static_txt-cond_txt}")

    # Sanity: at least some elements should be static
    assert static_img + static_txt > 0, "No static IDs found - check scene data"
    print(f"[PASS] ini_reduction_estimate: {static_img+static_txt} lines removable")


def test_di_count_to_elem_mapping_stable():
    """
    Critical: the di_count order used when writing static_id_map.buf
    MUST match the di_count order during INI execution.
    Both must use the same topo-sorted traversal.
    Verify that topo sort is deterministic (same result on 2 runs).
    """
    elems = load_scene()
    order_a = [e['id'] for e in topo_sort_elements(elems)]
    order_b = [e['id'] for e in topo_sort_elements(elems)]
    assert order_a == order_b, "Topo sort is not deterministic!"
    print(f"[PASS] di_count_mapping_stable: topo sort is deterministic ({len(order_a)} elements)")


TESTS = [
    test_buf_size_correct,
    test_image_id_roundtrip,
    test_text_id_roundtrip,
    test_uint16_range,
    test_conditional_elements_not_static,
    test_controller_static_wins,
    test_controller_conditional_override,
    test_controller_no_flag,
    test_ini_reduction_estimate,
    test_di_count_to_elem_mapping_stable,
]

if __name__ == "__main__":
    passed = failed = 0
    for fn in TESTS:
        print(f"\n--- {fn.__name__} ---")
        try:
            fn(); passed += 1
        except Exception as ex:
            print(f"[FAIL] {ex}")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed / {len(TESTS)} total")
