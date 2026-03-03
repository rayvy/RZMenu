# Phase 2.4: Apple Experience Refinement

This phase transforms the editor from a functional tool into a premium, fluid experience by implementing high-end interaction patterns, smooth physics, and structural refinement.

## Proposed Changes

### 1. Viewport & Interaction Physics
- **Refined Paper Drag**:
    - Add a velocity threshold for the paper tilt; micro-movements will remain flat.
    - Synchronize the Gizmo's transformation (or temporarily hide/dim it) during aggressive tilts to prevent visual detachment.
    - Integrate paper physics into the **Asset Browser** drag-and-drop flow.
- **Micro-Animations**:
    - **Hover State**: Subtle scale/glow effect when hovering over viewport elements.
    - **Pressed State**: Implement a "pressed fill" transition (solid or soft liquid) when an element is clicked.
    - **Liquid Fill Context**: Remove default selection liquid effect. Re-implement it specifically for "Image Drop" previews (based on the demo script).

### 2. Monolithic & Anchored Inspector
- **Unified Scroll Area**: Remove the `QTabWidget` (Identity/Layout/Style/Logic) and place all groups in a single, continuous vertical layout.
- **Sticky Anchor Bar**:
    - Implement a custom tab-like bar at the top that stays fixed.
    - **Smooth Accent Line**: Add a `QPropertyAnimation` for the selection underline that slides between active sections.
    - **Bi-directional Sync**: Clicking a tab jumps to the section. Scrolling the section updates the active tab in the bar.
- **UI Cleanup**:
    - Remove redundant "Properties" tab.
    - Remove old navigation buttons.

### 3. Polish & Global UX
- **Smooth Scrolling**: Implement an interpolated, physics-based scroll for all `QScrollArea` components (Inspector, Asset Browser).
- **Animated Dropdowns**: Add a fade-and-slide animation to `RZComboBox` popups.
- **Header Optimization**:
    - Reduce the height of the main window header.
    - Migrating "Layout" action buttons (Save/Reset) to the top header adjacent to the layout tabs.
- **Outliner Visuals**: Replace the "eye" icon with a more minimalist Apple-style alternative.
- **Flexible Inputs**: Enable vertical expansion/resizing for large text areas (e.g., Mod Info).

# Phase 2.6: Performance & Critical Finalization

## Proposed Changes

### [Inspector] [MODIFY] [inspector.py](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/qt_editor/widgets/inspector.py)
- [NEW] Define `self.chk_trans_formula` and `self.edit_trans_fx` in `_init_properties_ui` to fix `AttributeError`.
- [Refine] Improve `RZInspectorAnchorBar` to behave as a scrolling tab system with smooth interpolation.
- [Optimize] Throttle `refresh_data` calls using a short timer (debounce) to prevent UI freezing during rapid property updates.

### [Viewport] [MODIFY] [viewport.py](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/qt_editor/widgets/viewport.py)
- [Fix] Correct "Liquid Fill" detection to use the hovered item found via `_get_element_at` instead of the active selection.
- [Fix] Implement `set_drop_highlight` in `RZElementItem` (re-verify it's properly defined).
- [Fix] Ensure MMB navigation resets the cursor state from "drag" to "arrow/pointing" correctly.

### [Global UX] [MODIFY] [widgets.py](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/qt_editor/widgets/lib/widgets.py)
- [Optimize] Refactor `RZScrollArea` to reduce animation overhead. Ensure only one animation per area.
- [Animation] Add `RZSelectionInterpolation` helper and apply to `VariablesPanel` and `AssetBrowser` items for smooth hover/active states.

### [Inputs] [MODIFY] [inputs.py](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/qt_editor/widgets/lib/inputs.py)
- [Fix] Debug `RZCodeTextEdit` vertical resizing. Use `minimumHeight` constraints instead of `setFixedHeight` to allow layout flexibility.

## Verification Plan
### Automated Tests
- `python qt_editor/test/apple_viewport.py` (Verify physics and DnD).
### Manual Verification
1.  Check FPS during property dragging and scrolling.
2.  Verify "Liquid Fill" on non-selected elements during image drag.
3.  Test layout switching stability (spamming tabs).
4.  Verify vertical resizing of code text boxes.

## Regression Fixes & Stability

### 1. Inspector Panel (`inspector.py`)
- **Initialization Order**: Move `self.has_data = False` and `self._block_signals = False` to the very top of `__init__` before any UI building logic.
- **Reference Fixes**: Replace all remaining `self.l_logic.addWidget()` and `self.l_style.addWidget()` calls with `self.layout_props.addWidget()`.

### 2. Viewport DnD (`viewport.py`)
- **Recursive Item Search**: Implement a helper `_get_element_at(pos)` that looks for `RZElementItem` by traversing upwards from the item found at `pos`. This ensures that dropping an image onto a child (like a label) correctly highlights the parent element.
- **DnD Highlight**: Ensure `application/x-rzmenu-image-id` (Asset Browser images) correctly triggers the `set_drop_highlight(True)` call.

### 3. Outliner Visuals (`outliner.py`)
- **Header Cleanup**: Remove Unicode eye/arrow symbols from `setHeaderLabels`.
- **Icon Only Columns**: Remove text from visibility and lock columns, relying purely on the icons for a cleaner, modern look.

### 4. Crash Prevention (`window.py`)
- **Safe Layout Transitions**:
    - Disconnect all signals from the previous `self.splitter` before deletion.
    - Wrap `apply_layout` and `LayoutManager.build_layout` in try-except blocks.
    - Ensure `deleteLater()` is called only after the new layout is successfully inserted and signals are blocked.

## Verification Plan

### Automated Tests
- No new automated tests are planned for these visual/interactive changes, as they rely heavily on visual feel.

### Manual Verification
- **Inspector Anchor Test**: Verify that clicking "Style" in the anchor bar smoothly scrolls to the Style group and that the blue underline slides correctly.
- **Scroll Sync Test**: Scroll the Inspector manually and verify the anchor bar updates its active tab correctly.
- **Paper Physics Threshold**: Perform slow and fast drags in the viewport; verify that only fast sweeps cause the "paper tilt."
- **Asset Drop Test**: Drag an item from the Asset Browser and verify it exhibits paper physics.
- **Smooth Scroll Audit**: Verify that mouse-wheel scrolling in the Inspector doesn't "snap" but has a soft deceleration.
