# Shapekey Rework Experiment

## Objective
Analyze the output of the `Rayvich Auto-Component Injector` and validate the feasibility of a buffer-based shapekey system for EFMI/3DMigoto.

## Initial Findings (Baseline)
- **Files analyzed:**
    - Original: `Meshes\Component6_VB0.buf`
    - Modified: `Blend\Component6_VB0_Sport.buf`
- **Vertex Statistics:**
    - Total: 28,379
    - Changed: 8,000 (28.2%)
    - Max Displacement: 0.000499 (Matches `0.0005` limit)

## Tools
- `analyze_diff.py`: Basic byte-level and vertex-level comparison.
- `test_buffer_integrity.py`: Validation of buffer structure and data safety.

## Proposed "Buffer Parameter" Logic
Instead of relying on large amounts of keyframes for position offsets, we plan to:
1. Export each shape as a full `VB0`.
2. Map these buffers to `Resource` blocks in the mod `.ini`.
3. Swap `vb0` dynamically in a `CommandList` triggered by UI parameters.

> [!NOTE]
> This approach is great for binary toggles (on/off). For smooth blending, we may need to implement a vertex shader that takes two buffers and interpolates between them.
