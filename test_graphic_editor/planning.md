# Project Plan: Vector Graphic Editor (standalone)

This document outlines the design and feature set for a new vector-based graphic editor built with PySide6. The goal is to provide a powerful yet streamlined experience—more capable than Paint.NET but less complex than Adobe Photoshop.

## 1. Core Concept & Philosophy
- **Hybrid Approach**: Primarily vector-based (SVG/Path logic) but with robust raster support (layers, effects).
- **Standalone First**: Runs independently of Blender for development and testing.
- **Addon Ready**: Modular architecture to allow seamless integration as a Blender panel later.
- **Performance**: Lightweight core with lazy-loading for heavy operators.

---

## 2. Essential Functionality (Categorized)

### A. Core Engine & Data
- **Layer System**: 
    - Infinite layers (bounded by RAM).
    - Layer types: Vector (Paths, Shapes), Raster (Bitmaps), Adjustment (Filters), Group.
    - Blending modes: Normal, Multiply, Screen, Overlay, etc.
- **Vector Engine**:
    - Bezier curve manipulation.
    - Boolean operations (Unite, Subtract, Intersect, Exclude).
    - Stroke & Fill: Solid, Gradient (Linear/Radial), Pattern.
- **File Management**:
    - Custom `.vgproj` format (JSON/Binary hybrid).
    - **File Management**:
    - Custom `.vgproj` format (JSON/Binary hybrid).
    - Export: PNG, JPG, SVG, TIFF, **DDS**.
    - Open: PNG, JPG, SVG, BMP, **DDS**.
    - Auto-save & Versioning.

### B. Visual Tools (Operators)
- **Selection & Transform**:
    - Global move, rotate, scale.
    - Node-level editing (Vertex manipulation).
- **Drawing Tools**:
    - Pen Tool (Bezier).
    - Shape Tool (Rectangle, Ellipse, Polygon, Star).
    - Brush Tool (Vector-based with pressure support).
- **Image Processing (The "Operators")**:
    - **Blur**: Gaussian, Motion.
    - **Invert**: Color inversion.
    - **Warp**: Mesh transformation for vector and raster data.
    - **Color Correction**: HSL, Brightness/Contrast, Curves.

---

## 3. Visual Interface & Design (UI/UX)

### A. General Layout
- **Central Canvas**: High-performance viewport using `QGraphicsView` or custom OpenGL widget.
- **Sidebars (Dockable)**:
    - **Tools Palette**: Single/Double column on the left.
    - **Properties/Inspector**: Context-sensitive settings on the right.
    - **Layers Panel**: Lower right, with visibility, locking, and opacity controls.
- **Header**: Main menu (File, Edit, Image, Layer) + Contextual Options Bar (e.g., brush size when brush is selected).
- **Footer**: Status bar (Zoom level, Cursor coordinates, Current tool info).

### B. Input Management
- **Keyboard Shortcuts**: Fully rebindable (defaulting to standard Photoshop/Paint.NET shortcuts).
- **Mouse Handling**:
    - Left Click: Action/Select.
    - Middle Click/Space+Drag: Pan.
    - Ctrl + Scroll: Zoom.
- **Graphics Tablet Support**:
    - Pressure sensitivity for Brush size/opacity.
    - Tilt/Angle support for specific brushes.
    - WinTab/Windows Ink support via PySide6.

---

## 4. Technical Architecture (Directory Structure)

The folder structure is designed for modularity and ease of unit testing.

```text
test_graphic_editor/
├── core/
│   ├── app.py              # Main Application Entry (Standalone)
│   ├── canvas.py           # Viewport logic
│   ├── document.py         # Data model
│   └── layer.py            # Layer logic
├── managers/
│   ├── context_manager.py  # Tracks active tool/selection
│   ├── input_manager.py    # Tablet/Mouse/Keyboard routing
│   ├── file_manager.py     # IO (Save/Load/Export)
│   └── undo_manager.py     # Command pattern implementation
├── operators/
│   ├── base_op.py          # Abstract base class
│   ├── blur.py
│   ├── invert.py
│   ├── warp.py
│   └── colors.py
├── widgets/
│   ├── inspector.py
│   ├── layer_panel.py
│   ├── tool_bar.py
│   └── custom_inputs.py
├── utils/
│   ├── math_utils.py       # Geometry/Vector math
│   └── color_utils.py
├── resources/
│   ├── icons/
│   └── themes.qss
└── tests/
    ├── test_core.py
    ├── test_managers.py
    └── test_operators.py
```

---

## 5. Development Phases

1.  **Phase 1: Skeleton**: Basic PySide6 window + Canvas + Folder setup. [DONE]
2.  **Phase 2: Core Data**: Layer system and Vector Path classes. [IN PROGRESS]
3.  **Phase 3: Input & Tablet**: Pressure sensitivity and Input Manager.
4.  **Phase 4: Operators & Tools**: Implementation of Pen tool, Blur, Invert.
5.  **Phase 5: UI Polish**: Theming, Inspector, and Sidebar integration.
6.  **Phase 6: Testing & Optimization**: Rendering performance and Unit Tests.

---

## 6. Progress & Known Bugs

### ✅ Implemented
- Basic PySide6 application skeleton with dockable widgets.
- Viewport with zoom (Ctrl+Scroll) and tablet pressure sensitivity logging.
- Modular folder structure and base classes for managers/operators.
- **Document and Layer data models** (with layer stack management).
- **Raster Drawing System**: Brush and Eraser with size/hardness support.
- **Graphics Tablet Integration**: Pressure-sensitive drawing.
- **File IO**: Support for PNG, JPG, BMP, and **DDS** (via Pillow).
- **Core UI**: Menus (Open/Save) and Brush property toolbar.
- Basic unit testing setup (Tests passing).

### 🕒 In Progress
- Implementing Layer Panel UI for advanced stack management.
- Implementing "Operators" (Blur, Invert, Warp) logic.

### 🐞 Known Bugs
- **Resolved**: `NameError: QImage is not defined` in `FileManager` (missing import).
- **Resolved**: `NameError: VectorCanvas is not defined` in `app.py` (missing import).
