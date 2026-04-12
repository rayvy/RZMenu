# Missing Features in QT Editor

This document lists variables, functions, attributes, and components present in the Blender-native version of RZMenu but currently absent from the `qt_editor` implementation.

## 1. Data Structures & Properties
The following `bpy.types.PropertyGroup` structures and their corresponding mappings in `qt_editor/core/props.py` are missing:

- **Blend Resize System (`RZMBResizeSettings`)**
  - `is_enabled`: Logic toggle for bone-based resizing.
  - `groups`: Collection of `RZMBoneResizeGroup`.
  - `component_mappings`: Mapping layers for specific character components.
- **Native Shapes System (`ShapeKeyConfig`)**
  - `shape_discovery_collections`: Management of objects to scan for shape keys.
  - `shape_configs`: Per-key configuration (Mapping, Frame offsets).
  - `master_shape_value`: Global override attribute.
- **TexWorks Material System (Advanced blocks)**
  - `tw_blocks`: Complex material sequence definitions.
  - `tw_overrides`: Deep property overrides for shaders.
- **Export & Metadata**
  - `RZM_BuildProfile`: Definitions for different build variants.
  - `RZMAutoMenuSettings`: Automation flags for menu rebuilding.
  - `RZMGameSettings`: Global engine-specific behavior flags.

## 2. Functions & Operators (Logic)
Core logic modules and operators that are not yet reachable or implemented in the QT interface:

- **Puppet Master Pipeline**
  - Multi-layer vertex delta blending.
  - `puppet_master_ops.py`: Buffer generation and 3DMigoto export.
- **Blend Resize Logic**
  - Bone scale/position math for $Value links.
  - `blend_resize_ops.py`: Data baking and mapping.
- **Discovery & Validation**
  - Shape key auto-discovery across object hierarchies.
  - Dependency checking and auto-installation (`auto_check_dependencies`).
- **Capture System**
  - `capture_ops.py`: Logic for snapshotting visibility and shape states.
- **Mod Producer**
  - `mod_producer_ops.py`: Tier-based filtering and automated building.

## 3. UI Components (Widgets)
Panels and tabs from the Blender N-panel that have no equivalent in the QT viewport/inspector:

- **Blend Resize Tab**: All group and mapping management UI.
- **Native Shapes Manager**: Controls for bulk shape key editing and discovery.
- **Dependency Panel**: UI for Python package management.
- **Build Utilities**: Build suffix and active tier selection.
- **Debug Panel**: Statistics and raw data viewer.

## 4. Attributes & Global State
- `bpy.types.Scene.rzm_active_br_...`: All indices for BlendResize selection.
- `bpy.types.Object.rzm_tier_list`: Object-level tier assignment (partially handled in `props.py` but missing UI editor).
- `bpy.types.Scene.rzm_editor_mode`: Toggle between "Light" and "Pro" modes.
