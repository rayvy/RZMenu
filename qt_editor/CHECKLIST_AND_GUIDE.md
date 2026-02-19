# RZMenu/qt_editor Repair Checklist & Guide

This document was generated based on the "Technical Report (UI Tool for 3DMigoto)" and a code audit performed on 2026-02-20.

## 🚨 Legend
- **(black)**: Module Dead / Broken. Value: Critical. Needs complete rewrite/restoration.
- **(red)**: Logic Broken / Dangerous. Value: High. Needs immediate fix.
- **(yellow)**: Suspicious / Tech Debt. Value: Medium. Needs investigation or refactoring.
- **(green)**: Good / Stable.

---

## 🛠 Fix Checklist

### 1. Functional Criticals (Non-Functional)
- [ ] **TexWorks Main Block** `widgets/texworks_panel.py`
    - [ ] Status: **(black)** "Completely non-functional".
    - [ ] Fix: `TexWorksManager` initialization is suspect. Ensure `add_tab` and `stack` layout work.
    - [ ] Fix: `_on_val` calls `_call_op` which bypasses bridge context. Identify why operators fail or don't trigger updates.
- [ ] **TexWorks Layer Editor** `widgets/texworks_panel.py`
    - [ ] Status: **(black)** "Modules Dead".
    - [ ] Fix: `ListItemManager` integration. Identify if `decal_layers` property exists in `rzm.elements`.
    - [ ] Fix: `_update_layer` parent traversal is **(red)** fragile. Reimplement using explicit ID passing or a stable context lookup.

### 2. Architecture & Tech Debt
- [ ] **Bridge & Context** `core/blender_bridge.py`
    - [ ] Status: **(yellow)** Flaky `exec_in_context`.
    - [ ] Fix: Improve `get_stable_context` to handle non-3DView operators if needed (e.g. Image Editor context).
    - [ ] Fix: `widgets/texworks_panel.py` uses direct `bpy.context` access. If running in separate thread/process, this is fatal. If inside Blender, ensure thread safety.
- [ ] **Hardcoding**
    - [ ] Fix: `widgets/texworks_panel.py` string literals ("slots", "components"). Move to constants.
    - [ ] Fix: Fragile `while p: ... parent()` loops in `_update_slot` and `_update_layer`.

### 3. Transformation & UX
- [ ] **Teleportation** `core/structure.py`
    - [ ] Status: **(red)** `reparent_element`.
    - [ ] Fix: Implement matrix compensation.
        ```python
        # Pseudo-code fix
        old_global = elem.matrix_world
        elem.parent_id = new_parent
        elem.matrix_local = elem.parent.matrix_world.inverted() @ old_global
        ```
- [ ] **Teleportation** `core/transform.py`
    - [ ] Status: **(red)** `move_elements_delta`.
    - [ ] Fix: Ensure delta is applied in correct space (Local vs Global) depending on parent.
- [ ] **Gizmo Issues** `widgets/viewport.py`
    - [ ] Fix: `RZHandleItem` Z-Index (10000) might be causing fighting.
    - [ ] Fix: `handle_resize` calculation assumes simple hierarchy. Needs `mapFromScene` / `mapToItem` logic.

### 4. Data & Assets
- [ ] **Clipboard** `core/clipboard.py`
    - [ ] Status: **(yellow)** Missing "Paste in Place".
    - [ ] Fix: Add `paste_in_place` argument to `paste_elements` (offset=0).
    - [ ] Status: **(yellow)** Image Path Loss.
    - [ ] Fix: Ensure `image_id` refers to persistent data, or copy image data to new ID if it's temp.

---

## 📘 Implementation Guide

### How to Fix "Teleportation" (Reparenting)
The current `reparent_element` function in `core/structure.py` only changes the ID.
**Correction Strategy:**
1.  Calculate **Global Position** of the child before reparenting.
    - `GlobalPos = ParentGlobalPos + LocalPos` (simplified for 2D).
2.  Change `parent_id`.
3.  Calculate **New Local Position** relative to the new parent.
    - `NewLocalPos = GlobalPos - NewParentGlobalPos`.
4.  Apply `NewLocalPos` to `elem.position`.

### How to Fix "Dead" TexWorks Modules
The `TexWorks` panel relies on a UI hierarchy that mirrors the data hierarchy (`Block -> Component -> Slot -> Layer`).
The current code tries to reconstruct the Data ID chain by walking up the Qt Widget Tree (`w.parent().parent()...`).
**This is brittle.**
**Correction Strategy:**
1.  Pass the full `chain_ids` (BlockID, CompID, SlotID) explicitly to the sub-widgets or `ListItemManager`.
2.  Store them in a strict data object on the widget, not relying on `parent()` lookups.

### How to Fix Bridge Bypass
`widgets/texworks_panel.py` calls `bpy.context` directly.
**Correction Strategy:**
1.  Wrap all property updates in `blender_bridge.exec_in_context` or similar wrapper.
2.  Ensure `_call_op` forces the update to happen in the main Blender thread if strictly required.

---

## 🛑 Code Tags
I have marked the code with comments:
- Look for `# (black)` in `texworks_panel.py`.
- Look for `# (red)` in `transform.py` and `structure.py`.
- Look for `# (yellow)` in `clipboard.py` and `blender_bridge.py`.

Use `Ctrl+Shift+F` (Global Search) for these tags to jump to problem areas.
