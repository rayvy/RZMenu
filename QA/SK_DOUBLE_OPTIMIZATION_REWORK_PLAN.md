# ShapeKey Double Optimization Rework Plan

## Goal

Move native ShapeKey runtime from full target-buffer dispatches to a grouped sparse system:

- one command path for up to 16 ShapeKey slots per component group;
- only `IniParams[24..27].xyzw` are used as slot inputs;
- animation parameters and slot behavior live in HLSL-readable resources, not in SKC ini math;
- position, weight morph, parent-chain, condition/fallback, override swap, ranges and anim modes remain supported;
- VFX path remains unchanged.

The new runtime should stop dispatching over the full component when only a small subset of vertices is affected.

## Current Problems

Current native position ShapeKeys:

- generate one full-size target buffer per shape;
- bind one shape at a time through `cs-t51`;
- pass one value through `x88`;
- dispatch over the whole component;
- compute `target - base` in shader every time.

Current native weight ShapeKeys:

- use the same one-shape-at-a-time pattern;
- dispatch over the whole VB2;
- repeat unpack, pool merge, top4 and normalize for every vertex;
- preserve parent behavior by binding parent buffer as `cs-t50`, but still with full buffers.

This is especially bad for animated shapes because the dispatch runs every frame even when only a few thousand vertices move.

## Target Runtime Model

### IniParams

Only these slots are reserved:

```ini
x24/y24/z24/w24 = slot 0..3 input
x25/y25/z25/w25 = slot 4..7 input
x26/y26/z26/w26 = slot 8..11 input
x27/y27/z27/w27 = slot 12..15 input
```

No `IniParams[28..63]` reservation is needed for SK.

The commandlist still owns high-level ini conditions:

- condition blocks;
- fallback value selection;
- override switch routing;
- disabled slot = input becomes `0`;
- raw linked variable selection.

The shader owns the per-slot behavior:

- input range remap;
- inverse;
- multiplier;
- animation mode;
- animation window;
- optional phase/time behavior;
- parent slot dependency;
- slot type flags.

### Resource Config

Each component group gets a config resource, for example:

```ini
[ResourceDataConfigSK_<Char>_<Comp>_G0]
type = Buffer
format = R32G32B32A32_UINT
array = 256
filename = ./SK/<Char>_<Comp>_G0_Config.buf
```

Fixed size: `256 * 16 = 4096 bytes` per 16-slot group.

Suggested layout:

```text
uint4[0..7]      Header / group metadata
uint4[8..135]    Slot descriptors, 16 slots * 8 uint4
uint4[136..199]  Animation descriptors, 16 slots * 4 uint4
uint4[200..215]  Slot execution order / parent links
uint4[216..255]  Reserve
```

Per-slot descriptor budget: `8 uint4 = 128 bytes`.

Per-slot animation descriptor budget: `4 uint4 = 64 bytes`.

Total per-slot budget with reserve: about `192 bytes`, plus group metadata. This is intentionally larger than needed so future modes do not require format churn.

### Slot Descriptor Fields

Exact bit packing can be finalized during implementation, but it should cover:

```text
slot_id
enabled
shape_kind: position / weight / both
anim_mode
input_mode
parent_slot
entry_start
entry_count
record_start
record_count
input_min
input_max
multiplier
fallback
inverse
flags
```

Float values can be stored as `asuint(float)` in `R32G32B32A32_UINT`.

### Sparse Position Data

Export no longer writes full target buffers for ShapeKeys.

Instead, per 16-slot group:

```ini
[ResourceDataSKPosRecords_<Char>_<Comp>_G0]
type = Buffer
format = R32G32B32A32_UINT
filename = ./SK/<Char>_<Comp>_G0_PosRecords.buf

[ResourceDataSKPosEntries_<Char>_<Comp>_G0]
type = Buffer
format = R32G32B32A32_UINT
filename = ./SK/<Char>_<Comp>_G0_PosEntries.buf
```

Record:

```text
uint4(vertex_id, entry_offset, entry_count, flags)
```

Entry:

```text
uint4(slot_id_and_flags, packed_half_dxdy, packed_half_dz_extra, reserved)
```

One shader thread processes one touched vertex record:

1. load base position;
2. loop through entries for that vertex;
3. compute final slot value from `IniParams[24..27]` + config;
4. accumulate all active deltas locally;
5. write final position once.

This avoids write races and avoids atomics for position.

### Sparse Weight Data

Do not create a separate shader file for weight SK. The single SK shader/module handles weight entries through flags and bound VB2 resources.

Weight data uses separate resources but the same grouped command path:

```ini
[ResourceDataSKWeightRecords_<Char>_<Comp>_G0]
type = Buffer
format = R32G32B32A32_UINT
filename = ./SK/<Char>_<Comp>_G0_WeightRecords.buf

[ResourceDataSKWeightEntries_<Char>_<Comp>_G0]
type = Buffer
format = R32G32B32A32_UINT
filename = ./SK/<Char>_<Comp>_G0_WeightEntries.buf
```

Weight entry must contain enough data to apply parent-relative morphing:

```text
slot_id
target packed weights/indices or target weight ref
parent packed weights/indices or parent weight ref
flags
```

The shader must preserve current semantics:

```text
current = current + (target - parent_or_base) * slot_value
top4 selection
normalize
pack back to VB2
```

The expensive part remains top4/normalize, but it only runs for touched vertices.

## Parent Chain and Slot Ordering

Slot order only matters when dependency exists.

Rules:

1. If a shape has no parent and is not used as parent by another shape, it can be placed anywhere.
2. If a shape has `parent_shape`, the parent must appear before the child in the same group or in an earlier dependency group.
3. If a parent and child affect the same component, prefer placing them in the same 16-slot group.
4. If the graph exceeds 16 slots, split by topological layers:
   - group 0 contains roots and early parents;
   - group 1 can depend on completed output of group 0;
   - later groups continue in order.
5. Cycles are invalid and should block export with a clear message.

Exporter must build a dependency graph:

```text
ShapeConfig.parent_shape -> ShapeConfig.shape_name
```

Then use stable topological sort:

1. parent depth ascending;
2. component relevance;
3. original config order as tie-breaker.

This keeps independent shapes predictable and dependent chains correct.

## SKC Feature Preservation Checklist

Every existing SKC behavior must be mapped before deleting old code.

### Existing ShapeConfig Fields

Must preserve:

- `shape_name`;
- `shape_type`: Linear / Anim;
- `condition`;
- `fallback_value`;
- `disable_export`;
- `export_runtime_disabled`;
- `bake_weights`;
- `parent_shape`;
- `input_range_min`;
- `input_range_max`;
- `inverse`;
- `multiplier`;
- `anim_type_index`;
- `anim_start_frame`;
- `anim_end_frame`;
- `override_switch_condition`;
- `override_switch_value_link`;
- `value_link`;
- profile override values;
- affected object discovery/runtime refs.

### New Responsibility Split

Commandlist keeps:

- whether slot is active this frame;
- condition wrapping;
- fallback branch;
- override switch branch;
- profile-level source value selection;
- assigning the final raw input to one of `xyzw24-27`.

Shader/config keeps:

- range remap;
- inverse;
- multiplier;
- anim type;
- anim start/end;
- parent slot id;
- shape kind flags;
- sparse buffer offsets/counts.

## Animation Migration

Phase 1 should support shader-side stateless animation first.

The commandlist passes a single raw input per slot:

```text
slot_input = linked variable after condition/fallback/override selection
```

The config tells the shader how to interpret it:

- Linear: remap input range, inverse, multiplier.
- Anim sine: use input as speed or intensity according to mode.
- Hammer: use shader-side mode constants.
- Double linear: use shader-side mode constants.

Important decision for implementation:

- If old exact `Freq += input * dt` behavior is required, add a small `RWBuffer` phase state resource and update it inside the same shader path or a tiny state section.
- If absolute-time animation is acceptable for first migration, avoid state resource in phase 1.

Do not keep generated SKC math blocks for animation after migration.

## Exporter Data Migration

### Position Packing

For every component and every active shape:

1. resolve affected objects using existing runtime export refs;
2. preserve current fast path mapping:
   - `v_map`;
   - KD fallback;
   - barycentric fallback;
   - mirror/invert X behavior;
3. compute delta against parent:
   - no parent: `shape - basis`;
   - parent: `shape - parent`;
4. filter vertices where `length(delta) <= epsilon`;
5. store sparse entries.

Recommended epsilon:

```text
position epsilon = 1e-7 for detection
optional quantization epsilon = half-float visible threshold after pack
```

### Weight Packing

For every `bake_weights` shape:

1. reuse current `blendworks_baker.pack_efmi_weights`;
2. generate packed target weights for the shape;
3. generate parent/base packed weights;
4. compare per vertex;
5. only store vertices where packed weights or indices differ;
6. record parent slot dependency.

Do not subtract raw packed bytes blindly if indices differ. Parent-relative weight morph must be semantic:

```text
unpack parent/base weights
unpack target weights
apply weighted blend in shader
top4 normalize
pack
```

## Shader Migration

Create one main SK HLSL module, for example:

```text
basic_pack/modules/rzm_shape_sparse.hlsl
```

It should replace/adapt:

- `position_shape_linear.hlsl`;
- `position_shape_linear_ENDFIELD.hlsl`;
- `position_shape_anim*.hlsl`;
- `position_shape_jiggle.hlsl` if still part of native SK path;
- `weight_shape_linear_ENDFIELD.hlsl`.

The old files can remain as compatibility fallback until the new template path is stable.

Shader entry behavior:

1. load group header;
2. load 16 slot inputs from `IniParams[24..27]`;
3. resolve final slot values from config;
4. process position records;
5. optionally process weight records;
6. write VB0/VB2 output buffers.

The shader should support no-op missing resources through config flags. If 3DMigoto binding requires real resources, exporter writes tiny empty buffers.

## Template Migration

Replace per-shape sections with per-component-group sections.

Old pattern:

```ini
cs = ./modules/position_shape_linear_ENDFIELD.hlsl
cs-u5 = copy Resource<Component>_Base
x88 = $SKC_Shape
cs-t50 = copy Resource<Component>_Base
cs-t51 = copy Resource<Component>_Shape
Dispatch = (vertex_count + 255) // 256, 1, 1
```

New pattern:

```ini
[CustomShaderComputeShapes.<Component>.G0]
cs = ./modules/rzm_shape_sparse.hlsl
cs-u5 = copy Resource<Component>_Base
cs-u6 = copy Resource<Component>_VB2_Base ; only if weight records exist
cs-t50 = ResourceDataConfigSK_<Component>_G0
cs-t51 = ResourceDataSKPosRecords_<Component>_G0
cs-t52 = ResourceDataSKPosEntries_<Component>_G0
cs-t53 = ResourceDataSKWeightRecords_<Component>_G0
cs-t54 = ResourceDataSKWeightEntries_<Component>_G0
x24/y24/z24/w24 = slot 0..3 raw inputs
x25/y25/z25/w25 = slot 4..7 raw inputs
x26/y26/z26/w26 = slot 8..11 raw inputs
x27/y27/z27/w27 = slot 12..15 raw inputs
Dispatch = (record_count + 255) // 256, 1, 1
```

If position and weight record counts differ, the shader can use two dispatch regions or one max-record dispatch with branch guards. Prefer one dispatch per group if practical.

## Phased Implementation Plan

### Phase 0 - Audit and Golden Baseline

- Generate current ini and SK buffers for at least one EFMI/Endfield test mod.
- Save counts:
  - component vertex count;
  - shape count;
  - anim shape count;
  - current SK buffer sizes;
  - current dispatch counts;
  - current generated ini SK sections.
- Pick one test case with:
  - one linear position SK;
  - one anim position SK;
  - parent-child shape;
  - one weight SK;
  - VFX tail present but untouched.

Exit criteria:

- reproducible current output exists;
- expected visual behavior is documented.

### Phase 1 - Ini Input Simplification

- Replace generated `x88` usage with slot assignment to `xyzw24-27`.
- Keep old full-buffer shader temporarily.
- Group up to 16 shapes per component but still dispatch old per-shape logic if needed.
- Move condition/fallback/override wrappers around slot input assignment.

Exit criteria:

- old visual behavior remains;
- `x88` is gone from native SK templates;
- each component has deterministic slot assignment.

### Phase 2 - Config Resource Writer

- Add exporter structure for `ResourceDataConfigSK_<Component>_G#`.
- Write 4096-byte config buffer per group.
- Include slot descriptors, anim descriptors, parent/order data.
- Add debug dump JSON next to buffers for inspection.

Exit criteria:

- generated config can be decoded by a small QA script;
- every ShapeConfig field has a mapped destination or an explicit commandlist responsibility.

### Phase 3 - Sparse Position Pack

- Replace full target position SK buffers with sparse records/entries.
- Reuse current Puppet Master matching:
  - exact v_map;
  - KD exact;
  - slow barycentric fallback.
- Export parent-relative deltas.
- Keep old full-buffer output behind a fallback/debug flag.

Exit criteria:

- sparse touched count matches expected changed vertices;
- no full-size position target buffers are required for new path;
- static linear shapes match old result.

### Phase 4 - Unified Sparse Position Shader

- Implement `rzm_shape_sparse.hlsl` position path.
- Read inputs from `IniParams[24..27]`.
- Read behavior from config resource.
- Dispatch by sparse record count.
- Write final VB0 once per touched vertex.

Exit criteria:

- linear position SK matches old output;
- multiple active slots accumulate correctly;
- overlapping slots do not race;
- VFX appended vertices remain untouched.

### Phase 5 - Shader-Side Animation

- Move range, inverse, multiplier and anim mode evaluation into HLSL.
- Remove generated SKC math blocks for anim.
- Keep commandlist only for raw input, condition, fallback and override route.
- Decide and implement either:
  - stateless absolute-time animation; or
  - stateful phase buffer for exact legacy speed behavior.

Exit criteria:

- existing anim modes are visually equivalent or documented as intentionally changed;
- animated shapes no longer dispatch full component;
- ini SK section size drops significantly.

### Phase 6 - Parent Chain Ordering

- Implement graph build and stable topological sort.
- Group parent and child slots together when possible.
- Split overflow chains into ordered groups.
- Add cycle detection with export error.

Exit criteria:

- parent-relative position shapes match old chain behavior;
- independent shapes preserve deterministic order;
- invalid cycles fail early.

### Phase 7 - Weight SK in Unified Shader

- Add sparse weight records/entries.
- Keep same HLSL file/module.
- Add config flags for weight records per slot.
- Reproduce current semantic merge:
  - unpack current/base/parent/target;
  - apply `(target - parent_or_base) * value`;
  - top4;
  - normalize;
  - pack VB2.

Exit criteria:

- one weight SK matches current `weight_shape_linear_ENDFIELD.hlsl`;
- parent weight chain matches current parent-buffer behavior;
- weight dispatch only touches changed vertices.

### Phase 8 - Template Cleanup and Compatibility

- Remove old native SK target-buffer generation from default path.
- Keep legacy mode behind a debug setting for one release cycle.
- Update templates:
  - `shapes_native.j2`;
  - `weights_native.j2`;
  - module includes/resources.
- Do not change VFX templates.

Exit criteria:

- no default native SK path writes full target buffers;
- no default native SK path uses `x88`;
- VFX output diff is empty.

### Phase 9 - QA and Metrics

For each test scene, report:

- old vs new SK buffer size;
- old vs new dispatch count;
- old vs new dispatched thread count;
- sparse touched vertices per slot;
- visual comparison notes.

Required stress case:

```text
500K vertices total mod
230K vertices largest component
2K touched vertices in animated shape
16 bound slots
```

Expected theoretical result:

```text
old threads for 16 shapes on 230K component: 3.68M/frame
new threads if 2K unique touched vertices: about 2K/frame
thread count reduction: about 1840x
```

Bandwidth reduction depends on final entry format, but should be roughly two orders of magnitude for sparse anim shapes.

## Open Decisions

1. Exact legacy anim phase or stateless shader time.
2. Whether one dispatch handles both position and weight records or the same shader module is dispatched twice with mode flags.
3. Final compact bit layout for slot descriptors.
4. Whether half-float position deltas are enough for every game path or a high-precision flag is needed per slot/group.
5. Whether sparse records should be per-group unique vertex records or per-slot records merged by shader. Prefer per-group unique vertex records to avoid races.

## Non-Goals

- No VFX rewrite.
- No unrelated component resolver rewrite.
- No UI redesign beyond exposing diagnostics/fallback toggles if needed.
- No removal of legacy shader files until the sparse path has passed QA.
