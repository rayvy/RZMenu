# Prompt For TWAA_CORE.py Packing Work

You are working only on `utils/TWAA_CORE.py`.

Do not edit Blender operators, panels, TexWorks templates, image export code, or `bpy` integration. `TWAA_CORE.py` must remain pure Python with no Blender dependency.

## Goal

Implement robust UV cluster packing for RZMenu TexWorks AutoAtlas.

The surrounding Blender code already collects only faces belonging to the target Blender material. Your job is to transform those material-local faces into packed cluster data.

Hard rule:

- One Blender material equals one TexWorks component.
- A cluster is material-local.
- Other materials on the same mesh must not affect the cluster.
- The core must not know about Blender objects except opaque names stored in face dictionaries.

## Input Contract

Functions receive `faces`, a list of dictionaries. Each face is already filtered to the target material.

Each face has:

```python
{
    "object": "ObjectName",
    "mesh": "MeshName",
    "poly_index": 123,
    "material_index": 2,
    "loop_indices": [10, 11, 12],
    "uvs": [(u0, v0), (u1, v1), (u2, v2)],
    "source_uvs": [(u0, v0), (u1, v1), (u2, v2)],
    "surface_area": 1.234,
}
```

Notes:

- `uvs` are the UVs to pack.
- `source_uvs` are the UVs used for texture sampling when exporting PNG.
- For normal rebuild, `uvs == source_uvs`.
- For preview re-export, `uvs` are preview UVs and `source_uvs` are original source UVs.
- `loop_indices` are Blender loop indices, but core must treat them as opaque.
- UV values may be outside 0..1.

Reference dimensions:

```python
ref_w, ref_h
```

For texture mode these are usually the Diffuse size and define pixel density.

Margin:

```python
margin_px
```

Margin is part of every packed group rectangle.

## Output Contract

Core functions must return:

```python
islands, groups, face_to_group
```

`groups` are dictionaries:

```python
{
    "index": 0,
    "island_indices": [0, 1],
    "face_indices": [0, 4, 5],
    "u_min": 0.1,
    "v_min": 0.2,
    "u_max": 0.4,
    "v_max": 0.7,
    "content_w": 256,
    "content_h": 512,
    "w": 264,
    "h": 520,
}
```

After packing, layout groups must additionally contain:

```python
{
    "x": 0,
    "y": 0,
}
```

The Blender side uses:

- `group["u_min"]`, `group["v_min"]`, `content_w`, `content_h`, `x`, `y`, and margin to remap UVs.
- `face_to_group[face_index]` to know which packed rectangle each face belongs to.

Do not return Blender objects, image objects, or file paths.

## Two Modes

### 1. Texture Crop/Repack Mode

Triggered when Diffuse texture exists.

Intent:

- Remove unused source texture space.
- Preserve source pixel density.
- Do not rotate initially.
- Do not rescale content except the affine placement into the packed cluster.
- Move useful material-local UV regions into a compact canvas.
- Stacked islands are allowed to overlap only when they are truly stacked/same source region.

Important:

- This is not smart UV unwrap.
- This is crop/repack of used source texture regions.
- Horizontal strips caused by using whole-mesh bounds are a bug.
- The input faces are already material-local; use only them.

Expected strategy:

- Build UV islands from material-local faces.
- Detect stacked islands with high bbox/shape similarity.
- Keep stacked islands in one group.
- Pack island/groups without overlap.
- Preserve large connected islands when possible.
- Split large sparse groups only when it materially reduces wasted bbox area and does not create thousands of strips.

Forbidden:

- Per-vertex custom transforms.
- Whole-mesh bounds.
- Rotation unless explicitly added later as 90-degree-only optional mode.
- Output dimensions above 4096.

### 2. No-Texture Dense Mode

Triggered when Diffuse texture does not exist.

Intent:

- Generate a usable editable cluster UV layout from material-local faces.
- Allocate space by useful geometry contribution, not equal size for every tiny face.
- Avoid overlap.

Expected strategy:

- Prefer islands, not individual triangles, unless the source has no coherent islands.
- Use `surface_area` as density weight.
- Keep a minimum editable island size.
- Produce stable, readable UVs.

Current known bug:

- Existing no-texture behavior can create severe overlap and excessive triangle chaos. Fix this in core.

## Substance Size Constraint

The final cluster canvas must have width and height from this set:

```text
128, 256, 512, 1024, 2048, 4096
```

Examples of valid cluster sizes:

- 128x1024
- 512x4096
- 2048x2048

Core may return raw used width/height, but packing must fit within 4096x4096. Blender side pads the final canvas to Substance-compatible dimensions without rescaling content.

If content cannot fit within 4096, raise a clear error or return failure metadata.

## Test Requirements

Add pure-Python tests or quick scripts for:

- one material with sparse UV islands on a 4096x4096 source;
- stacked islands;
- multiple disconnected islands;
- no-texture large/small surface-area weighting;
- non-square output;
- no overlaps except stacked islands;
- no output larger than 4096 per side.

The real Blender test objects are:

- `TEST_CLUSTERS0`
- `TEST_CLUSTERS1`
- `TEST_CLUSTERS2`
- `TEST_CLUSTERS3`
- `TEST_CLUSTERS_NOTEX0`
- `TEST_CLUSTERS_NOTEX1`
- `TEST_CLUSTERS_NOTEX2`
- `TEST_CLUSTERS_NOTEX3`

The core tests should be possible without Blender by constructing face dictionaries manually.

## Logging / Diagnostics

Core should expose enough metadata to diagnose:

- input face count;
- island count;
- group count;
- raw used size;
- packed size;
- fill percent;
- overlap warnings;
- stack detections.

Do not print excessively inside tight loops. Return diagnostics when possible.
