# Implementation Plan - Shader Refactoring & Buffer Fixes

## Goal
Fix `draw_instancer.hlsl` compilation errors (SV_POSITION in PS context), resolve `E_INVALIDARG` buffer errors (0-byte files), and address HLSL warnings in `BlendResize.hlsl`.

## Proposed Changes

### 1. Shader Refactoring

#### [CREATE] `draw_instancer_vs.hlsl`
- Port the Vertex Shader logic from `draw_instancer.hlsl`.
- Contains `VS_INPUT`, `VS_OUTPUT`, and `main` (VS entry point).

#### [CREATE] `draw_instancer_ps.hlsl`
- Port the Pixel Shader logic from `draw_instancer.hlsl`.
- Contains `VS_OUTPUT` (as input) and `ps_main` (PS entry point).

#### [MODIFY] [core.j2](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/rztemplate/modules/core.j2)
- Update code injection to use separate VS/PS files if necessary, or ensure `ps_main` is explicitly specified as the entry point for PS sections.

### 2. Multi-Export Logic

#### [MODIFY] [exporter.py](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/core/live2d/exporter.py)
- Update `pack_live2d_data` to write a 16-byte dummy record (four zeros) instead of an empty file for `mesh.bin`, `weights.bin`, `bones.bin`, and `animations.bin` when no data exists.
- This ensures 3DMigoto can create the D3D buffers successfully.

### 3. Optimization & Warning Fixes

#### [MODIFY] [BlendResize.hlsl](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/rztemplate/modules/BlendResize.hlsl)
- Replace integer divisions/modulus with `uint` operations to clear compiler warnings.

## Verification Plan
### Automated Tests
- Export a project with NO Live2D elements and verify `res/*.bin` files are all 16 bytes or larger.
- Dry-run the HLSL compiler (fxc.exe if available) on the new VS and PS files.

### Manual Verification
- Check 3DMigoto log `d3d11_log.txt` for "Failed to substantiate" errors.
- Verify that the UI elements and bones appear in-game without "purple box" (shader failure) indicators.
