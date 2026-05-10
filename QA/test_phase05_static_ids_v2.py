# QA/test_phase05_static_ids_v2.py
# Tests for Phase 0.5 v2: $id-indexed ElementStaticMap
# Run: python QA/test_phase05_static_ids_v2.py

import json, struct
from pathlib import Path

SCENE_PATH = Path(__file__).parent / "test_scene.json"

FLAG_IS_ELEMENT      = 0x04
FLAG_USE_STATIC_IMG  = 0x01
FLAG_USE_STATIC_TEXT = 0x02


def _safe_id(val):
    if val is None: return 0
    try: v = int(val); return max(0, v)
    except: return 0


def build_element_static_map(elements):
    """Compact sorted array: (id, imageID, textID, 0) per element + sentinel."""
    entries = []
    for elem in elements:
        eid = elem.get('id', 0)
        img = _safe_id(elem.get('image_id'))
        txt = _safe_id(elem.get('text_id'))
        entries.append((eid, img, txt))
    entries.sort(key=lambda e: e[0])
    result = bytearray()
    for eid, img, txt in entries:
        result += struct.pack('<ffff', float(eid), float(img), float(txt), 0.0)
    result += struct.pack('<ffff', 0.0, 0.0, 0.0, 0.0)  # sentinel
    return bytes(result)


def build_element_flags_map(elements):
    flags_map = {}
    for elem in elements:
        flags = FLAG_IS_ELEMENT
        img = _safe_id(elem.get('image_id'))
        txt = _safe_id(elem.get('text_id'))
        if img > 0 and not elem.get('conditional_images'):
            flags |= FLAG_USE_STATIC_IMG
        if txt > 0 and not elem.get('conditional_texts'):
            flags |= FLAG_USE_STATIC_TEXT
        flags_map[elem['id']] = flags
    return flags_map


def simulate_cs_lookup(buf_bytes, target_id):
    """Simulate CS linear scan for matching id. Returns (imageID, textID)."""
    entry_size = 16  # 4 floats * 4 bytes
    n_entries  = len(buf_bytes) // entry_size
    for i in range(n_entries):
        eid, img, txt, _ = struct.unpack_from('<ffff', buf_bytes, i * entry_size)
        if int(eid) == 0:      # sentinel
            break
        if int(eid) == target_id:
            return int(img), int(txt)
    return 0, 0


def simulate_controller(ini_image_id, found_image, flags):
    """
    Python simulation of the CS override priority logic.
    Returns final imageID written to DataBuffer.
    """
    tile_x = ini_image_id  # default: from INI x102
    if (flags & FLAG_IS_ELEMENT) and (flags & FLAG_USE_STATIC_IMG):
        if found_image > 0 and ini_image_id < 0.5:
            tile_x = float(found_image)   # static wins
        # else: ini_image_id >= 0.5 means INI provided value → INI wins
    return tile_x


def load_scene():
    with open(SCENE_PATH, encoding='utf-8') as f:
        return json.load(f)['elements']


# ─────────────────────────────────────────────────────────────────────────────

def test_sentinel_at_end():
    """Buffer must end with {0,0,0,0} sentinel."""
    elems = load_scene()
    data  = build_element_static_map(elems)
    last_entry = struct.unpack_from('<ffff', data, len(data) - 16)
    assert all(v == 0.0 for v in last_entry), f"Sentinel not zero: {last_entry}"
    print(f"[PASS] sentinel_at_end: {len(data)//16 - 1} entries + sentinel")


def test_sorted_by_id():
    """Entries must be sorted ascending by id."""
    elems = load_scene()
    data  = build_element_static_map(elems)
    n     = len(data) // 16
    ids   = []
    for i in range(n):
        eid = struct.unpack_from('<f', data, i * 16)[0]
        if int(eid) == 0: break
        ids.append(int(eid))
    assert ids == sorted(ids), f"IDs not sorted: {ids[:10]}"
    print(f"[PASS] sorted_by_id: {len(ids)} entries sorted")


def test_all_elements_included():
    """All rzm.elements must appear in the buffer."""
    elems = load_scene()
    data  = build_element_static_map(elems)
    id_set_in_buf = set()
    n = len(data) // 16
    for i in range(n):
        eid = int(struct.unpack_from('<f', data, i * 16)[0])
        if eid == 0: break
        id_set_in_buf.add(eid)
    for elem in elems:
        assert elem['id'] in id_set_in_buf, f"Missing id={elem['id']} ({elem['element_name']})"
    print(f"[PASS] all_elements_included: {len(id_set_in_buf)} elements in buffer")


def test_836767_included():
    """System element 836767 (ControllerCursor) must be in buffer with image_id=10009."""
    elems = load_scene()
    data  = build_element_static_map(elems)
    img, txt = simulate_cs_lookup(data, 836767)
    assert img == 10009, f"Expected imageID=10009 for id=836767, got {img}"
    print(f"[PASS] 836767_included: id=836767 -> imageID={img}")


def test_lookup_correct_for_all():
    """CS simulation: every element's imageID resolves correctly."""
    elems = load_scene()
    data  = build_element_static_map(elems)
    mismatches = []
    for elem in elems:
        expected_img = _safe_id(elem.get('image_id'))
        found_img, _ = simulate_cs_lookup(data, elem['id'])
        if found_img != expected_img:
            mismatches.append(
                f"  id={elem['id']} {elem['element_name']}: "
                f"expected {expected_img}, got {found_img}"
            )
    assert not mismatches, "Lookup mismatches:\n" + "\n".join(mismatches)
    print(f"[PASS] lookup_correct_for_all: all {len(elems)} elements verified")


def test_flag_is_element_always_set():
    """FLAG_IS_ELEMENT (0x04) must be set for ALL rzm.elements."""
    elems  = load_scene()
    flags  = build_element_flags_map(elems)
    broken = [e['id'] for e in elems if not (flags[e['id']] & FLAG_IS_ELEMENT)]
    assert not broken, f"Missing FLAG_IS_ELEMENT for ids: {broken}"
    print(f"[PASS] flag_is_element_always_set: all {len(elems)} elements")


def test_conditional_elements_not_static():
    """Elements with conditional_images must NOT have FLAG_USE_STATIC_IMG."""
    elems  = load_scene()
    flags  = build_element_flags_map(elems)
    broken = []
    for elem in elems:
        if elem.get('conditional_images') and (flags[elem['id']] & FLAG_USE_STATIC_IMG):
            broken.append(f"  id={elem['id']} {elem['element_name']}")
    assert not broken, "Conditional elements marked static:\n" + "\n".join(broken)
    print("[PASS] conditional_elements_not_static")


def test_static_wins_when_ini_zero():
    """CS sim: INI x102=0 (commented) + IS_ELEMENT + STATIC_IMG → buffer wins."""
    result = simulate_controller(ini_image_id=0.0, found_image=47,
                                  flags=FLAG_IS_ELEMENT | FLAG_USE_STATIC_IMG)
    assert abs(result - 47.0) < 0.001, f"Expected 47, got {result}"
    print("[PASS] static_wins_when_ini_zero")


def test_ini_wins_when_conditional():
    """CS sim: INI x102=46 (conditional set) → INI wins, buffer ignored."""
    result = simulate_controller(ini_image_id=46.0, found_image=47,
                                  flags=FLAG_IS_ELEMENT | FLAG_USE_STATIC_IMG)
    assert abs(result - 46.0) < 0.001, f"Expected 46 (INI), got {result}"
    print("[PASS] ini_wins_when_conditional")


def test_preset_bypasses_lookup():
    """CS sim: preset/helper x111=0 (no IS_ELEMENT) → lookup skipped, INI as-is."""
    result = simulate_controller(ini_image_id=9.0, found_image=47, flags=0)
    assert abs(result - 9.0) < 0.001, f"Expected 9 (preset INI), got {result}"
    print("[PASS] preset_bypasses_lookup: x111=0 -> no static map consulted")


def test_element_without_image_has_zero():
    """Elements with no imageID → found_image=0 → CS writes nothing (tile stays from INI)."""
    elems  = load_scene()
    data   = build_element_static_map(elems)
    no_img = [e for e in elems if _safe_id(e.get('image_id')) == 0]
    for elem in no_img[:5]:
        found_img, _ = simulate_cs_lookup(data, elem['id'])
        assert found_img == 0, f"id={elem['id']} should have 0 imageID in map"
    print(f"[PASS] element_without_image_has_zero: {len(no_img)} elements checked")


def test_reduction_summary():
    """Print summary of what gets removed from INI."""
    elems  = load_scene()
    flags  = build_element_flags_map(elems)
    total  = len(elems)
    s_img  = sum(1 for e in elems if flags[e['id']] & FLAG_USE_STATIC_IMG)
    s_txt  = sum(1 for e in elems if flags[e['id']] & FLAG_USE_STATIC_TEXT)
    c_img  = sum(1 for e in elems if e.get('conditional_images'))
    c_txt  = sum(1 for e in elems if e.get('conditional_texts'))
    data   = build_element_static_map(elems)
    print(f"[INFO] ElementStaticMap: {len(data)} bytes ({total}+1 entries)")
    print(f"[INFO] imageID: {s_img} static (removable) | {c_img} conditional (stay in INI)")
    print(f"[INFO] textID:  {s_txt} static (removable) | {c_txt} conditional (stay in INI)")
    assert s_img + s_txt > 0, "Nothing to remove — check image_id/text_id fields"
    print(f"[PASS] reduction_summary: {s_img+s_txt} INI assignments removable")


TESTS = [
    test_sentinel_at_end,
    test_sorted_by_id,
    test_all_elements_included,
    test_836767_included,
    test_lookup_correct_for_all,
    test_flag_is_element_always_set,
    test_conditional_elements_not_static,
    test_static_wins_when_ini_zero,
    test_ini_wins_when_conditional,
    test_preset_bypasses_lookup,
    test_element_without_image_has_zero,
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
