# Implementation Plan - Fixing Property Errors & Restoring Shaders

## Goal
Resolve `_PropertyDeferred` errors in Blender 5.0/4.0+ by converting property assignments to annotations, fix registration issues, and restore "old system" compatibility by reordering resource bindings in `core.j2`.

## Proposed Changes

### 1. Data Model (Blender Props)

#### [MODIFY] [blender_props.py](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/core/live2d/blender_props.py)
- Convert all `name = StringProperty(...)` to `name: StringProperty(...)` to comply with Blender 4.0+ / 5.0 RNA requirements. This will fix the `_PropertyDeferred` issue.

#### [MODIFY] [properties.py](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/data/properties.py)
- Ensure consistent annotation style for all properties.

### 2. UI & Registration

#### [MODIFY] [live2d_ops.py](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/operators/live2d_ops.py)
- Fix the `AttributeError: '_PropertyDeferred' object has no attribute 'add'` by ensuring the props are correctly accessed once the class is fixed.

#### [MODIFY] [inspector.py](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/qt_editor/widgets/inspector.py)
- Fix `TypeError: 'setText' called with wrong argument types` by ensuring values passed to `setText` are explicitly strings.

### 3. Template & Buffer Compatibility

#### [MODIFY] [core.j2](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/rztemplate/modules/core.j2)
- Reorder `[Resource...]` blocks. Move `[ResourceAnimationBuffer]` to the end of the resource list to prevent slot-index shifting for existing buffers (`t106`, `u7`, etc.).
- Verify all `filename` paths are correct.

## Open Questions
- Were the old shaders relying on a specific order of `[Resource...]` sections in the `.ini` file for binding? 3DMigoto sometimes uses the order to assign defaults if slots are missing.

## Verification Plan
### Automated Tests
- Run `pack_live2d_data` and verify no more `_PropertyDeferred` errors occur.
- Verify that `res/*.bin` files are correctly generated.

### Manual Verification
- Check the Inspector in the Qt Editor to ensure the Skeleton name displays correctly.
- Test adding a bone and verify it doesn't throw `AttributeError`.
- Export and check if the generated `.ini` file correctly lists the resources in an order compatible with the old setup.
