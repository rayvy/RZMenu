# Radical GPU UI Architecture Plan

## 0. Short Verdict

The old static-buffer migration plan was directionally correct, but incomplete.
It treated the main problem as "INI is too large". The deeper problem is that
INI currently owns too much runtime behavior:

- per-element hitbox checks;
- immediate hover/click reaction;
- preset/helper expansion;
- slider math;
- value/action execution routing;
- repeated draw setup for things that are actually static.

The target architecture should make INI a thin orchestration layer. Most UI
state, layout, hit detection, draw expansion and interaction classification
should move into GPU buffers and compute passes.

The main risk is not buffers themselves. The main risk is custom formulas.
They must be isolated into a limited action/formula layer instead of being
allowed to block the whole migration.

## 1. Current Architecture

### Current Runtime Flow

```text
Per frame:
  INI CommandListElement_N
    -> restore variables
    -> compute position/size formulas
    -> run hover AABB checks
    -> run click/hold/slider logic
    -> write draw params through CustomShaderRCI2D
    -> draw_instancer consumes DataBuffer
```

### Current Buffers

- `DataBuffer`: final per-draw-element slots consumed by `draw_instancer.hlsl`.
- `IndexBuffer`: instance id -> DataBuffer offset.
- `ElementStaticMap`: static image/text/color by stable Blender element id.
- `ElementBlackList`: force static values back into DataBuffer.
- `ElementDefaultProps`: early visual defaults such as style/font/rotation.
- `ImagePoolBuffer` / `images.bin`: InstID -> atlas rect and image metadata.
- `AnimFramesBuffer`: animation frame InstID list.
- `StyleBuffer`, text buffers, font atlases.

### Current Pain

- Hit detection is repeated as INI `if $cursorX > ...` blocks.
- Interaction is immediate and local: each element both detects and reacts.
- Presets/helpers are expanded as generated CommandLists.
- `value_link_formula`, `transform_formula`, custom click/hover/hold formulas
  can execute arbitrary INI snippets, so they resist a pure buffer migration.
- The draw path and interaction path are mixed together.

## 2. Fundamental Constraints To Adopt

These constraints are good and should be made explicit.

### Preset / Helper Slot Limits

Each host element gets fixed slot budgets:

```text
underlayer presets: 5
normal presets:     5
helpers:            5
```

These are separate categories, not one shared sum.

This gives a fixed GPU layout:

```text
HostInstanceLinks:
  underlayer[5]
  preset[5]
  helper[5]
```

Fixed limits are not a weakness here. They make the buffer layout predictable,
the instancer simple, and the export validator strict.

### No Unlimited Runtime Formula Freedom In The Core Path

Custom formulas cannot remain arbitrary if the goal is GPU batching.
They must be classified:

- static formula: export-time resolved;
- action formula: executed by an action system after input classification;
- animation preset: GPU-known behavior with parameters;
- unsupported legacy formula: stays in INI fallback.

The migration should not wait until all formulas are translatable. It should
create a fast path and keep a compatibility path.

## 3. Target Architecture

### Desired Frame Flow

```text
Frame start:
  1. Init/refresh GPU state buffers.
  2. Layout pass computes final positions, sizes, visibility and draw rects.
  3. Hit detection pass classifies cursor/gamepad interaction.
  4. Optional tiny readback exposes only selected ids/events to INI.
  5. Action dispatch updates values/states.
  6. Draw pass renders all visible quads from buffers.
```

### Important Shift

Old model:

```text
element checks hitbox -> element immediately reacts
```

New model:

```text
GPU detects hit/capture/slider target -> action system reacts by id
```

This is the key conceptual change.

It enables:

- one batched hit detection pass;
- honest colliders, not just AABB;
- triangle/polygon hitboxes;
- accurate z/order priority;
- less repeated INI boilerplate;
- future gamepad/navigation improvements;
- cleaner separation between input classification and UI actions.

## 4. Readback Rule

GPU compute is useful. GPU readback is dangerous.

Use GPU readback only for tiny event/state payloads and only at controlled sync
points. The CPU should not read back big UI buffers.

Allowed readback payload:

```text
hovered_id
captured_id
click_trigger_id
active_slider_id
hit_kind
local_uv/progress
event_flags
mouse_buttons
```

Not allowed:

```text
full DataBuffer
all element positions
large collision lists
per-element debug state every frame
```

If readback is required, do it at the beginning of the next frame and treat it
as a one-frame-delayed event stream if necessary.

## 4.1. Fixed GPU Memory Rule

Do not design the core GPU path around smart dynamic allocation.

Dynamic allocation is useful on CPU, but it is a poor fit for predictable GPU
workloads. The core UI buffers should prefer fixed-size records, fixed slot
budgets and explicit flags. Unused capacity is acceptable if it removes
branches, reallocations and unpredictable memory layout.

Good GPU-side shape:

```text
one element -> one fixed record
one host    -> fixed preset/helper slots
one action  -> fixed descriptor
one collider -> fixed descriptor + optional fixed payload
```

Bad GPU-side shape:

```text
per-frame variable arrays
unbounded preset/helper lists
arbitrary formula blobs in the hot path
CPU-side rebuilds for small state changes
large readbacks to discover what happened
```

The price of this rule is hard limits and stricter validation. That is a good
tradeoff for this UI system.

## 5. New Core Buffers

### StaticElementBuffer

One record per logical element.

```text
id
parent_id / parent_buf_index
base_pos
base_size
base_color
base_image_inst
style_id
font_slot
flags
collider_type
action_id
```

### RuntimeElementBuffer

Mutable state.

```text
visibility
hover_amount
click_amount
captured
pressed
released
held
disabled
value
animated_pos/size
final_pos
final_size
final_alpha
```

This buffer should replace old scattered state variables such as `w23`, `z23`
and similar generated fields. The exact old names are not important; the
important part is that button/slider state becomes typed state, not anonymous
per-element INI variables.

### InputStateBuffer

Small global/per-device input state. Updated once per frame.

```text
cursor_pos
cursor_delta
mouse_down_mask
mouse_pressed_mask
mouse_released_mask
wheel_delta
modifiers
frame_index
time
dt
```

This is input classification data, not per-element behavior.

### ValueConstraintBuffer

One record per value-owning element or slider.

```text
value_id
min_value
max_value
step_value
increment_type:
  0 continuous
  1 integer step
  2 fixed decimal step
  3 enum/cycle
  4 logarithmic
default_value
flags
```

Sliders, steppers, toggles, cycles and HSV-like controls should consume this
instead of duplicating min/max/increment formulas in generated INI.

### InstanceLinkBuffer

Fixed visual expansion links.

```text
underlayer[5]
preset[5]
helper[5]
```

Each entry points to another element/static visual record or `-1`.

### ColliderBuffer

Collider data used by hit detection.

```text
collider_type:
  0 none
  1 rect
  2 rounded rect approximation
  3 circle/ellipse
  4 triangle
  5 convex polygon
```

For first implementation, support rect + triangle. More can come later.

### ActionBuffer

Action descriptors, not arbitrary INI snippets.

```text
action_id
action_type
target_value_id
param0..paramN
constraint_id
fallback_command_id
```

Action types:

- set toggle;
- cycle value;
- set slider progress;
- copy value;
- run legacy CommandList fallback;
- apply animation preset;
- open/close page/popup.

## 6. Presets, Helpers And Underlayers

### What Should Become Buffer-Driven

Visual expansion should move fully to buffers:

- underlayer presets;
- normal presets;
- helpers that are purely visual;
- helper positioning relative to host;
- inherited color/style/image where possible.

### What May Stay Legacy Initially

Functional helpers with custom formulas can stay as legacy action fallbacks.
They should be flagged as `LEGACY_FORMULA` or `LEGACY_COMMAND`.

This avoids blocking the visual buffer migration on the hardest cases.

## 7. Custom Formula Strategy

### Formula Categories

```text
STATIC
  Can be resolved at export time.

GPU_EXPR
  Small HLSL-like expression over known inputs:
  time, value, hover, click, local_uv, parent final rect.

ACTION_EXPR
  Runs only when an action fires, not every draw call.

LEGACY_INI
  Kept as generated INI fallback.
```

### Animation Presets

Many formulas should become animation presets:

- hover scale;
- hover color;
- pulse;
- rotate;
- value-driven position;
- value-driven alpha;
- click bounce;
- slider fill;
- page transition.

Preset = GPU-known opcode + parameters.

This removes a huge amount of custom formula need without pretending all
formulas can be compiled.

## 8. Safe Preparatory Changes

These are not radical. They can be done while preserving current behavior.

1. Introduce explicit `Action` objects.
   Existing `run_link`, `value_link`, click/hover/hold formulas are wrapped as
   actions, but still executed by current INI logic.

2. Add action ids to elements.
   No GPU behavior change yet.

3. Add preset/helper hard validation.
   Warn/error if more than 5 underlayers, 5 presets or 5 helpers are assigned.

4. Add export-time formula classifier.
   Only reports categories first. It does not change output.

5. Generate debug maps.
   Element id -> buffer index, element id -> action id, host -> preset/helper
   slot assignments.

6. Keep old hitboxes.
   The action wrapper can be adopted before GPU hit detection exists.

These steps are low-risk because the current INI execution model remains intact.

## 9. Medium-Risk Changes

These change internals but can still preserve the visible model.

1. Move preset/helper visual expansion into fixed buffers.
   Keep legacy CommandLists only for formula/action fallbacks.

2. Add `InstanceLinkBuffer` and expand draw_instancer to draw host + linked
   visuals in a fixed quad budget.

3. Add `StaticElementBuffer` and initialize more DataBuffer slots from it.

4. Add `PatchBuffer` / `slot_mask`.
   INI no longer writes full element state; it patches only changed slots.

5. Move hover interpolation and click interpolation into RuntimeElementBuffer.

These steps need visual regression tests but do not yet require a full input
architecture rewrite.

## 10. Radical Changes

These are architecture pivots.

1. GPU hit detection.
   A compute pass reads final rect/collider data and writes the best hit result.

2. Delayed/batched action dispatch.
   Elements no longer instantly react inside their own CommandList.
   The system reacts to a hit/action event stream.

3. GPU slider solving.
   Sliders compute progress from hit local coordinates, not from per-slider INI
   `if` blocks.

4. Layout propagation on GPU.
   Parent/child final position, visibility and alpha are resolved by compute.

5. Removal of most per-element CommandLists.
   INI keeps bindings, global variables, debug toggles and fallback actions.

6. Optional readback.
   Only a tiny event payload crosses from GPU to CPU/INI, if needed.

These are radical because they alter when and where behavior is computed.

## 11. Proposed Phase Chain

### Phase A: Action Abstraction

Goal: make "what happens on click/hover/hold" explicit.

- Add action ids and action descriptors.
- Map current button/slider/value_link/run_link behavior into actions.
- Keep current hitbox logic and current INI execution.
- Add QA that generated behavior is identical.

### Phase B: Formula Classification

Goal: stop treating all custom formulas as equal.

- Classify formulas as STATIC, GPU_EXPR, ACTION_EXPR, LEGACY_INI.
- Export a report.
- No behavior change yet.

### Phase C: Slot Limits And Instance Links

Goal: lock down preset/helper topology.

- Enforce 5 underlayer + 5 preset + 5 helper slots.
- Export `InstanceLinkBuffer`.
- Add debug dump.
- First keep old visual CommandLists.

### Phase D: Buffer-Driven Visual Expansion

Goal: draw presets/helpers/underlayers from buffers.

- Extend instancer to expand linked visuals.
- Keep functional helpers in legacy fallback.
- Remove generated visual-only preset/helper CommandLists.

### Phase E: Static And Runtime State Split

Goal: separate export-time element data from per-frame state.

- Add `StaticElementBuffer`.
- Add `RuntimeElementBuffer`.
- Add `PatchBuffer`.
- INI writes only patches.

### Phase F: GPU Layout Pass

Goal: compute final positions and visibility in buffers.

- Add parent index/toposort.
- Add final rect/alpha pass.
- Keep position formulas that are not classified as GPU-compatible in legacy.

### Phase G: GPU Hit Detection

Goal: replace per-element AABB INI checks.

- Start with rect colliders.
- Add triangle collider.
- Add z/order priority.
- Write tiny `InteractionResultBuffer`.

### Phase H: Batched Actions

Goal: make click/hold/slider update state through action dispatch.

- Convert button actions.
- Convert sliders.
- Convert vector box/HSV later.
- Legacy action fallback remains available.

### Phase I: Minimal INI

Goal: INI becomes orchestration and fallback only.

- Keybinds.
- Resource declarations.
- Global settings.
- Dispatch order.
- Legacy CommandList fallbacks.
- Debug controls.

## 12. What Not To Do Yet

- Do not move all formulas directly into HLSL at once.
- Do not remove per-element CommandLists before action abstraction exists.
- Do not use GPU readback for full UI state.
- Do not make preset/helper slots dynamic-sized in GPU buffers.
- Do not migrate Position/Size before layout and patch contracts are stable.

## 13. Practical Next Step

The next best safe step is Phase A:

```text
Action abstraction without changing hit detection.
```

That gives a bridge:

- today: INI hitbox -> action;
- later: GPU hit detection -> same action.

This prevents rewriting button/slider behavior twice.
