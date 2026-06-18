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
- one mesh vertex may be touched by faces with different materials;
- one face cannot have two Blender materials, so material ownership is face/loop based;
- one exported buffer vertex cannot hold two different runtime UV placements.

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

### Shared Exported Vertex Rule

If one buffer vertex is used by two materials requiring different TW placements, it must be duplicated before export or represented as two buffer vertices by the exporter.

Test expectation:
- If the exporter already duplicates material-boundary vertices, the post-patcher can patch each material's buffer indices independently.
- If it does not, TWAA must not silently patch the entire object as one material.
- Conflict handling is explicit:
  - safe path: skip the conflicting material slice and warn;
  - permissive/debug path: fall back to the legacy whole-object/object-range behavior only when the user opts in;
  - no hidden mesh splitting or destructive topology repair.
- Mesh preparation remains the user's responsibility. TWAA should report bad ownership clearly, not mutate the scene to rescue it.

### Export Strategy Decision

The MVP path is post-export material slicing. Temporary split-by-material is not the default plan because it requires extra depsgraph/object lifecycle churn and has a higher Blender crash risk.

#### A. Post-Export Per-Material Buffer Slice

After export, patch only vertices belonging to material-specific triangles.

Pros:
- avoids Blender depsgraph mutation during export;
- keeps authoring meshes untouched;
- works with the exporter's real buffer output instead of predicting object splits;
- naturally supports one Blender object with many materials when cache ownership is good.

Cons:
- requires exact material -> face/loop -> exported vertex mapping;
- must account for stride/layout from dump files;
- fails or falls back if the exporter does not duplicate material-boundary vertices;
- needs strong debug logs because bad cache ownership is otherwise visually confusing.

Decision:
- Use this as the first production direction.
- Extend export cache with `material_slices` / `vertex_indices_by_material`.
- Patch exact exported indices or compact index ranges, never infer multi-material ownership from the whole object range.
- Do not auto-split meshes for TWAA MVP.

#### B. Legacy / Fallback Whole-Object Patch

This is allowed only as a compatibility fallback for old scenes or intentionally loose debug exports.

Pros:
- keeps single-material objects working with the current cache format;
- gives users an escape hatch for poorly prepared meshes.

Cons:
- corrupt for mixed-material objects if used silently;
- may make UV placement visually wrong when one object owns multiple TWAA materials;
- cannot solve shared exported vertices that require two atlas placements.

Decision:
- Default: use whole-object range only when the object has exactly one active TWAA material.
- For mixed-material objects, require `material_slices`.
- If `material_slices` are missing, skip with a warning unless an explicit debug fallback is enabled.

#### C. Temporary Split By Material

Temporary split-by-material remains a possible rescue/prototype path, but not the main migration plan.

Reason:
- It can create reliable ownership, but it touches object/mesh/depsgraph state heavily.
- Frequent pointer churn inside one export frame is too risky for Blender stability.
- It also hides bad authoring/export topology instead of exposing the real ownership problem.

Decision:
- Keep it out of MVP.
- Reconsider only as an explicit user-run repair/export helper, never as hidden SafeExport behavior.

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

## Major Feature 2: Material-Level HSV

Purpose: allow each TWAA material/component to keep a dynamic HSV control without forcing the user to build manual TexWorks component variables.

### Authoring Surface

HSV is configured on the `RZM TexWorks Material` node group:

- `Use HSV`: boolean socket / checkbox.
- `HSV Base`: color/vector socket, default initialized color for the runtime variable.

The node group setting is the authoring source. TexWorks component fields are generated/synced data.

### Generated Runtime Variables

For every material with `Use HSV` enabled:

- create a stable variable stem from the material key, for example `RZ_TWAA_HSV_<MaterialKey>`;
- emit four component variables in J2:
  - `RZ_TWAA_HSV_<MaterialKey>_X`
  - `RZ_TWAA_HSV_<MaterialKey>_Y`
  - `RZ_TWAA_HSV_<MaterialKey>_Z`
  - `RZ_TWAA_HSV_<MaterialKey>_W`
- initialize them from `HSV Base`;
- bind the generated vector to the matching TexWorks component HSV fields.

### Sync Rules

When `bpy.ops.rzm.tw_mc_build_autoatlas_layout()` creates or refreshes TWAA blocks:

1. For every material marked `Use HSV`, add/keep HSV fields on the corresponding TexWorks component.
2. Enable HSV for that component.
3. Set `hsv_link` to the generated `RZ_TWAA_HSV_<MaterialKey>` stem.
4. Initialize `hsv_base` from the material node `HSV Base`.
5. Do not reset user-edited HSV runtime values during layout refresh unless the material explicitly disables HSV.
6. When `Use HSV` is disabled, keep stale generated data inert rather than deleting user-tuned variables immediately.

### Non-Goals For First HSV Pass

- no HSV mask workflow yet;
- no complex driver/live-preview graph;
- no per-decal HSV;
- no final atlas bake dependency.

## Major Feature 3: Final Atlas Bake

Purpose: collapse DynAtlas cluster PNGs into final DDS atlas underlays while keeping Blender materials and TexWorks components separated.

This is an optimization bake, not a destructive material merge.

### Revised Concept

- Blender materials are never merged by this stage.
- TexWorks components remain one-to-one with Blender materials.
- Each `RZAutoAtlas*` block becomes a static atlas texture underlay.
- Existing cluster PNGs are baked into the block atlas at TW component rects.
- Participating materials keep their component identity so a future mod update can add, remove, or repack clusters by rebuilding the layout.
- Dynamic per-component features, especially HSV, can stay live on top of the static baked underlay.

### HSV Rule

- Texture data can be baked into the static atlas for optimization.
- HSV stays dynamic per component/material.
- The bake must not collapse materials into one final material because HSV needs component identity.
- Material-level HSV is defined by Major Feature 2 and must continue to work after bake.

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
- post-export material-slice path with `vertex_indices_by_material`.
- post-export path with deliberately shared boundary vertices.
- legacy whole-object fallback explicitly enabled for a bad mixed-material mesh.

Expected:
- one cluster per Blender material;
- exact per-material buffer vertex indices or clear conflict warning;
- no whole-object patch when material count > 1.
- MVP material-slice path exports correct visuals when the exporter/cache provides distinct material-owned vertices.
- bad mixed-material ownership produces a warning/skip or explicit debug fallback, not silent corruption.

### Vertex Sharing Stress

- two materials sharing an edge.
- two materials sharing a vertex only.
- same geometry before and after triangulation.
- modifiers that duplicate/split topology.

Expected:
- if exporter duplicates material-boundary vertices, patch succeeds;
- if not, TWAA reports shared-vertex conflict and skips or uses explicit fallback instead of silently corrupting UV.

### Material HSV

- material with `Use HSV` disabled.
- material with `Use HSV` enabled and default `HSV Base`.
- layout rebuild after editing `HSV Base`.
- layout rebuild after user edits runtime HSV variables.
- disable `Use HSV` after variables already exist.

Expected:
- disabled materials emit no active HSV binding.
- enabled materials generate stable `_X/_Y/_Z/_W` variables.
- component `hsv_enabled`, `hsv_link`, and `hsv_base` sync from the material node.
- user-tuned runtime values are not wiped by layout refresh.
- disabling HSV makes stale generated data inert rather than destructively deleting it.

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
- Do not hidden-split authoring meshes during normal export.
- Do not use manifest groups in post-export patching.
- Do not round cluster image dimensions to 16; only round block atlas dimensions.
- Do not assume square atlas dimensions.
- Do not assume `TEXCOORD.xy` is always f32; use dump layout.
- Do not patch TEXCOORD1/TEXCOORD2 by default.
- Do not make final atlas bake destructive for material/component identity.
- Do not reset HSV masks or user HSV variables during TWAA layout refresh.

## Target Architecture

TWAA should become an automatic material atlas pipeline, not a manual TexWorks editor mode.

High-level flow:

```text
Imported / transferred asset
  -> Material schema detection
  -> Game texture-slot adapter
  -> Optional texture map remap/packing
  -> TWAA material cluster rebuild
  -> TWAA virtual atlas layout
  -> Export cache material slices
  -> TEXCOORD post patch
  -> TexWorks-compatible generated resources/J2
```

### Module Boundaries

- `utils/TWAA_CORE.py`
  - pure packing/UV/island/material-cluster algorithms;
  - no Blender data mutation;
  - no J2/ini emission.
- `utils/texworks_mc.py`
  - Blender material/node/faces/image IO bridge;
  - calls TWAA_CORE;
  - writes cluster PNGs and manifests;
  - syncs generated TWAA data into TexWorks blocks/components.
- `utils/twaa_texcoord_patcher.py`
  - reads export cache and dump layout;
  - patches only affine virtual-atlas placement;
  - uses `material_slices` when present;
  - legacy object-range fallback stays explicit.
- TWAA J2 module
  - emits generated variables/resources/commands from TWAA IR;
  - owns `RZ_TWAA_*` variables;
  - does not expose generated internals in normal TexWorks UI.

### Core Algorithm

1. Collect export candidates from the current export context.
2. Read only versioned `RZM TexWorks Material` node groups.
3. Resolve material slots through the current game adapter.
4. Build a material-first face inventory:
   - object name;
   - polygon index;
   - material slot;
   - material key;
   - UV layer;
   - area/density hints.
5. For each material key, build or update one material cluster.
6. Write cluster PNGs to `Textures/DynAtlas`.
7. Register cluster files as TWAA-managed source artifacts.
8. Build virtual atlas blocks per texture slot.
9. Sync one TexWorks component per Blender material.
10. Generate TWAA runtime IR:
    - resources;
    - block/component rects;
    - HSV variables;
    - material-slot routing;
    - debug report.
11. During export, cache material-owned buffer indices/ranges.
12. Post-export, patch TEXCOORD by exact material slice.
13. If material slice ownership is missing or ambiguous, skip/warn or use explicit fallback.

### User-Facing Philosophy

- Default workflow should be: bring an asset from another game, assign/repair material schema, rebuild, export.
- TWAA automates repetitive texture-slot mapping, cluster generation, atlas placement, and runtime binding.
- Manual work should be reserved for genuinely ambiguous artistic choices, not routine atlas bookkeeping.
- Destructive manual atlas authoring is avoided; DynAtlas files are intermediate authoring artifacts.
- The final game limitation of one texture slot per texture type is handled by virtual atlas placement, not by forcing the user to hand-merge source assets.

## Not Implemented Yet / Backlog

### Core Refactor Boundary

- `utils/TWAA_CORE.py` is the data-in/data-out home for UV grouping and rectangle packing.
- `utils/texworks_mc.py` must stay responsible for Blender IO only:
  - collect material/faces/images;
  - call TWAA_CORE;
  - raster/export PNGs;
  - write Blender/TexWorks data.
- Future packer changes must happen in TWAA_CORE first, then be wired through Blender-side tests.
- Core implementation prompt lives in `TWAA_CORE_CHATBOT_PROMPT.md`.

### Current Infrastructure Fixes

- Cluster collection must pass only polygons belonging to the active target material.
- Apply must copy preview UVs back to `TEXCOORD.xy` only for polygons belonging to that material.
- Multi-material meshes must be visible in logs through per-object face/material-slot stats.
- Cluster PNG canvas dimensions are padded, not rescaled, to Substance-compatible sizes:
  - 128
  - 256
  - 512
  - 1024
  - 2048
  - 4096
- If raw packed content exceeds 4096 on any side, fail loudly instead of silently clamping.

### Rebuild Quality

- Replace the current shelf/BSP MVP with a real bounded packer, probably MaxRects/Guillotine.
- If `core_input.object_face_stats` shows only target material faces, then texture/no-texture UV chaos is a TWAA_CORE algorithm bug, not Blender collection.
- If `core_input.object_face_stats` contains non-target material indices, fix Blender-side collection before touching TWAA_CORE.
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
  - use post-export per-material buffer slicing as the main path;
  - avoid hidden split-by-material temp export in normal SafeExport;
  - keep temporary split only as an explicit repair/prototype helper if ever needed.
- Required rule:
  - one Blender material = one TexWorks component;
  - multi-material meshes must not be patched as one whole object range.
- Need `material_slices` in export cache:
  - material key;
  - source object;
  - material slot;
  - exported vertex indices;
  - compacted exported vertex ranges;
  - optional index/triangle ranges for diagnostics.
- Need explicit conflict detection for shared exported vertices across material boundaries.
- Need skip/warn/debug-fallback behavior when ownership is ambiguous.

### Component Based Export

- Long-term goal: Component Manager can understand texture availability and material usage, not only object/component membership.
- It should be able to read:
  - which materials are used by each component;
  - which texture slots exist for each material;
  - which TWAA clusters/resources are generated or missing;
  - which game adapter is active.
- Manual mapping must be possible, but defaults should come from the selected game preset.
- Cross-game remap examples:
  - Genshin Impact asset -> Zenless Zone Zero texture slot/channel mapping;
  - PBR single-map workflow -> game-specific packed MaterialMap/LightMap channels;
  - separate Roughness/Metallic/AO maps -> packed runtime texture according to adapter rules.
- This is a later plan and should not block the current TWAA stabilization.

### Final Atlas Bake

- `Bake Current Atlas` is not implemented.
- This is a later plan until the authoring model is stable enough.
- Conceptual blockers:
  - Substance Painter roundtrip;
  - dynamic HSV;
  - planned decals;
  - Blender node/driver/live-preview organization.
- Required final bake steps:
  - stitch DynAtlas cluster PNGs into block atlas PNGs using TW block component rects;
  - convert via `texconv.exe`;
  - Diffuse -> BC7 SRGB;
  - LightMap/MaterialMap/NormalMap/ExtraMap -> BC7 Linear;
  - move final DDS to `./Textures/`;
  - register physical TexWorks resources;
  - keep Blender materials and TexWorks components separated.

### HSV Path

- Material node `Use HSV` flag is not implemented.
- Material node `HSV Base` socket is not implemented.
- TW component HSV fields are not generated from material settings yet.
- TWAA `_X/_Y/_Z/_W` variables are not emitted by J2 yet.
- HSV masks are out of scope for the first HSV pass.
- Final bake must preserve dynamic HSV components instead of destructively flattening everything.

### Substance Painter Bridge

- Current cluster sizes must stay Substance-friendly:
  - minimum practical cluster size: 256 unless a later bridge proves smaller textures are usable;
  - maximum practical cluster size: 4096 for normal workflow, with 8192 treated as heavy/exceptional if enabled.
- Need a bridge workflow to reduce manual repeated clicks:
  - export/update per-material DynAtlas PNG set;
  - detect changed files from Substance;
  - reimport or refresh Blender image nodes automatically;
  - keep TWAA material keys and file names stable;
  - rebuild only dirty materials when possible.
- Later bridge options:
  - watched folder refresh;
  - Substance project template naming convention;
  - one-click "Send To Substance" / "Refresh From Substance";
  - debug report listing changed slots/materials.
- This bridge is a workflow automation target, not a dependency for the first stable TWAA patcher.

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
