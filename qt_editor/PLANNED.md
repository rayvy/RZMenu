# RZMenu Project Status: Planned Features & Roadmap

This document consolidates all planned features, pending fixes, and the long-term roadmap for the RZMenu QT Editor.

## 🔴 Current Phase: Advanced Logic, UX & Critical Fixes
* **Preservation System**: Logic to maintain element identities and formula overrides during structural changes.
* **Identity Recovery**: Automated recovery of broken links in formulas when elements are renamed.
* **"Apple Experience" Polish**:
    * **Elastic Viewport**: Rubber-band resistance at zoom/pan limits.
    * **Audio-Visual Cues**: Haptic-like sounds for snapping and clicks.
    * **Selection Interpolation**: Smooth hover/active animations for the Variables panel.
    * **Snapping Refinement**: Convert Snap Solver to use Global (Scene) coordinates.
* **AttributeError Fix**: Add missing `chk_trans_formula` and `edit_trans_fx` fields.
* **Performance Optimization**: Implement throttling for UI updates and optimize scroll animations to restore high FPS.
* **Liquid Fill Fix**: Ensure the effect works on any element under the cursor (hover), not just the active one.
* **Inspector Improvement**: Transform the top anchor panel into a dynamic tab system with smooth scrolling.
* **Resize & Cursor Fix**: Repair vertical expansion of textboxes and fix cursor sticking issues within the viewport.
* **TexWorks Reconstruction (Low Priority)**:
    * Repair `widgets/texworks_panel.py`.
    * Fix `TexWorksManager` initialization and bridge context calls.
    * Reimplement `ListItemManager` and layer editor with stable hierarchy tracking.

## 🟠 Future Phases (Roadmap)
### Phase 2: Integrated Graphics Editor
* **Atlas Workshop**: Dedicated canvas for direct decal painting within the editor.
* **Hybrid Engine**: Support for both raster (QImage) and vector (Bezier paths) primitives.
* **Standard Toolset**: Layers, brushes, eyedropper, and non-destructive cropping.


### Phase 3: Mesh-Based Animation System
* **Mesh Foundation**: Support for arbitrary Vertex Buffers in the GPU instancer.
* **2D Skeletal Skinning**: Bone hierarchy buffer and vertex-to-bone weighting.
* **Timeline & Curves**: Professional keyframe editor with cubic Bezier support.

### Phase 4: Live 3D Preview
* **QtQuick3D Integration**: Embedded 3D viewport for PBR visualization.
* **Live Model Sync**: "Body Pick" system to fetch Blender mesh as proxy data.
* **Multichannel PBR**: Support for Normal, Metallic, and Roughness maps.

---
*Last updated: 2026-03-03*