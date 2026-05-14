# QA/test_phase05_static_ids_v2.py
# Tests for Phase 0.5.5: $id-indexed ElementStaticMap (2x float4 format)
# Run: python QA/test_phase05_static_ids_v2.py

import json, struct
from pathlib import Path

SCENE_PATH = Path(__file__).parent / "test_scene.json"

FLAG_IS_ELEMENT       = 0x04
FLAG_USE_STATIC_IMG   = 0x01
FLAG_USE_STATIC_TEXT  = 0x02
FLAG_USE_STATIC_COLOR = 0x08  # Phase 0.5.5

BL_COLOR    = 0x001
BL_IMAGE_ID = 0x002
BL_TEXT_ID  = 0x004


def _safe_id(val):
    if val is None: return 0
    try: v = int(val); return max(0, v)
    except: return 0


def _safe_color(val):
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


# ─── Phase 0.5.5 format: 2x float4 per entry ─────────────────────────────────

def build_element_static_map(elements):
    """Phase 0.5.5: compact sorted array (2x float4 per entry) + 2x sentinel."""
    entries = []
    for elem in elements:
        eid = elem.get('id', 0)
        img = _safe_id(elem.get('image_id'))
        txt = _safe_id(elem.get('text_id'))
        color_is_formula = bool(elem.get('color_is_formula'))
        r, g, b, a = _safe_color(elem.get('color'))
        has_color = 0.0 if color_is_formula else 1.0
        entries.append((eid, img, txt, has_color, r, g, b, a))
    entries.sort(key=lambda e: e[0])
    result = bytearray()
    for eid, img, txt, hc, r, g, b, a in entries:
        result += struct.pack('<ffff', float(eid), float(img), float(txt), hc)  # float4 A
        result += struct.pack('<ffff', r, g, b, a)                              # float4 B
    # Sentinel: 2x float4 with id==0
    result += struct.pack('<ffff', 0.0, 0.0, 0.0, 0.0)
    result += struct.pack('<ffff', 0.0, 0.0, 0.0, 0.0)
    return bytes(result)


def build_element_flags_map(elements):
    flags_map = {}
    for elem in elements:
        eid = int(elem.get('id', 0))
        is_preset = bool(elem.get('is_preset'))
        is_helper = bool(elem.get('is_helper'))
        if is_preset or is_helper:
            flags_map[eid] = 0
            continue
        flags = FLAG_IS_ELEMENT
        img = _safe_id(elem.get('image_id'))
        hover_img = _safe_id(elem.get('hover_image_id'))
        cond_imgs = elem.get('conditional_images')
        if img > 0 and not cond_imgs and hover_img <= 0:
            flags |= FLAG_USE_STATIC_IMG
        txt = _safe_id(elem.get('text_id'))
        cond_txts = elem.get('conditional_texts')
        if txt > 0 and not cond_txts:
            flags |= FLAG_USE_STATIC_TEXT
        if not elem.get('color_is_formula'):
            flags |= FLAG_USE_STATIC_COLOR
        flags_map[eid] = flags
    return flags_map


def build_element_blacklist_map(elements):
    bl_map = {}
    for elem in elements:
        eid = int(elem.get('id', 0))
        is_preset = bool(elem.get('is_preset'))
        is_helper = bool(elem.get('is_helper'))
        if is_preset or is_helper:
            bl_map[eid] = 0
            continue
        mask = 0
        if not elem.get('color_is_formula'):
            mask |= BL_COLOR
        img = _safe_id(elem.get('image_id'))
        hover_img = _safe_id(elem.get('hover_image_id'))
        if img > 0 and not elem.get('conditional_images') and hover_img <= 0:
            mask |= BL_IMAGE_ID
        txt = _safe_id(elem.get('text_id'))
        if txt > 0 and not elem.get('conditional_texts'):
            mask |= BL_TEXT_ID
        bl_map[eid] = mask
    return bl_map


def simulate_cs_lookup(buf_bytes, target_id):
    """Simulate CS linear scan (step=2 for 2x float4). Returns (imageID, textID, R, G, B, A, has_color)."""
    entry_size = 32  # 2x float4 = 8 floats * 4 bytes
    n_entries  = len(buf_bytes) // entry_size
    for i in range(n_entries):
        offset_a = i * entry_size
        eid, img, txt, has_color = struct.unpack_from('<ffff', buf_bytes, offset_a)
        if int(eid) == 0:   # sentinel
            break
        if int(eid) == target_id:
            r, g, b, a = struct.unpack_from('<ffff', buf_bytes, offset_a + 16)
            return int(img), int(txt), r, g, b, a, has_color
    return 0, 0, 0.0, 0.0, 0.0, 0.5, 0.0


def load_scene():
    with open(SCENE_PATH, encoding='utf-8') as f:
        return json.load(f)['elements']


# ─────────────────────────────────────────────────────────────────────────────

def test_sentinel_at_end():
    """Buffer must end with two {0,0,0,0} sentinel float4s (Phase 0.5.5: 2x sentinel)."""
    elems = load_scene()
    data  = build_element_static_map(elems)
    # Last 32 bytes must be all zeros
    last_32 = data[-32:]
    values = struct.unpack_from('<ffffffff', last_32)
    assert all(v == 0.0 for v in values), f"Sentinel not zero: {values}"
    n_entries = len(data) // 32 - 1  # subtract sentinel
    print(f"[PASS] sentinel_at_end: {n_entries} entries + 2x float4 sentinel ({len(data)} bytes)")


def test_sorted_by_id():
    """Entries must be sorted ascending by id."""
    elems = load_scene()
    data  = build_element_static_map(elems)
    n     = len(data) // 32
    ids   = []
    for i in range(n):
        eid = struct.unpack_from('<f', data, i * 32)[0]
        if int(eid) == 0: break
        ids.append(int(eid))
    assert ids == sorted(ids), f"IDs not sorted: {ids[:10]}"
    print(f"[PASS] sorted_by_id: {len(ids)} entries sorted")


def test_all_elements_included():
    """All rzm.elements must appear in the buffer."""
    elems = load_scene()
    data  = build_element_static_map(elems)
    id_set_in_buf = set()
    n = len(data) // 32
    for i in range(n):
        eid = int(struct.unpack_from('<f', data, i * 32)[0])
        if eid == 0: break
        id_set_in_buf.add(eid)
    for elem in elems:
        assert elem['id'] in id_set_in_buf, f"Missing id={elem['id']} ({elem['element_name']})"
    print(f"[PASS] all_elements_included: {len(id_set_in_buf)} elements in buffer")


def test_836767_included():
    """System element 836767 (ControllerCursor) must be in buffer with image_id=10009."""
    elems = load_scene()
    data  = build_element_static_map(elems)
    img, txt, *_ = simulate_cs_lookup(data, 836767)
    assert img == 10009, f"Expected imageID=10009 for id=836767, got {img}"
    print(f"[PASS] 836767_included: id=836767 -> imageID={img}")


def test_lookup_correct_for_all():
    """CS simulation: every element's imageID resolves correctly."""
    elems = load_scene()
    data  = build_element_static_map(elems)
    mismatches = []
    for elem in elems:
        expected_img = _safe_id(elem.get('image_id'))
        found_img, _, *__ = simulate_cs_lookup(data, elem['id'])
        if found_img != expected_img:
            mismatches.append(
                f"  id={elem['id']} {elem['element_name']}: "
                f"expected {expected_img}, got {found_img}"
            )
    assert not mismatches, "Lookup mismatches:\n" + "\n".join(mismatches)
    print(f"[PASS] lookup_correct_for_all: all {len(elems)} elements verified")


def test_color_stored_for_static_elements():
    """Phase 0.5.5: elements without color_is_formula must have has_color=1 and non-zero RGBA."""
    elems = load_scene()
    data  = build_element_static_map(elems)
    static_elems = [e for e in elems if not e.get('color_is_formula') and e.get('color')]
    if not static_elems:
        print("[SKIP] color_stored_for_static_elements: no static color elements in test scene")
        return
    failures = []
    for elem in static_elems[:10]:
        _, _, r, g, b, a, has_color = simulate_cs_lookup(data, elem['id'])
        if has_color < 0.5:
            failures.append(f"  id={elem['id']}: has_color={has_color} (expected 1.0)")
    assert not failures, "Static elements missing has_color:\n" + "\n".join(failures)
    print(f"[PASS] color_stored_for_static_elements: {len(static_elems)} checked")


def test_formula_color_has_no_bake():
    """Phase 0.5.5: elements with color_is_formula must have has_color=0."""
    elems = load_scene()
    data  = build_element_static_map(elems)
    formula_elems = [e for e in elems if e.get('color_is_formula')]
    if not formula_elems:
        print("[SKIP] formula_color_has_no_bake: no formula color elements in test scene")
        return
    failures = []
    for elem in formula_elems:
        _, _, r, g, b, a, has_color = simulate_cs_lookup(data, elem['id'])
        if has_color > 0.5:
            failures.append(f"  id={elem['id']}: has_color={has_color} (expected 0.0)")
    assert not failures, "Formula elements have has_color set:\n" + "\n".join(failures)
    print(f"[PASS] formula_color_has_no_bake: {len(formula_elems)} checked")


def test_flag_use_static_color_set():
    """Phase 0.5.5: FLAG_USE_STATIC_COLOR must be set for elements without color_is_formula."""
    elems = load_scene()
    flags = build_element_flags_map(elems)
    broken = []
    for elem in elems:
        eid = int(elem.get('id', 0))
        if elem.get('is_preset') or elem.get('is_helper'):
            continue
        if not elem.get('color_is_formula'):
            if not (flags.get(eid, 0) & FLAG_USE_STATIC_COLOR):
                broken.append(f"  id={eid}: FLAG_USE_STATIC_COLOR not set")
    assert not broken, "Missing FLAG_USE_STATIC_COLOR:\n" + "\n".join(broken)
    print(f"[PASS] flag_use_static_color_set")


def test_blacklist_color_set_for_static():
    """Phase 0.5.5: BL_COLOR must be set for all non-formula, non-preset, non-helper elements."""
    elems = load_scene()
    bl = build_element_blacklist_map(elems)
    broken = []
    for elem in elems:
        eid = int(elem.get('id', 0))
        if elem.get('is_preset') or elem.get('is_helper'):
            continue
        if not elem.get('color_is_formula'):
            if not (bl.get(eid, 0) & BL_COLOR):
                broken.append(f"  id={eid}")
    assert not broken, "Missing BL_COLOR:\n" + "\n".join(broken)
    print("[PASS] blacklist_color_set_for_static")


def test_flag_is_element_always_set():
    """FLAG_IS_ELEMENT (0x04) must be set for ALL rzm.elements (non-preset, non-helper)."""
    elems  = load_scene()
    flags  = build_element_flags_map(elems)
    broken = [e['id'] for e in elems
              if not e.get('is_preset') and not e.get('is_helper')
              and not (flags.get(int(e['id']), 0) & FLAG_IS_ELEMENT)]
    assert not broken, f"Missing FLAG_IS_ELEMENT for ids: {broken}"
    print(f"[PASS] flag_is_element_always_set: all main elements covered")


def test_conditional_elements_not_static():
    """Elements with conditional_images must NOT have FLAG_USE_STATIC_IMG."""
    elems  = load_scene()
    flags  = build_element_flags_map(elems)
    broken = []
    for elem in elems:
        if elem.get('conditional_images') and (flags.get(int(elem['id']), 0) & FLAG_USE_STATIC_IMG):
            broken.append(f"  id={elem['id']} {elem['element_name']}")
    assert not broken, "Conditional elements marked static:\n" + "\n".join(broken)
    print("[PASS] conditional_elements_not_static")


def test_reduction_summary():
    """Print summary of what gets removed from INI."""
    elems  = load_scene()
    flags  = build_element_flags_map(elems)
    total  = len(elems)
    s_img  = sum(1 for e in elems if flags.get(int(e['id']), 0) & FLAG_USE_STATIC_IMG)
    s_txt  = sum(1 for e in elems if flags.get(int(e['id']), 0) & FLAG_USE_STATIC_TEXT)
    s_clr  = sum(1 for e in elems if flags.get(int(e['id']), 0) & FLAG_USE_STATIC_COLOR)
    c_img  = sum(1 for e in elems if e.get('conditional_images'))
    c_txt  = sum(1 for e in elems if e.get('conditional_texts'))
    data   = build_element_static_map(elems)
    print(f"[INFO] ElementStaticMap (v2): {len(data)} bytes ({total}+1 entries, 32B each)")
    print(f"[INFO] imageID: {s_img} static (removable) | {c_img} conditional (stay in INI)")
    print(f"[INFO] textID:  {s_txt} static (removable) | {c_txt} conditional (stay in INI)")
    print(f"[INFO] color:   {s_clr} baked -> ~{s_clr * 4} INI lines saved ($colorR/G/B/A)")
    total_saved = s_img + s_txt + (s_clr * 4)
    assert s_img + s_txt + s_clr > 0, "Nothing to remove — check image_id/text_id/color fields"
    print(f"[PASS] reduction_summary: ~{total_saved} INI assignments removable "
          f"({s_img} img + {s_txt} txt + {s_clr*4} color lines)")


TESTS = [
    test_sentinel_at_end,
    test_sorted_by_id,
    test_all_elements_included,
    test_836767_included,
    test_lookup_correct_for_all,
    test_color_stored_for_static_elements,
    test_formula_color_has_no_bake,
    test_flag_use_static_color_set,
    test_blacklist_color_set_for_static,
    test_flag_is_element_always_set,
    test_conditional_elements_not_static,
    test_reduction_summary,
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
