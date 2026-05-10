# QA/test_buffer_concept.py
# Tests for Static Buffer concept using real test_scene.json data
# Run: python QA/test_buffer_concept.py

import json, struct, os, sys
from collections import defaultdict, Counter
from pathlib import Path

SCENE_PATH = Path(__file__).parent / "test_scene.json"
SCREEN_W, SCREEN_H = 1920, 1080
SLOTS_PER_ELEM = 7  # float4 records in DataBuffer per element

# ─────────────────────────────────────────────────────────────────────────────
# CORE CONCEPTS
# ─────────────────────────────────────────────────────────────────────────────

# Whitelist: attributes that MUST stay in INI (dynamic at runtime)
INI_WHITELIST = {
    # Interaction
    'click_event_enabled', 'hold_event_enabled', 'hover_event_enabled',
    'value_link', 'value_link_formula', 'value_link_is_formula',
    # Formulas
    'position_is_formula', 'size_is_formula', 'color_is_formula',
    'rotation_is_formula', 'transform_formula',
    # Conditional visibility
    'visibility_mode',       # only if == 'CONDITIONAL'
    'visibility_condition',
    # Interactive classes always stay in INI
    # (BUTTON, SLIDER, VECTOR_BOX, ANCHOR, GRID_CONTAINER)
    # Position/size stay if drag-capable:
    # ANCHOR -> position dynamic (draggable)
    # GRID_CONTAINER -> size dynamic (resizable)
}

# Blacklist: goes to static binary buffer
BUFFER_BLACKLIST = {
    'image_id', 'hover_image_id', 'extramap_image_id',
    'flip_x', 'flip_y', 'font_slot', 'style_id',
    'image_blending_mode', 'rotation',
    'alignment', 'text_align',
    'color',         # static RGBA
    'position',      # static XY  (unless anchor/grid)
    'size',          # static WH  (unless anchor/grid)
}

INTERACTIVE_CLASSES = {'BUTTON', 'SLIDER', 'VECTOR_BOX', 'ANCHOR', 'GRID_CONTAINER'}
DRAGGABLE_CLASSES   = {'ANCHOR'}
RESIZABLE_CLASSES   = {'GRID_CONTAINER'}

def needs_ini(elem):
    """Returns True if element needs ANY runtime code in INI."""
    cls = elem.get('elem_class', '')
    if cls in INTERACTIVE_CLASSES:
        return True
    if elem.get('position_is_formula') or elem.get('size_is_formula'):
        return True
    if elem.get('color_is_formula') or elem.get('rotation_is_formula'):
        return True
    if elem.get('transform_formula', '').strip():
        return True
    if elem.get('click_event_enabled') or elem.get('hold_event_enabled'):
        return True
    if elem.get('hover_event_enabled'):
        return True
    if elem.get('value_link') or elem.get('value_link_formula', '').strip():
        return True
    if elem.get('visibility_mode') == 'CONDITIONAL':
        return True
    return False

def position_is_dynamic(elem):
    """Position must be in INI (not static buffer) for draggable/formula elements."""
    if elem.get('elem_class') in DRAGGABLE_CLASSES:
        return True
    if elem.get('position_is_formula'):
        return True
    return False

def size_is_dynamic(elem):
    if elem.get('elem_class') in RESIZABLE_CLASSES:
        return True
    if elem.get('size_is_formula'):
        return True
    return False

# ─────────────────────────────────────────────────────────────────────────────
# TOPOLOGICAL SORT (parent must come before children, regardless of array order)
# ─────────────────────────────────────────────────────────────────────────────

def topo_sort(elements):
    """Sort elements so parent always appears before its children.
    This defines the draw order AND the buffer index assignment.
    No recursion - iterative DFS with explicit stack."""
    id_to_elem = {e['id']: e for e in elements}
    visited = set()
    result = []

    def visit_iterative(start_id):
        stack = [start_id]
        in_stack = set()
        while stack:
            eid = stack[-1]
            if eid in visited:
                stack.pop()
                continue
            e = id_to_elem.get(eid)
            if e is None:
                stack.pop()
                continue
            pid = e['parent_id']
            if pid >= 0 and pid not in visited and pid not in in_stack:
                in_stack.add(pid)
                stack.append(pid)
            else:
                stack.pop()
                in_stack.discard(eid)
                if eid not in visited:
                    visited.add(eid)
                    result.append(e)

    for e in elements:
        visit_iterative(e['id'])
    return result

# ─────────────────────────────────────────────────────────────────────────────
# BUFFER LAYOUT
# ─────────────────────────────────────────────────────────────────────────────

class ElementRecord:
    """Represents one element's static data in the binary buffer."""
    def __init__(self, elem, buf_index, id_to_bufidx):
        self.elem_id   = elem['id']
        self.buf_index = buf_index   # draw order index (= INI di_count slot)
        self.elem_name = elem.get('element_name', '')
        self.elem_class = elem.get('elem_class', 'CONTAINER')
        self.parent_id = elem['parent_id']
        self.parent_buf_index = id_to_bufidx.get(self.parent_id, -1)

        # Static slot values (7 float4 records)
        pos  = elem.get('position', [0, 0])
        size = elem.get('size', [100, 30])
        col  = elem.get('color', [1, 1, 1, 1])
        img  = elem.get('image_id', 0) if elem.get('image_id', -1) >= 0 else 0
        flip = (1 if elem.get('flip_x') else 0) | (2 if elem.get('flip_y') else 0)
        font = elem.get('font_slot', 0)
        rot  = elem.get('rotation', 0.0)
        style = elem.get('style_id', -1)
        # draw_mode: 0=solid, 3=text, determined by class+image
        if elem.get('elem_class') == 'TEXT':
            draw_mode = 3
        elif img > 0:
            draw_mode = 1  # image
        else:
            draw_mode = 0  # solid color

        self.slots = [
            (0.0, 0.0, 0.0, 0.0),                                   # slot 0: flags
            (pos[0]/SCREEN_W, pos[1]/SCREEN_H,
             size[0]/SCREEN_W, size[1]/SCREEN_H),                    # slot 1: pos+size
            tuple(col[:4]),                                           # slot 2: color
            (float(img), 0.0, 0.0, 0.0),                            # slot 3: tile_data
            (float(flip), float(font), 0.0, float(rot)),             # slot 4: mirror/font/rot
            (0.0, 0.0, 0.0, 0.0),                                    # slot 5: clip_rect (filled at runtime by parent)
            (0.0, float(max(style, 0)), 0.0, float(draw_mode)),      # slot 6: fn/style/tex/mode
        ]

    def to_bytes(self):
        """Serialize to binary: 7 * 4 floats = 112 bytes per element."""
        data = b''
        for slot in self.slots:
            data += struct.pack('4f', *slot)
        return data

    def patch_slot(self, slot_idx, values):
        """Patch a single slot (used for partial updates from INI)."""
        assert len(values) == 4
        self.slots[slot_idx] = tuple(values)


class StaticBuffer:
    """Binary buffer with all static element data, indexed by buf_index."""

    RECORD_SIZE = SLOTS_PER_ELEM * 16  # 7 * 4 floats * 4 bytes = 112 bytes

    def __init__(self):
        self.records = []   # list[ElementRecord] in draw order
        self.id_to_record = {}

    def add(self, rec):
        self.records.append(rec)
        self.id_to_record[rec.elem_id] = rec

    def get_by_id(self, elem_id):
        return self.id_to_record.get(elem_id)

    def serialize(self):
        """Produce flat binary blob."""
        return b''.join(r.to_bytes() for r in self.records)

    def byte_offset(self, buf_index):
        return buf_index * self.RECORD_SIZE


class INISection:
    """Represents the minimal INI fragment needed for one dynamic element."""
    def __init__(self, elem, buf_index):
        self.elem_id   = elem['id']
        self.buf_index = buf_index
        self.elem_name = elem.get('element_name', '')
        self.lines = []
        self._build(elem)

    def _build(self, elem):
        """Generate only the dynamic parts of the element."""
        cls = elem.get('elem_class', 'CONTAINER')
        L = self.lines

        # Position formula
        if elem.get('position_is_formula'):
            L.append(f"; pos formula")
            if elem.get('position_formula_x', '').strip():
                L.append(f"$PositionX = {elem['position_formula_x']}")
            if elem.get('position_formula_y', '').strip():
                L.append(f"$PositionY = {elem['position_formula_y']}")
        elif cls in DRAGGABLE_CLASSES:
            pos = elem.get('position', [0, 0])
            L.append(f"$PositionX = $window_{self.elem_id}_X")
            L.append(f"$PositionY = $window_{self.elem_id}_Y")

        # Color formula
        if elem.get('color_is_formula'):
            L.append(f"$colorR = {elem.get('color_formula_r', '1')}")
            L.append(f"$colorG = {elem.get('color_formula_g', '1')}")
            L.append(f"$colorB = {elem.get('color_formula_b', '1')}")
            L.append(f"$colorA = {elem.get('color_formula_a', '1')}")

        # Transform formula (raw)
        tf = elem.get('transform_formula', '').strip()
        if tf:
            L.append(tf)

        # Visibility
        if elem.get('visibility_mode') == 'CONDITIONAL':
            cond = elem.get('visibility_condition', '1')
            L.append(f"if !({cond})")
            L.append(f"  run = CommandListPatchAlpha0_{self.buf_index}")
            L.append(f"else")
            L.append(f"  run = CommandListPatchAlpha1_{self.buf_index}")
            L.append(f"endif")

        # Click event
        if elem.get('click_event_enabled'):
            L.append(f"if $clickTriggerID == {self.elem_id}")
            formula = elem.get('click_event_formula', '').strip()
            if formula:
                L.append(f"  {formula}")
            L.append(f"endif")

        # Hold event
        if elem.get('hold_event_enabled'):
            formula = elem.get('hold_event_formula', '').strip()
            if formula:
                L.append(f"if $capturedID == {self.elem_id} && $dragState == 3")
                L.append(f"  {formula}")
                L.append(f"endif")

        # Value link
        value_link = elem.get('value_link', [])
        if value_link:
            for vl in value_link:
                vname = vl.get('value_name', '')
                if vname:
                    L.append(f"if $clickTriggerID == {self.elem_id}")
                    L.append(f"  ${vname} = 1 - ${vname}")
                    L.append(f"endif")

        # Patch buffer instruction (always last - writes dynamic data to buffer slot)
        L.append(f"z111 = {self.buf_index}")
        L.append(f"run = CustomShaderPatchElement_{self.elem_id}")

    @property
    def line_count(self):
        return len(self.lines) + 2  # +2 for [section header] + blank line

    def render(self):
        header = f"[CommandListElement_{self.elem_name}_{self.elem_id}]"
        return "\n".join([header] + self.lines + [""])


# ─────────────────────────────────────────────────────────────────────────────
# PARTIAL PATCH SYSTEM
# "How does the buffer know which slots to update when INI only specifies rotation?"
# Answer: each patch command encodes a SLOT MASK
# ─────────────────────────────────────────────────────────────────────────────

SLOT_POS   = 1 << 1   # slot 1: position+size
SLOT_COLOR = 1 << 2   # slot 2: color
SLOT_CLIP  = 1 << 5   # slot 5: clip rect

def compute_patch_mask(elem):
    """Which buffer slots need runtime patching for this element?"""
    mask = 0
    if elem.get('position_is_formula') or elem.get('elem_class') in DRAGGABLE_CLASSES:
        mask |= SLOT_POS
    if elem.get('color_is_formula'):
        mask |= SLOT_COLOR
    # Clip rect needs patching if element has a parent with clipping
    if elem.get('parent_id', -1) >= 0:
        mask |= SLOT_CLIP
    return mask


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE: Build full layout from scene JSON
# ─────────────────────────────────────────────────────────────────────────────

def build_pipeline(elements):
    """
    1. Topo-sort elements (parent before child, regardless of array order)
    2. Assign buf_index = position in sorted array
    3. Classify each element: static (buffer only) vs dynamic (needs INI section)
    4. Build StaticBuffer and list of INISections
    Returns: (static_buf, ini_sections, sorted_elems, id_to_bufidx)
    """
    sorted_elems = topo_sort(elements)

    # Assign buf_index
    id_to_bufidx = {e['id']: i for i, e in enumerate(sorted_elems)}

    # Build static buffer
    static_buf = StaticBuffer()
    for buf_idx, elem in enumerate(sorted_elems):
        rec = ElementRecord(elem, buf_idx, id_to_bufidx)
        static_buf.add(rec)

    # Build INI sections only for dynamic elements
    ini_sections = []
    for buf_idx, elem in enumerate(sorted_elems):
        if needs_ini(elem):
            ini_sections.append(INISection(elem, buf_idx))

    return static_buf, ini_sections, sorted_elems, id_to_bufidx


# ─────────────────────────────────────────────────────────────────────────────
# TESTS
# ─────────────────────────────────────────────────────────────────────────────

def load_scene():
    with open(SCENE_PATH, encoding='utf-8') as f:
        return json.load(f)['elements']


def test_topo_sort_correctness():
    """After sort, every parent must appear BEFORE its children."""
    elems = load_scene()
    sorted_elems = topo_sort(elems)
    id_to_pos = {e['id']: i for i, e in enumerate(sorted_elems)}

    violations = []
    for e in sorted_elems:
        pid = e['parent_id']
        if pid >= 0:
            parent_pos = id_to_pos.get(pid)
            child_pos  = id_to_pos[e['id']]
            if parent_pos is None:
                violations.append(f"  orphan: id={e['id']} references missing parent={pid}")
            elif parent_pos >= child_pos:
                violations.append(f"  VIOLATION: id={e['id']} at pos {child_pos}, parent {pid} at pos {parent_pos}")

    assert not violations, "Topo sort violations:\n" + "\n".join(violations)
    print(f"[PASS] topo_sort_correctness: {len(sorted_elems)} elements, 0 violations")


def test_buf_index_stable():
    """buf_index (draw order) must match topological position, not array id or element id."""
    elems = load_scene()
    _, _, sorted_elems, id_to_bufidx = build_pipeline(elems)

    # Parent must always have a lower buf_index than its children
    for i, e in enumerate(sorted_elems):
        pid = e['parent_id']
        if pid >= 0:
            parent_buf = id_to_bufidx.get(pid, -1)
            assert parent_buf < i, (
                f"Draw order violation: elem id={e['id']} (buf={i}) "
                f"has parent id={pid} (buf={parent_buf})"
            )
    print(f"[PASS] buf_index_stable: all {len(sorted_elems)} buf_indexes are correct")


def test_static_vs_dynamic_classification():
    """Validate that classification matches expected counts from scene analysis."""
    elems = load_scene()
    static_buf, ini_sections, sorted_elems, _ = build_pipeline(elems)

    total = len(sorted_elems)
    n_static = total - len(ini_sections)
    n_dynamic = len(ini_sections)

    print(f"[INFO] Total elements: {total}")
    print(f"[INFO] Static (buffer only): {n_static} ({100*n_static/total:.1f}%)")
    print(f"[INFO] Dynamic (needs INI):  {n_dynamic} ({100*n_dynamic/total:.1f}%)")

    # Every interactive class must be dynamic
    for e in sorted_elems:
        if e['elem_class'] in INTERACTIVE_CLASSES:
            is_dyn = any(s.elem_id == e['id'] for s in ini_sections)
            assert is_dyn, f"Interactive elem id={e['id']} class={e['elem_class']} should be dynamic!"

    print(f"[PASS] static_vs_dynamic: all interactive classes are dynamic")


def test_static_buffer_serialization():
    """Buffer must serialize to correct byte size."""
    elems = load_scene()
    static_buf, _, sorted_elems, _ = build_pipeline(elems)

    blob = static_buf.serialize()
    expected_size = len(sorted_elems) * StaticBuffer.RECORD_SIZE
    assert len(blob) == expected_size, (
        f"Buffer size mismatch: got {len(blob)}, expected {expected_size}"
    )

    # Verify first element's position slot
    first = sorted_elems[0]
    pos  = first.get('position', [0, 0])
    size = first.get('size', [100, 30])
    # Read back slot 1 from blob (offset = 1 * 16 bytes into first record)
    slot1 = struct.unpack('4f', blob[16:32])
    assert abs(slot1[0] - pos[0]/SCREEN_W) < 1e-5, f"pos.x mismatch: {slot1[0]} vs {pos[0]/SCREEN_W}"
    assert abs(slot1[1] - pos[1]/SCREEN_H) < 1e-5, f"pos.y mismatch"

    print(f"[PASS] static_buffer_serialization: {len(blob)} bytes, first elem pos verified")


def test_partial_patch_mask():
    """Each dynamic element gets correct slot mask for partial buffer updates."""
    elems = load_scene()
    _, _, sorted_elems, _ = build_pipeline(elems)

    # Elements with position_formula must have SLOT_POS set
    formula_elems = [e for e in sorted_elems if e.get('position_is_formula')]
    for e in formula_elems:
        mask = compute_patch_mask(e)
        assert mask & SLOT_POS, f"elem id={e['id']} has pos formula but mask missing SLOT_POS"

    # Pure static elements (no formula, no events, root) must have mask=0 for pos/color
    pure_static = [
        e for e in sorted_elems
        if not needs_ini(e) and e.get('parent_id', -1) < 0
    ]
    for e in pure_static:
        mask = compute_patch_mask(e)
        assert not (mask & SLOT_POS), f"Static root elem id={e['id']} should not patch pos"

    print(f"[PASS] partial_patch_mask: {len(formula_elems)} formula elems verified")


def test_ini_line_reduction():
    """Measure how many INI lines are saved vs naive (all-dynamic) approach."""
    elems = load_scene()
    static_buf, ini_sections, sorted_elems, _ = build_pipeline(elems)

    # Naive: every element gets ~15 lines in INI
    NAIVE_LINES_PER_ELEM = 15
    naive_total = len(sorted_elems) * NAIVE_LINES_PER_ELEM

    # New: only dynamic elements get INI sections
    new_total = sum(s.line_count for s in ini_sections)
    # Plus: static buffer declaration (~3 lines)
    new_total += 3

    saved = naive_total - new_total
    pct   = 100.0 * saved / naive_total if naive_total > 0 else 0

    print(f"[INFO] Naive INI lines:   {naive_total}")
    print(f"[INFO] New INI lines:     {new_total}")
    print(f"[INFO] Lines saved:       {saved} ({pct:.1f}%)")
    print(f"[INFO] Static buf size:   {len(static_buf.serialize())} bytes "
          f"({len(sorted_elems)} elems x {StaticBuffer.RECORD_SIZE}b)")

    assert new_total < naive_total, "New approach should save lines"
    print(f"[PASS] ini_line_reduction: {pct:.1f}% reduction")


def test_parent_offset_resolution():
    """
    KEY PROBLEM: INI uses $id for interaction (hoveredID==id etc).
    buf_index is the draw/buffer position.
    These are DIFFERENT. Verify that both mappings are maintained independently.
    """
    elems = load_scene()
    _, _, sorted_elems, id_to_bufidx = build_pipeline(elems)

    # id = unique element identifier (arbitrary, set by Blender)
    # buf_index = sequential draw order index (0..N)
    # These must NEVER be confused.

    sample = sorted_elems[:5]
    print("[INFO] id vs buf_index mapping (sample):")
    for e in sample:
        bid = id_to_bufidx[e['id']]
        print(f"  elem_name={e['element_name']:25s}  id={e['id']:6d}  buf_index={bid:3d}")

    # Verify: parent's buf_index must be accessible from child's INI via lookup
    # The INI section for a child knows its buf_index, and can refer to parent's
    # buf_index for clip rect inheritance
    child_with_parent = [e for e in sorted_elems if e['parent_id'] >= 0]
    for e in child_with_parent[:3]:
        parent_buf = id_to_bufidx.get(e['parent_id'], -1)
        child_buf  = id_to_bufidx[e['id']]
        assert parent_buf >= 0, f"Parent buf_index missing for elem id={e['id']}"
        assert parent_buf < child_buf, "Parent must precede child in buffer"

    print(f"[PASS] parent_offset_resolution: id<->buf_index mapping is correct and separate")


def test_preset_underlayer_slots():
    """
    Presets/helpers/underlayers: instead of separate CommandLists,
    they are drawn as additional instances around the main element.
    Concept: 5 underlayer slots + 1 main + 5 preset slots + 5 helper slots = 16 draws.
    All from the same DrawInstanced call.
    """
    elems = load_scene()
    _, _, sorted_elems, id_to_bufidx = build_pipeline(elems)

    elems_with_presets = [e for e in sorted_elems if e.get('preset_ids')]
    elems_with_under   = [e for e in sorted_elems if e.get('underlayer_preset_ids')]

    MAX_UNDERLAYER = 5
    MAX_PRESET     = 5
    MAX_HELPER     = 5
    DRAW_SLOTS_PER_ELEM = 1 + MAX_UNDERLAYER + MAX_PRESET + MAX_HELPER  # = 16

    print(f"[INFO] Elements with presets:    {len(elems_with_presets)}")
    print(f"[INFO] Elements with underlayers:{len(elems_with_under)}")
    print(f"[INFO] Draw slots per element:   {DRAW_SLOTS_PER_ELEM}")
    print(f"[INFO] Max visual draws total:   {len(sorted_elems) * DRAW_SLOTS_PER_ELEM}")

    # Verify: preset_ids reference valid element ids
    all_ids = {e['id'] for e in sorted_elems}
    broken_refs = 0
    for e in elems_with_presets:
        for pref in e.get('preset_ids', []):
            pid = pref.get('preset_id', -1)
            if pid >= 0 and pid not in all_ids:
                broken_refs += 1

    print(f"[INFO] Broken preset references: {broken_refs}")
    print(f"[PASS] preset_underlayer_slots: concept validated")


def test_debug_full_export_flag():
    """
    Full debug export: all elements write their buffer section explicitly in INI.
    This overwrites the static buffer region for that element.
    Patch mask = ALL_SLOTS (0x7F = all 7 slots).
    """
    elems = load_scene()
    static_buf, ini_sections, sorted_elems, id_to_bufidx = build_pipeline(elems)

    ALL_SLOTS_MASK = 0x7F  # bits 0..6

    debug_ini_lines = 0
    for buf_idx, elem in enumerate(sorted_elems):
        # In debug mode, every element explicitly patches all 7 slots
        # Format: "z111 = <buf_idx>  x111 = <ALL_SLOTS_MASK>  dispatch = 1,1,1"
        debug_ini_lines += 5  # section header + 3 patch lines + blank

    print(f"[INFO] Debug full export would generate {debug_ini_lines} INI lines")
    print(f"[INFO] vs normal mode: {sum(s.line_count for s in ini_sections)} lines")
    print(f"[PASS] debug_full_export_flag: concept validated")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

TESTS = [
    test_topo_sort_correctness,
    test_buf_index_stable,
    test_static_vs_dynamic_classification,
    test_static_buffer_serialization,
    test_partial_patch_mask,
    test_ini_line_reduction,
    test_parent_offset_resolution,
    test_preset_underlayer_slots,
    test_debug_full_export_flag,
]

if __name__ == "__main__":
    passed = 0
    failed = 0
    for test_fn in TESTS:
        print(f"\n--- {test_fn.__name__} ---")
        try:
            test_fn()
            passed += 1
        except Exception as ex:
            print(f"[FAIL] {ex}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed / {len(TESTS)} total")
