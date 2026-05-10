# QA/test_formula_classifier.py
# Tests for formula relative/absolute classification
# using real element data from test_scene.json

import json, re
from pathlib import Path

SCENE_PATH = Path(__file__).parent / "test_scene.json"

# ---- Position flags (mirrors Slot 7.y bits) ----
BIT_RELATIVE          = 1 << 0  # static position = offset from parent
BIT_ABSOLUTE          = 1 << 1  # static position = world coords, ignore parent
BIT_FORMULA_RELATIVE  = 1 << 2  # formula adds to inherited $PositionX/$PositionY
BIT_FORMULA_ABSOLUTE  = 1 << 3  # formula writes final world position directly

# Vars that indicate a formula inherits parent position
RELATIVE_VARS = {'$PositionX', '$positionX', '$PositionY', '$positionY',
                 '$SizeX', '$sizeX', '$SizeY', '$sizeY'}

def classify_formula(formula_x: str, formula_y: str) -> int:
    """
    Determine if a position formula is relative (uses $PositionX/$PositionY)
    or absolute (writes world coordinates directly).
    Returns a bitmask: BIT_FORMULA_RELATIVE or BIT_FORMULA_ABSOLUTE.
    """
    combined = (formula_x or '') + ' ' + (formula_y or '')
    for var in RELATIVE_VARS:
        if var in combined:
            return BIT_FORMULA_RELATIVE
    return BIT_FORMULA_ABSOLUTE


def classify_position_flags(elem: dict, has_parent: bool) -> int:
    """
    Full position flag classification for a single element.
    Returns combined bitmask for Slot 7.y.
    """
    flags = 0
    pos_is_formula = elem.get('position_is_formula', False)

    if pos_is_formula:
        fx = elem.get('position_formula_x', '')
        fy = elem.get('position_formula_y', '')
        flags |= classify_formula(fx, fy)
    else:
        # Static position
        if has_parent:
            # Default: treat static position as offset from parent
            # (generator places children relative to parent in Blender)
            flags |= BIT_RELATIVE
        else:
            flags |= BIT_ABSOLUTE  # root = world coordinates

    return flags


# ─────────────────────────────────────────────────────────────────────────────
# TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_formula_relative_detection():
    """Formulas using $PositionX/$PositionY -> RELATIVE."""
    cases_relative = [
        ("$PositionX + 20",   "$PositionY + 10"),
        ("$positionX + ($SizeX / 2)", "$PositionY"),
        ("$PositionX - 5",    "$PositionY + $SizeY"),
    ]
    for fx, fy in cases_relative:
        flags = classify_formula(fx, fy)
        assert flags == BIT_FORMULA_RELATIVE, (
            f"Expected RELATIVE for ({fx!r}, {fy!r}), got {flags:#010b}"
        )
    print(f"[PASS] formula_relative_detection: {len(cases_relative)} cases")


def test_formula_absolute_detection():
    """Formulas NOT using $PositionX/$PositionY -> ABSOLUTE."""
    cases_absolute = [
        ("$ElementAnchorPositionX + 25", "$ElementAnchorPositionY"),
        ("$window0AreaX + 120",          "$window0AreaY + 45"),
        ("960",                          "540"),
        ("$screenW / 2",                 "$screenH / 2"),
    ]
    for fx, fy in cases_absolute:
        flags = classify_formula(fx, fy)
        assert flags == BIT_FORMULA_ABSOLUTE, (
            f"Expected ABSOLUTE for ({fx!r}, {fy!r}), got {flags:#010b}"
        )
    print(f"[PASS] formula_absolute_detection: {len(cases_absolute)} cases")


def test_root_element_is_absolute():
    """Root elements (parent_id < 0) with static position -> ABSOLUTE."""
    elem = {
        'parent_id': -1,
        'position_is_formula': False,
        'position': [100, 200],
    }
    flags = classify_position_flags(elem, has_parent=False)
    assert flags & BIT_ABSOLUTE, "Root static elem should be ABSOLUTE"
    assert not (flags & BIT_RELATIVE), "Root should NOT be RELATIVE"
    print("[PASS] root_element_is_absolute")


def test_child_element_is_relative():
    """Child elements (parent_id >= 0) with static position -> RELATIVE."""
    elem = {
        'parent_id': 2,
        'position_is_formula': False,
        'position': [10, 10],
    }
    flags = classify_position_flags(elem, has_parent=True)
    assert flags & BIT_RELATIVE, "Child static elem should be RELATIVE"
    assert not (flags & BIT_ABSOLUTE), "Child should NOT be ABSOLUTE"
    print("[PASS] child_element_is_relative")


def test_real_scene_formula_classification():
    """Run classifier on all formula elements from test_scene.json."""
    with open(SCENE_PATH, encoding='utf-8') as f:
        elems = json.load(f)['elements']

    formula_elems = [e for e in elems if e.get('position_is_formula')]
    id_set = {e['id'] for e in elems}

    relative_count = 0
    absolute_count = 0
    examples_rel = []
    examples_abs = []

    for e in formula_elems:
        fx = e.get('position_formula_x', '')
        fy = e.get('position_formula_y', '')
        flags = classify_formula(fx, fy)
        has_parent = e.get('parent_id', -1) in id_set

        if flags == BIT_FORMULA_RELATIVE:
            relative_count += 1
            if len(examples_rel) < 3:
                examples_rel.append((e['element_name'], fx, fy))
        else:
            absolute_count += 1
            if len(examples_abs) < 3:
                examples_abs.append((e['element_name'], fx, fy))

    total = len(formula_elems)
    print(f"[INFO] Formula elements: {total}")
    print(f"[INFO]   RELATIVE: {relative_count} ({100*relative_count/max(1,total):.0f}%)")
    print(f"[INFO]   ABSOLUTE: {absolute_count} ({100*absolute_count/max(1,total):.0f}%)")
    print()
    print("[INFO] Examples RELATIVE:")
    for name, fx, fy in examples_rel:
        print(f"  {name}: x='{fx[:50]}' y='{fy[:50]}'")
    print("[INFO] Examples ABSOLUTE:")
    for name, fx, fy in examples_abs:
        print(f"  {name}: x='{fx[:50]}' y='{fy[:50]}'")

    assert total > 0, "Should have formula elements in test scene"
    print(f"\n[PASS] real_scene_formula_classification: {total} elements classified")


def test_full_position_flags_scene():
    """Assign position_flags for every element in scene, verify no element has flags=0."""
    with open(SCENE_PATH, encoding='utf-8') as f:
        elems = json.load(f)['elements']

    id_set = {e['id'] for e in elems}
    flag_dist = {BIT_RELATIVE: 0, BIT_ABSOLUTE: 0,
                 BIT_FORMULA_RELATIVE: 0, BIT_FORMULA_ABSOLUTE: 0}
    zero_flags = []

    for e in elems:
        has_parent = e.get('parent_id', -1) in id_set
        flags = classify_position_flags(e, has_parent)
        if flags == 0:
            zero_flags.append(e['element_name'])
        for bit, count in flag_dist.items():
            if flags & bit:
                flag_dist[bit] = count + 1

    print("[INFO] Position flags distribution across all elements:")
    for bit, cnt in flag_dist.items():
        names = {BIT_RELATIVE: 'RELATIVE', BIT_ABSOLUTE: 'ABSOLUTE',
                 BIT_FORMULA_RELATIVE: 'FORMULA_RELATIVE',
                 BIT_FORMULA_ABSOLUTE: 'FORMULA_ABSOLUTE'}
        print(f"  {names[bit]:20s}: {cnt:3d} ({100*cnt/len(elems):.0f}%)")

    assert not zero_flags, f"Elements with flags=0 (broken): {zero_flags}"
    print(f"[PASS] full_position_flags_scene: all {len(elems)} elements have valid flags")


TESTS = [
    test_formula_relative_detection,
    test_formula_absolute_detection,
    test_root_element_is_absolute,
    test_child_element_is_relative,
    test_real_scene_formula_classification,
    test_full_position_flags_scene,
]

if __name__ == "__main__":
    passed = 0
    failed = 0
    for fn in TESTS:
        print(f"\n--- {fn.__name__} ---")
        try:
            fn()
            passed += 1
        except Exception as ex:
            print(f"[FAIL] {ex}")
            import traceback; traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed / {len(TESTS)} total")
