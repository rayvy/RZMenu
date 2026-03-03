# RZMenu QT Editor Migration: Implementation Plan

This plan outlines the modernization of the RZMenu QT Editor, focusing on stability, performance, and "Apple Magic" aesthetics.

## Phase 1.5: High Performance Viewport [COMPLETED]
*   **Viewport Optimization**:
    *   **Font Cache**: Implemented `RZFontManager`.
    *   **LOD Grid**: Implemented adaptive grid rendering in `drawBackground`.
    *   **Result**: Stable 100+ FPS behavior.

---

## Phase 2: Apple Magic & UX Refinement (Multi-Part Overhaul)

### Phase 2.1: Design System & Minimalist Icons
*   **Aesthetic Token Update**:
    *   Update `definitions.py` with premium design tokens: `radius_sm` (8px), `radius_md` (16px), `radius_lg` (24px).
    *   Define `elevation_shadows` (soft, multi-layer drop shadows for depth).
*   **Minimalist Icons**:
    *   Replace existing "complex" icons with crisp, minimalist SVGs.
    *   Update `IconManager` to correctly search `base_icons/` with prefix handling if necessary.
*   **QSS Engine Update**:
    *   Refactor `generator.py` to support variable-based border-radius and shadow-emulation via QProxyStyle or custom painting wrappers where QSS is insufficient.

### Phase 2.2: Animation Layer (Transitions & Physics)
*   **Core Animations**:
    *   **Liquid Fill**: Shader-like reveal animations for button states.
    *   **Fade Transitions**: Smooth opacity ramps (0.0 -> 1.0) for panel switching and hover states.
*   **Physics Interaction**:
    *   **"Flying Paper" DND**: Implement the physics-based drag-and-drop from the `apple_viewport` prototypes into the main `viewport.py`.

### Phase 2.3: Structural UX & Layout Overhaul
*   **Layout Navigation**:
    *   Move the current layout switcher to a **Top-Aligned Tab Bar** with smooth underline transitions.
*   **Inspector Refactoring**:
    *   **Tabbed Properties**: Separate "Transform", "Anchor/Pivot", and "Logic" into clearly defined tabs.
    *   **Flexible Textboxes**: Implement vertical auto-expansion for formula inputs.
*   **Global Theming**:
    *   Eliminate all remaining hardcoded color strings in favor of `get_current_theme()` lookups.

---

## Phase 3: Advanced Functionality
*   **Element Preservation**: Ensure absolute identity stability during complex structural edits.

## Verification Plan

### Automated Tests
*   `python tests/benchmarks/viewport_fps.py`: Baseline performance check.
*   `python tests/ui/theme_validation.py`: Verify no hardcoded colors remain.

### Manual Verification
*   **Visual Inspection**: Compare new minimalist icons against "premium" reference designs.
*   **Animation Smoothness**: Verify that panel switching does not "pop" but fades gracefully.
*   **Physics Feel**: Verify the "lag" and "corner-pinning" of elements during viewport dragging.
 stone
