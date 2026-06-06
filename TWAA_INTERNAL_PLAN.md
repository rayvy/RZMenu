# TWAA Internal Plan

Working plan for TexWorks AutoAtlas / Material Combiner integration.

## Hard Rules

- Do not mix cluster rebuild with post-export runtime placement.
- Blender material equals TexWorks component.
- TexWorks block equals texture set / resource target, for example `RZAutoAtlasDiffuse`.
- TW Blocks are the source of truth for virtual atlas placement:
  - block resource size = virtual atlas size
  - component rect = material cluster placement inside that atlas
- Object custom properties are not TWAA source of truth.
- `RZM_EXPORT_*` object properties are debug/export-cache metadata only.
- Post-export buffer patching is affine only:
  - `u2 = u * scale_x + offset_x`
  - `v2 = v * scale_y + offset_y`
  - optional runtime buffer invert is applied only at write time
- Per-island/per-face packing belongs only to rebuild/apply/bake stages.

## Current Pipeline Split

### 1. Cluster Rebuild

Purpose: build one compact material cluster PNG set.

Input:
- Blender material.
- All mesh faces using that Blender material.
- `TEXCOORD.xy` or preview UV.
- Texture inputs or solid fallback colors.

Output:
- Flat files in `Textures/DynAtlas`, Substance-friendly:
  - `{MaterialName}Diffuse.png`
  - `{MaterialName}LightMap.png`
  - `{MaterialName}MaterialMap.png`
  - `{MaterialName}NormalMap.png`
  - `{MaterialName}ExtraMap.png`
- `RZAutoAtlas.{material_key}.manifest.json`.
- `RZAutoAtlas.UV.preview` before destructive Apply.

Allowed logic:
- per-face collection
- per-island detection
- stacked island grouping
- UV repack into compact cluster
- raster sampling / solid fallback generation

Forbidden here:
- writing final TW virtual atlas offsets into object properties as source of truth.

### 2. TWAA Layout Build

Purpose: pack already-built material clusters into TexWorks virtual atlas blocks.

Input:
- Registered MC file entries / exported PNG sizes.
- Material key per cluster.
- Texture slot availability.

Output:
- TW blocks named by slot:
  - `RZAutoAtlasDiffuse`
  - `RZAutoAtlasLightMap`
  - `RZAutoAtlasMaterialMap`
  - `RZAutoAtlasNormalMap`
  - `RZAutoAtlasExtraMap`
- One TexWorks component per Blender material in each applicable block.
- Atlas size rounded to multiple of 16.
- Cluster sizes are not rounded, only the final atlas size is rounded.

Rule:
- One Blender material = one TexWorks component.

### 3. Post-Export Runtime Placement

Purpose: patch exported `Texcoord.buf` so runtime samples the TW virtual atlas.

Input:
- Export cache vertex ranges / future material-specific vertex indices.
- TW Blocks placement.
- Addon post patch settings.
- Dump layout files from `xxmi.dump_path` for exact TEXCOORD format and offset.

Output:
- Patched exported `*Texcoord.buf`.

Allowed logic:
- pick the correct TEXCOORD payload.
- apply affine placement from TW Blocks.

Forbidden here:
- reading TWAA object props.
- reading manifest groups for geometry remap.
- per-island/per-vertex group selection.
- clamp/fract as hidden geometry logic.

## Major Feature 1: Multi-Object / Multi-Material Bake and Pack

### Problem

Current simple path works when an exported object range maps to one material cluster.

Multi-material objects are harder:
- one Blender object can contain polygons with several material slots;
- one exported component can contain many Blender objects;
- vertices may be shared between faces with different materials;
- a single shared buffer vertex cannot hold two different runtime UV placements.

### Required Model

Collection must be material-first, not object-first:

1. Scan export candidates.
2. For each mesh polygon, resolve Blender material slot.
3. Group faces by Blender material key.
4. Build one cluster per material key across all objects using that material.
5. Build TW Blocks from exported cluster files.
6. During post-export patch, patch only buffer vertices that belong to faces using that material.

### Export Cache Requirement

Object-level contiguous `vb_offset/vb_count` is enough only for single-material objects.

For multi-material objects we need one of:

- Preferred: `vertex_indices_by_material`.
  - map material key or material slot index to exact buffer vertex indices;
  - can be compacted into ranges for logs/performance.
- Acceptable fallback: per-material contiguous ranges if exporter already splits material submeshes.
- Unsafe fallback: whole object range. Use only when object has exactly one material.

### Shared Vertex Rule

If one buffer vertex is used by two materials requiring different TW placements, it must be duplicated before export or represented as two buffer vertices by the exporter.

Test expectation:
- If exporter/material split already duplicates vertices, post-patcher can patch each material's buffer indices independently.
- If it does not, TWAA must report a conflict and refuse affine patch for that object/material combination.

### Export Strategy Decision

There are two viable implementation paths.

#### A. Temporary Separate By Material

Before export, create temporary export meshes split by material.

Pros:
- reliable material-to-buffer ownership;
- each exported mesh/range can be patched as a single material cluster;
- avoids shared-vertex UV conflicts;
- easiest path for MVP and hard testing.

Cons:
- slower export;
- requires careful temporary object lifecycle;
- must be written without depsgraph side effects or persistent scene damage.

Decision:
- Use this as the first robust implementation for multi-material meshes.
- Never destructively split the user's authoring mesh.
- Temporary split output must be cleaned/restored like SafeExport helper objects.

#### B. Post-Export Per-Material Buffer Split

After export, patch only vertices belonging to material-specific triangles.

Pros:
- faster in the long term;
- avoids Blender depsgraph mutation during export.

Cons:
- requires exact material -> triangle -> exported vertex mapping;
- must account for stride/layout from dump files;
- fails if exporter does not duplicate material-boundary vertices;
- high risk of partial-face/interpolation artifacts without strict validation.

Decision:
- Do not use this as the MVP path.
- Implement later only after export cache stores exact `vertex_indices_by_material` or equivalent validated ranges.
- If shared vertices are detected, fail loudly instead of trying to patch ambiguous data.

### Rebuild Stage Behavior

Cluster rebuild can still work per-face:
- faces are collected by material;
- islands can split naturally without manual seams;
- triangulation must not change orientation because rebuild writes preview/local cluster UV, not runtime atlas UV.

### No-Texture / No-Color Packing Heuristic

When a material has no usable texture and no meaningful configured color:

- do not allocate equal pixel space blindly;
- estimate useful space from geometry contribution;
- larger visible surface area receives more cluster space;
- small accessories receive proportionally less space.

Example intent:
- shirt-like large surface: about 70% of the material cluster budget;
- crown-like medium detail: about 28%;
- ring-like tiny accessory: about 2%.

Implementation direction:
- compute per-island or per-face 3D surface area in object/world space;
- use that as packing weight when no source texture density exists;
- keep hard minimum dimensions so tiny islands remain editable;
- still preserve stacked islands when their UV/source-space overlap is intentional.

This heuristic is only for texture-less fallback rebuild. Real texture inputs keep texture-density based sizing.

## Major Feature 2: Final Atlas Bake

Purpose: collapse DynAtlas cluster PNGs into final DDS atlas underlays while keeping Blender materials and TexWorks components separated.

This is an optimization bake, not a destructive material merge.

### Revised Concept

- Blender materials are never merged by this stage.
- TexWorks components remain one-to-one with Blender materials.
- Each `RZAutoAtlas*` block becomes a static atlas texture underlay.
- Existing cluster PNGs are baked into the block atlas at TW component rects.
- Participating materials keep their component identity so a future mod update can add, remove, or repack clusters by rebuilding the layout.
- Dynamic per-component features, especially HSV, can stay live on top of the static baked underlay.

### HSV Extension

Materials can be marked as `has HSV`.

When `bpy.ops.rzm.tw_mc_build_autoatlas_layout()` creates or refreshes TWAA blocks:

1. For every material/component marked `has HSV`, add/keep HSV fields on the corresponding TexWorks component.
2. Enable HSV for that component.
3. Optionally attach an HSV mask slot/resource.
4. Do not reset existing HSV mask data during layout refresh.
5. Do not wipe user-edited HSV variables during layout refresh unless the material explicitly disables HSV.

Rule:
- Texture data can be baked into the static atlas for optimization.
- HSV stays dynamic per component/material.
- The bake must not collapse materials into one final material because HSV needs component identity.

### Pipeline

1. Read TW Blocks source of truth.
2. For each block/texture set:
   - create a blank atlas of `block_resource_size`;
   - paste each component's cluster PNG into `component.rect`;
   - no extra margin between components unless explicitly configured later.
3. Export stitched atlas PNG as temporary/intermediate.
4. Convert via `texconv.exe`:
   - Diffuse -> BC7 SRGB
   - all other slots -> BC7 Linear
5. Move final DDS files to `./Textures/`.
6. Register or update physical TexWorks resources for the baked block atlas textures.
7. Repoint participating TWAA blocks/resources to the baked physical atlas underlay.
8. Keep all participating Blender materials/TexWorks components separated.
9. Leave non-participating TexWorks data untouched.

### Non-Destructive Authoring Rule

The DynAtlas cluster PNGs remain the authoring/intermediate layer:

- Substance Painter workflow can keep using separated `{MaterialName}{TextureSet}.png`.
- Final DDS bake is a build artifact.
- Rebuilding layout or cluster PNGs invalidates the final baked atlas until `Bake Current Atlas` is run again.

### Resource Naming

Keep dotless resource names for 3DMigoto variable compatibility:

- `RZAutoAtlasDiffuse`
- `RZAutoAtlasLightMap`
- `RZAutoAtlasMaterialMap`
- `RZAutoAtlasNormalMap`
- `RZAutoAtlasExtraMap`

## Minor Features

### Quick Apply Existing TW Clusters

Add a toolbox button near `bpy.ops.rzm.copy_tex_slots_to_selected()`.

Behavior:
- apply only existing block resources;
- do not create phantom `ResourceRZAutoAtlas*`;
- use TW Blocks and registered cluster files;
- intended as a convenience operator for already-built layout.

### Fill To Square UV Operator

Add to UV Editor.

Behavior:
- scale selected UV bounds to fill a square target area;
- preserve orientation;
- no rotation;
- useful before cluster rebuild when the user wants manual cleanup.

### NormalMap Fallback Color

Default normal map solid color must be:

```text
0.5, 0.5, 1.0, 1.0
```

### TWAA Material Selection Helpers

Add TWAA panel controls for debugging material coverage:

- Select objects using one registered material/component.
- Select all objects using any registered TWAA material.
- Show active/inactive counts:
  - active = mesh object using the material and present in the current export collection/view-layer context;
  - inactive = mesh object using the material but not currently part of that export context.

This is only a UI/debug helper. It must not become source of truth for export placement.

## Tests To Run

### Single Material

- one object, one material, solid colors only.
- one object, one material, real Diffuse only.
- one object, one material, Diffuse + LightMap + NormalMap with mixed resolutions.
- multiple objects using the same material.

Expected:
- one material cluster;
- one TexWorks component per block;
- affine post-export placement only;
- no diagonal distortion.

### Multi-Material Object

- one quad object, two materials, each material on one triangle.
- one triangulated object, two materials.
- one object with 3-8 material slots.
- one material reused on multiple objects and also inside a multi-material object.
- temporary separate-by-material export path.
- post-export path with deliberately shared boundary vertices.

Expected:
- one cluster per Blender material;
- exact per-material buffer vertex indices or clear conflict warning;
- no whole-object patch when material count > 1.
- MVP separate-by-material path exports correct visuals even when authoring mesh has many materials.

### Vertex Sharing Stress

- two materials sharing an edge.
- two materials sharing a vertex only.
- same geometry before and after triangulation.
- modifiers that duplicate/split topology.

Expected:
- if exporter duplicates material-boundary vertices, patch succeeds;
- if not, TWAA reports shared-vertex conflict instead of corrupting UV.

### Runtime Patch

- compare with `TW MC Post Buffer Patch` disabled/enabled.
- test `invert_y` on and off.
- test only `TEXCOORD0`.
- debug-only test with all TEXCOORD payloads.

Expected:
- default patches only primary `TEXCOORD.xy`;
- secondary payload patching stays opt-in debug.

### Final Atlas Bake

- bake only Diffuse.
- bake Diffuse + LightMap + NormalMap.
- bake materials with missing slots.
- bake non-square virtual atlas.
- bake materials with HSV enabled and verify HSV remains dynamic.
- rebuild layout after adding one new material cluster and verify previous components keep identity.
- verify DDS format and path registration.

Expected:
- Diffuse BC7 SRGB;
- non-Diffuse BC7 Linear;
- final physical resources registered;
- materials/components are not merged;
- HSV component state is preserved;
- DynAtlas cluster files can remain as intermediate authoring data.

## Known Pitfalls

- Do not patch whole object ranges when object has multiple material slots.
- Do not infer runtime placement from object custom props.
- Do not rebuild TWAA layout automatically during SafeExport.
- Do not use manifest groups in post-export patching.
- Do not round cluster image dimensions to 16; only round block atlas dimensions.
- Do not assume square atlas dimensions.
- Do not assume `TEXCOORD.xy` is always f32; use dump layout.
- Do not patch TEXCOORD1/TEXCOORD2 by default.
- Do not make final atlas bake destructive for material/component identity.
- Do not reset HSV masks or user HSV variables during TWAA layout refresh.

## Not Implemented Yet / Backlog

### Core Refactor Boundary

- `utils/TWAA_CORE.py` is the data-in/data-out home for UV grouping and rectangle packing.
- `utils/texworks_mc.py` must stay responsible for Blender IO only:
  - collect material/faces/images;
  - call TWAA_CORE;
  - raster/export PNGs;
  - write Blender/TexWorks data.
- Future packer changes must happen in TWAA_CORE first, then be wired through Blender-side tests.

### Rebuild Quality

- Replace the current shelf/BSP MVP with a real bounded packer, probably MaxRects/Guillotine.
- Texture rebuild mode still needs real-scene validation on:
  - `TEST_CLUSTERS0`
  - `TEST_CLUSTERS1`
  - `TEST_CLUSTERS2`
  - `TEST_CLUSTERS3`
- No-texture dense mode still needs real-scene validation on:
  - `TEST_CLUSTERS_NOTEX0`
  - `TEST_CLUSTERS_NOTEX1`
  - `TEST_CLUSTERS_NOTEX2`
  - `TEST_CLUSTERS_NOTEX3`
- 90-degree UV island rotation is not implemented.
- Overlap detection is not exposed as a Blender UI/debug report.
- Preview UV visual output can still differ from exported PNG evaluation and needs a reliable compare tool.

### Multi-Material Meshes

- Multi-material object handling is not production-ready.
- MVP decision still needs implementation:
  - use separate-by-material temp export path first for reliability;
  - keep post-export per-material mesh slicing as a later optimization.
- Required rule:
  - one Blender material = one TexWorks component;
  - multi-material meshes must not be patched as one whole object range.
- Need explicit conflict detection for shared exported vertices across material boundaries.
- Need per-material exported vertex range/cache data before post-export patching can be trusted on mixed-material meshes.

### Final Atlas Bake

- `Bake Current Atlas` is not implemented.
- Required final bake steps:
  - stitch DynAtlas cluster PNGs into block atlas PNGs using TW block component rects;
  - convert via `texconv.exe`;
  - Diffuse -> BC7 SRGB;
  - LightMap/MaterialMap/NormalMap/ExtraMap -> BC7 Linear;
  - move final DDS to `./Textures/`;
  - register physical TexWorks resources;
  - keep Blender materials and TexWorks components separated.

### HSV Path

- Material/component `has HSV` flag is not implemented.
- TW component HSV variables are not generated yet.
- HSV masks must not be reset during layout rebuild.
- Final bake must preserve dynamic HSV components instead of destructively flattening everything.

### Performance

- Large image export is still too slow for production use.
- Need profiling around:
  - Blender image pixel reads;
  - NumPy raster path;
  - PNG save/reload;
  - texture node relinking during Apply.
- Solid-color outputs should use direct fast-fill and avoid slow per-pixel paths.

### UI / Workflow

- TWAA material active/inactive selection helpers exist only as rough debug UI.
- Need a single clear operator flow:
  - Rebuild = rebuild cluster and export PNGs;
  - Export = only appears/used for preview re-export;
  - Apply = destructive preview UV + texture path apply.
- Need a UI report showing:
  - material/component;
  - cluster PNG size;
  - TW block;
  - component rect;
  - final affine post-export transform.

### Runtime Patch

- Post-export patch currently depends on dump layout parsing and needs broader validation.
- Need repeatable visual tests for:
  - `TEXCOORD.xy` f16;
  - `TEXCOORD.xy` f32;
  - non-square atlases;
  - invert_y on/off;
  - patch disabled/enabled.
- `TEXCOORD1`/`TEXCOORD2` patching must remain debug-only until proven necessary.
