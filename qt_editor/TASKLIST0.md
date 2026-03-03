# RZMenu Strategic Roadmap (March - Dec 2026)

This roadmap details the transformation of RZMenu from a functional addon into a premium, professional creative suite inspired by "Apple Magic" UX and industry-standard technical foundations.

---

## � Phase 1: UX & "Apple Magic" (March - May)
*Goal: Achieve 60+ FPS fluidity, sub-pixel precision, and emotional visual feedback.*

### Technical Objectives
- [ ] **Virtual Viewport Sync**: Decouple QT dragging from Blender property updates. 
    - *Method*: Local-first transform in QT GraphicsScene, batched commit to Blender.
- [ ] **Micro-Animation Engine**: Implement easing curves (In-Out-Back) for every UI state change.
    - *Targets*: Hover scales, elastic lists, "springy" drag-and-drop.
- [ ] **Visual Polish**: 
    - Sub-pixel AA for text and shapes.
    - Sound triggers for "Satisfying" interactions (clicks, snaps, errors).
    - Adaptive layout that doesn't "jump" when switching tabs.

### 🚩 Pitfalls
- **Blender Overhead**: Frequent script-side updates block the UI thread. Must use `bpy.app.timers` or lazy synchronization.
- **Redraw Loops**: Excessive `SIGNALS.structure_changed` triggers. Need localized refresh narrow-casting.

---

## 🎨 Phase 2: Integrated Graphics Editor (March - May)
*Goal: Low-latency decal and icon editing without leaving the workspace.*

### Technical Objectives
- [ ] **Atlas Workshop**: A dedicated canvas for direct decal painting/modification.
- [ ] **Hybrid Vector/Raster Engine**:
    - Raster support via `PySide6.QtGui.QImage`.
    - Simple vector primitives (Bezier paths) for icon creation.
- [ ] **Standard Toolset**: Layers, brushes, eyedropper, and non-destructive cropping.
- [ ] **TexWorks Parity**: Live-mapping of painted data into the TexWorks resource system.

### 🚩 Pitfalls
- **Memory Management**: High-res textures (4K) in Python/QT memory.
- **Undo Stack Sync**: Reconciling the Graphics Canvas history with Blender's global undo-push.

---

## 🎬 Phase 3: Mesh-Based Animation System (April - June)
*Goal: Dynamic UI deformations and skeletal logic using Triangle Lists.*

### Technical Objectives
- [ ] **Mesh Foundation**: Upgrade `draw_instancer.hlsl` to support arbitrary Vertex Buffers (beyond quads).
- [ ] **2D Skeletal Skinning**:
    - Bone hierarchy buffer in GPU memory.
    - Vertex-to-bone weighting (Skinning shader).
- [ ] **Timeline & Curves**: Professional keyframe editor with cubic Bezier support.
- [ ] **Shader Parity**: Ensuring `position_shape_anim2.hlsl` logic integrates with the new skeletal system.

### 🚩 Pitfalls
- **Complexity**: Weight painting/assignment in a 2D UI context is UX-heavy.
- **Performance**: Skinned mesh calculations can be expensive if not correctly instanced.

---

## 🧊 Phase 4: Live 3D Preview (October - December)
*Goal: Real-time PBR visualization for decals on 3D models.*

### Technical Objectives
- [ ] **Qt3D/QtQuick3D Integration**: Embedded 3D viewport within the Python UI.
- [ ] **Live Model Sync**: "Body Pick" system to fetch current Blender mesh and textures as proxy data.
- [ ] **Multichannel PBR**: Support for RZMenu's specific PBR map layout (Normal, Metallic, Roughness).
- [ ] **Live Debugging**: Inspect how a decal wraps around the body *before* exporting to 3DMigoto.

### 🚩 Pitfalls
- **Shader Mismatch**: Ensuring the Qt shader looks like the game/Blender shader.
- **Context Management**: 3D viewports consume significant system resources (VRAM).

---

## 📦 Infrastructure: Smart Deployment
- [ ] **Remote-Binary Downloader**: 
    - *Fix*: Move the 150MB `RZMenu3622408.exe` to GitHub Releases.
    - *Implementation*: A "Check for Updates/Setup" script that fetches the binary only when needed.

---

> [!IMPORTANT]
> **Compatibility Policy**: Target OS: Windows. Target Blender: 4.5+. 
> We prioritize advanced features over legacy support.
