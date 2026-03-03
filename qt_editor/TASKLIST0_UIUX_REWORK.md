# UI/UX Rework: "The Apple Magic" (TASKLIST0_UIUX_REWORK)

This document focuses on the visual and interactive "soul" of RZMenu Editor. The goal is to move from "functional but stiff" to "fluid and emotional".

## 🛠️ The "Sync Lie" Problem & Solution
**Issue**: Direct Blender updates on every mouse move cause low FPS and jitter. Previous attempts at local caching led to desynchronization (The "Source of Truth" conflict).

**Proposed Solution: Shadow State + Transactional Sync**
1.  **Mirror Model**: Qt stores a local `QPersistentModelIndex`-style cache of element data.
2.  **Interaction Layer**: During Drag/Resize, ONLY the Mirror Model is updated. Viewport renders at 144Hz+.
3.  **Atomic Commit**: `mouseReleaseEvent` triggers ONE batch update to Blender.
4.  **Blender Heartbeat**: Periodic (lazy) sync from Blender back to Qt ensures no divergent reality. If Blender UNDO happens, Qt receives a signal and repositions its Mirror Model.

---

## ✨ Apple-Style UX Requirements
- [ ] **Elastic Viewport**: When zooming/panning reaches limits, add subtle "rubber-band" resistance.
- [ ] **Spring Physics**: Move elements with momentum. Use `QPropertyAnimation` with `QEasingCurve.OutBack`.
- [ ] **Adaptive Feedback**:
    - Elements "breathe" (scale 1.0 -> 1.05) when hovered.
    - Drag-shadows have blur and distance-based offset.
- [ ] **Sub-pixel Layout**: Render coordinates with float precision in Qt, snap to Int only during the Blender Commit.
- [ ] **Audio-Visual Cues**: 
    - Soft "tick" sound when snapping.
    - Subtle "ripple" effect on click.

---

## 🏗️ Technical Prototype (qt_editor/test)
- [ ] **AppleViewport**: Clean scene with smooth pan/zoom and elastic borders.
- [ ] **MagicElement**: A test item demonstrating hover scaling, spring-drags, and magnetic snapping.
- [ ] **GraphicsEditorStub**: Workspace for raster/vector experiments.
- [ ] **3DPreviewStub**: Slot for QtQuick3D integration.

---

## 📈 Timeline
- **April**: Core UX Redesign (Viewport/Signals).
- **May**: "Magic" Animations & Physics integration.
- **June**: Unified Graphics/Animation workflow.
