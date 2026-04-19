# Implementation Plan - Live2D Fix & Polish

The user reported a crash in the Qt Inspector due to a missing `skeleton_name` property in the blender data model. Additionally, I need to verify and fix UI visibility logic and potential method name mismatches.

## User Review Required

> [!IMPORTANT]
> I will be adding a `skeleton_name` property to the `RZSkeletonProp` group. This will be used to display the active skeleton identity in the Qt Editor.

## Proposed Changes

### 1. Data Model (`blender_props.py`)
- [MODIFY] [blender_props.py](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/core/live2d/blender_props.py)
    - Add `skeleton_name: StringProperty(name="Skeleton Name", default="Main Skeleton")` to `RZSkeletonProp`.

### 2. Inspector UI (`inspector.py`)
- [MODIFY] [inspector.py](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/qt_editor/widgets/inspector.py)
    - Fix `update_ui` to correctly toggle the visibility of `grp_mesh` based on whether the selected element is `LIVE2D`.
    - Correct the slider update method from `refresh_value` (stale/typo) to `set_value_from_backend` to match the rest of the inspector.

### 3. Data Reading (`read.py`)
- [MODIFY] [read.py](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/qt_editor/core/read.py)
    - Ensure `skeleton_name` is read from the correct property once added.

### 4. Logic & Shaders
- I reviewed the `animate_bones.hlsl` matrix logic and found it correct for 2D affine transforms. No changes needed there unless testing shows otherwise.
- I will double-check `draw_instancer.hlsl` for any obvious typos in variable names.

## Verification Plan

### Manual Verification
- Launch the Qt Editor in Blender.
- Select a `LIVE2D` element.
- Verify that the "Mesh & Skeleton" group appears and displays the default skeleton name.
- Verify that selecting a non-Live2D element hides the group.
- Check the console for any `AttributeError` during selection.
