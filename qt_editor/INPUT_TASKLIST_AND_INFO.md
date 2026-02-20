# RZMenu Core Architecture Analysis & Tasks

## Objective
Analyze the fundamental architecture of RZMenu's Core modules (`transform`, `structure`, `blender_bridge`, `signals`) to identify why viewport interactions (movement, resize) are fragile and prone to regressions. Fix the core logic to provide a stable API for the Viewport.

## User Report
- "Teleportation" occurs during reparenting.
- "Jerky/Incorrect" movement.
- "Resize not working".
- Revert was performed due to worsening state (crashes/errors).

## Architectural Findings
1.  **Data Flow**: `Blender PropertyGroup` -> `read.py` -> `Viewport (Qt)` -> `transform.py` -> `Blender PropertyGroup`.
    -   **Bottleneck**: Writing to Blender Properties (`transform.py`) triggers a Scene Update. If called on every `mouseMove`, performance collapses.
2.  **Coordinate Systems**:
    -   **Blender**: Stores **Local** Position (Int).
    -   **Qt Viewport**: Operates in **Scene** (Global Float) or **Item** (Local Float) space.
    -   **Mismatch**: `move_elements_delta` applies a raw Delta to the Local Position. If the element is effectively global (root), this is fine. If it has a parent, and we move it visually in Scene Space, the Delta *should* be converted to Local Space, but `move_elements_delta` blindly adds it.
3.  **Reparenting Logic (`structure.py`)**:
    -   **Current State**: Updates `parent_id` but ignores coordinate space.
    -   **Result**: Visual Teleportation (Local (10,10) in Parent A becomes Local (10,10) in Parent B, which is a different World Loop).
    -   **Fix Required**: `NewLocal = NewParentInverseGlobal * OldGlobal`.

## Plan of Action (Core Only)
The User has restricted this task to **Core Modules**. The Viewport will be handled separately. We must ensure Core provides robust APIs that the Viewport *can* use (even if it currently doesn't).

### 1. Robust Math Module (`core/maths.py`)
-   Implement `get_global_position(element_id)`: Traverses parent hierarchy to sum positions.
-   Implement `calculate_local_pos(global_x, global_y, parent_id)`: Calculates required local pos to achieve a global target.

### 2. Fix `structure.reparent_element`
-   Use the new `Math Module` to calculate the correct new local position.
-   **Constraint**: Must preserve the *visual* location (Global Pos) of the element.

### 3. Fix `transform.py`
-   **Add `set_element_global_pos(elem_id, x, y)`**:
    -   Calculates necessary Local Pos.
    -   Updates Blender Data.
    -   Triggers Signal.
-   **Refactor `move_elements_delta`**:
    -   Keep for backward compatibility (keyboard shortcuts).
    -   Add warning or logic to handle parent transforms if possible.

### 4. Optimize Signals
-   Ensure `update_element_pos` (if added) has a `silent` flag for batch updates.

## Task List

- [ ] **maths.py**: Add global/local coordinate helpers.
- [ ] **structure.py**: Fix `reparent_element` using `maths.py`.
- [ ] **transform.py**: Add `set_element_global_pos` and `set_element_local_pos`.
- [ ] **transform.py**: Verify `resize_element` respects locks and hierarchy.
