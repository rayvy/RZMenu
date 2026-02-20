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
- [x] **Teleportation** `core/structure.py`
    - [x] Status: **(green)** Fixed via Global Pos math.
- [x] **Teleportation** `core/transform.py`
    - [x] Status: **(green)** Fixed via `to_blender_coords` sign flip correction.
- [x] **Group Movement** `widgets/viewport.py`
    - [x] Status: **(green)** Fixed via Batch Commit on MouseRelease.
- [x] **Gizmo Issues** `widgets/viewport.py`
    - [x] Status: **(green)** Handles moved to Scene-Root with Max Z.
- [ ] **New: Ghost Handles** `widgets/viewport.py`
    - [ ] Status: **(yellow)** Handles remain after element deletion.
- [ ] **New: Keyboard Shortcuts** `widgets/viewport.py`
    - [ ] Status: **(yellow)** Layout-dependent (e.g. "Ф" check). Needs physical key codes.

### 4. Data & Assets
- [/] **Clipboard** `core/clipboard.py`
    - [ ] Status: **(yellow)** Missing "Paste in Place" (Ctrl+Shift+V).
- [ ] **DnD Assignment** `widgets/viewport.py`
    - [ ] Status: **(yellow)** Dragging image onto element should replace image_id, not create new element.

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

---

## 🚨 POST-MORTEM & RECOVERY PLAN (FEB 2026)

This section was added after an aborted session on 2026-02-20. The code has been reverted to a stable state. Use this guide to resume work without repeating the same mistakes.

### 🛑 Failed Implementations (Do Not Blindly Retry)
The following features caused critical regressions and system instability.

#### 1. Transform Caching ("The Cannon Shot")
*   **Attempt:** Caching `initial_scene_pos` and `matrices` on `mousePress` to avoid recalculation during drag.
*   **Failure:**
    *   **Recursive Drift:** `mouseMoveEvent` calculated a delta (`current - start`) and emitted it. The Blender Bridge applied this delta *cumulatively* to the object's position on every frame, causing exponential acceleration (e.g., `x += 10` became `x += 10, x += 20, x += 30...`).
    *   **Signal Noise:** Emitting signals on every pixel move flooded the bridge, causing massive FPS drops.
*   **Recovery Strategy:**
    *   **Throttle Signals:** Only emit update signals to Blender every `N` ms, or only on `mouseRelease`.
    *   **Visual vs Logical:** Update Qt Items visually in real-time (smooth), but update Blender Data *only* at the end of the operation.

#### 2. Anchor-Locked Resizing ("The Teleport")
*   **Attempt:** Calculating a fixed "Anchor Point" (opposite corner) in Scene Space and applying `setPos` to the item to keep it in place while resizing.
*   **Failure:**
    *   **Coordinate Space Mismatch:** `scenePos()` returns Scene Coordinates. `setPos()` expects **Parent Local** Coordinates. Applying Scene Coords to a child item caused it to fly off to `(SceneX, SceneY)` relative to its parent, effectively doubling its position offset.
    *   **NameError:** Usage of undefined variables (e.g., `is_ctrl`) inside helper functions due to scope issues.
*   **Recovery Strategy:**
    *   **Strict Mapping:** ALWAYS map calculated coordinates: `ParentItem.mapFromScene(TargetScenePos)` before calling `setPos`.
    *   **Atomic Updates:** Use `setRect` and `setPos` together. If possible, use `setGeometry` or a custom atomic method.

#### 3. Precision & Snapping ("Micro-teleportation")
*   **Attempt:** Rounding coordinates to integers to match RZMenu's data structure.
*   **Failure:**
    *   **Deadzone:** Rounding `0.4` to `0` meant small mouse movements were ignored.
    *   **Drift:** Continuous rounding of floating-point accumulators resulted in a "walking" error where the object would slowly drift 1px at a time or snap back to an old position on release.
*   **Recovery Strategy:**
    *   **Float Visuals, Int Data:** Allow Qt Items to float (sub-pixel) during drag. Only Cast to Int when saving to Blender Data.
    *   **Final Sync:** On `mouseRelease`, force the Qt Item to snap to the exact Integer position stored in Blender to ensure 1:1 sync.

---

### 🏗 Architecture Guide for Future Edits

#### 1. Input Handling (Viewport)
*   **Rule:** Do NOT put logic in `mouseMoveEvent`. It runs hundreds of times per second.
*   **Pattern:**
    ```python
    def mouseMoveEvent(self, event):
        # 1. Calc Delta (Raw Float)
        # 2. Update Visuals (Qt Item setPos) -> Fast, no bridge calls
        # 3. (Optional) Throttle Signal -> Emit to Blender every 50ms
    ```

#### 2. Coordinate Systems
*   **Scene Space:** Global view. Use for mouse interaction and absolute positioning.
*   **Local Space:** Relative to Parent. Use for storage and `setPos`.
*   **Conversion:**
    ```python
    # Correct Reparenting / Move Logic
    target_pos_scene = ... # Calculated from mouse
    parent = item.parentItem()
    if parent:
        target_pos_local = parent.mapFromScene(target_pos_scene)
        item.setPos(target_local_pt)
    else:
        item.setPos(target_pos_scene)
    ```

#### 3. Debugging Tools
*   **Disable Snapping:** Before testing core math, implement a global flag `DISABLE_SNAPPING = True` to isolate whether bugs are from constraints or raw logic.
*   **Visual Debug:** Draw the "Target Rect" and "Anchor Point" as debug lines (`QGraphicsLineItem`) during resize to see where the math thinks the object should be.

### 📋 Next Steps (Prioritized)
1.  **Re-verify Basics:** After revert, confirm standard single-item move works.
2.  **Fix Multi-Selection (Logic Only):** Implement the Bounding Box math *without* touching the Coordinate System first. Print the calculated values to console to verify scale factors.
3.  **Implement Coordinate Mapping:** Create a robust helper function `set_scene_pos(item, point)` that handles the parent mapping automatically, and use it everywhere.
