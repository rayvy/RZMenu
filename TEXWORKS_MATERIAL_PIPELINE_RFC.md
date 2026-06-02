# TexWorks Material Pipeline RFC

## Context

Current TexWorks is configured mostly as an RZMenu-side data model: blocks,
components, slots, decal layers, config buffers, and Jinja export glue. This is
powerful, but the authoring surface is detached from Blender's native material
workflow. The user has to describe texture behavior in RZMenu terms, then hope
the export path correctly maps that onto 3DMigoto resources.

The proposed direction is to invert that relationship:

> Author materials in Blender first, then make the export pipeline translate
> Blender material intent into 3DMigoto/TexWorks runtime behavior.

This document is not an implementation plan yet. It is a concept sketch and a
list of tradeoffs, risks, and questions.

## Core Idea

Use Blender materials as the primary authoring source for TexWorks.

Each material that participates in TexWorks would contain a dedicated RZMenu
node group, for example:

```text
RZM TexWorks Material
  Diffuse
  LightMap
  MaterialMap
  NormalMap
  GlowMap
  ExtraMap
  Condition / Driver expression
  Runtime mode / blend mode
```

The exact slots are game-dependent. For example, LightMap can be split into
ambient occlusion, shadow, emission mask, or game-specific channels during
export. The important part is that the node group gives RZMenu a stable
semantic interface to read.

## Proposed Pipeline

```text
Blender Materials
  -> MaterialCollector
  -> Material IR / Python Data Handler
  -> AtlasMerger
  -> Component-aware texture layout
  -> Jinja ini export
  -> TexWorks runtime command lists
```

### MaterialCollector

Reads Blender materials from export targets and extracts only supported RZMenu
nodes and inputs. It should not try to evaluate arbitrary shader graphs as a
renderer. Instead, it should extract declared intent:

- texture image sockets
- slot role: Diffuse, NormalMap, MaterialMap, LightMap, etc.
- optional condition variables such as `$Foo`, `@Bar`, `#Baz`
- blend mode
- channel mapping
- per-game mapping overrides
- material grouping keys
- atlas merge policy

The collector should produce a normalized intermediate representation, not
write ini directly.

### Material IR

The IR should be plain Python data suitable for Jinja and safe export caches.
Example shape:

```python
{
    "materials": [
        {
            "name": "CyberSpine",
            "source_material": "MAT_CyberSpine",
            "slots": {
                "Diffuse": {"image": "...", "uv": "UVMap"},
                "NormalMap": {"image": "...", "format": "normal"},
                "LightMap": {"image": "...", "channels": {"r": "ao", "g": "shadow"}}
            },
            "condition": "$CyberSpineEnabled",
            "blend": "replace",
            "dedupe_key": "..."
        }
    ]
}
```

This keeps the Jinja layer dumb: it receives already resolved resources,
conditions, atlases, hashes, and component routing.

### AtlasMerger

Atlas merging should happen before ini generation. The merger can run in
several modes:

- global atlas for the whole mod
- per component atlas
- per component plus shared atlas for duplicated textures
- no atlas, direct texture passthrough

The merger should understand:

- image deduplication by content hash
- material deduplication by semantic slot graph
- object/component boundaries
- UV remapping output
- game-specific texture format requirements
- DDS/PNG export policy
- dynamic separation by material

### Component-Aware Separation

One strong reason to move TexWorks closer to materials is dynamic separation.
Objects could be split during export by material assignment when needed:

```text
Object A
  material Body
  material CyberSpine

Export:
  Component Torso / material Body
  Component Torso / material CyberSpine
```

This is potentially valuable for:

- material-specific overrides
- atlas-level dedupe
- per-material toggles
- texture morphs
- conditional visibility
- avoiding manual duplicate objects

But it has risk: splitting changes buffer object ranges and can interfere with
shape key, weight, and component cache ownership. This needs a strict contract
with SafeExport and ComponentCollector.

## Runtime TexWorks Layer

The runtime ini layer should not know Blender material complexity. It should
receive clean component data:

- generated texture resources
- generated config resources
- command lists per material or material group
- conditional resource swaps
- atlas UV remap data
- texture slot assignment

Runtime should remain focused on:

- safe resource save/restore
- if/else condition handling
- dynamic texture swaps
- final texture binding
- avoiding duplicate work per frame

## Why This Is Better

- Blender material slots become the source of truth.
- Artists can inspect and organize materials in native Blender UI.
- Texture semantics live near texture assets, not in disconnected RZMenu lists.
- Discovery can rebuild TexWorks data after project migration.
- Material dedupe and atlas dedupe become more natural.
- Component-specific export can be derived from actual object/material usage.
- RZMenu can stop forcing users to think like 3DMigoto during authoring.

## Main Risks

### Blender Node Graphs Are Not Stable APIs

Arbitrary node graphs are too flexible. The system must not try to infer
meaning from any possible shader tree. It needs a dedicated RZMenu node group
with known socket names and versioned metadata.

### Node Group Versioning

The node group needs a schema version:

```text
rzm_texworks_schema = 1
```

Without versioning, old project materials will silently become ambiguous.

### Texture Evaluation Is Hard

If a socket is connected through color ramps, math nodes, mixes, drivers, or
procedurals, exporting an image is no longer a simple pointer read.

Possible rule:

- supported: Image Texture node directly connected to RZM slot input
- supported: constant values for scalar config
- supported later: small whitelist of math/mix nodes
- unsupported: arbitrary shader graph baking

### Atlas Remap Can Break Geometry Contracts

If the atlas merger modifies UVs, it must coordinate with:

- SafeExport mesh backups
- XXMI/EFMI export order
- shape key export buffers
- component cache
- material split objects

Atlas remap should probably happen in a temporary export state and be restored,
like SafeExport.

### Component Splitting Is Dangerous

Splitting by material can change:

- vertex order
- object ranges
- buffer offsets
- shape-key ownership
- weight buffer expectations
- draw call grouping

This must be designed as an explicit export mode, not a hidden side effect.

### Driver/Condition Syntax

The idea of requiring `$`, `@`, or `#` variables is good because it makes
runtime intent explicit. But the system needs validation:

- empty condition means always active
- strings with no variable prefix should warn
- invalid variable names should fail before export
- generated ini must not embed raw untrusted text without sanitation

### Cross-Game Slot Semantics

The same node socket may mean different things per game. For example LightMap
channels can map differently in ZZZ, GI, HSR, WW, or Endfield.

The collector should keep semantic names, then a game adapter should lower them
to concrete texture channels/resources.

## Questions

- Should material metadata live on the Material datablock, the RZM node group,
  or both?
- Should RZMenu create/update the node group automatically?
- Should the material collector ignore materials without the RZM node group?
- Should atlas merging be opt-in per material, per component, or global?
- Should dynamic material splitting happen before or after modifier application?
- How should this interact with shared mesh instances using different object
  params/modifiers?
- Can per-material component splitting preserve current component cache offsets,
  or does it require a new cache format?
- Should condition expressions be stored as socket string values, node labels,
  or custom properties?
- Should texture dedupe hash source image bytes, resolved exported bytes, or
  semantic material slot config?
- How much procedural node support is actually worth implementing?

## Suggested First Prototype

Keep the first prototype small:

1. Create a versioned `RZM TexWorks Material` node group.
2. Support direct Image Texture inputs only.
3. Read Diffuse, LightMap, MaterialMap, NormalMap.
4. Collect materials from selected/export objects.
5. Produce a debug JSON IR.
6. Do no atlas merge yet.
7. Generate the same style of TexWorks ini resources the current system expects.

Only after this works should atlas merging and dynamic material splitting be
added.

## Suggested Second Prototype

Add atlas merging, still without dynamic object splitting:

1. Dedupe images by content hash.
2. Pack per component atlas.
3. Temporarily remap UVs during SafeExport.
4. Export atlas textures.
5. Generate TexWorks resources from the atlas layout.
6. Validate that shape and weight export remain unchanged.

## Suggested Third Prototype

Add material-based separation as an explicit opt-in mode:

```text
RZM TexWorks Material -> Export Split Mode:
  None
  Split By Material
  Split By Material And Condition
```

This stage needs strong debug output:

- original object
- generated export object
- material
- component
- vertex count
- vb offset
- atlas slot
- generated resources

## Non-Goals For Now

- full procedural shader baking
- automatic interpretation of arbitrary Blender materials
- replacing all current TexWorks data structures immediately
- hidden material splitting during normal export
- changing shape key / weight export semantics as part of this RFC

## Bottom Line

The concept is stronger than the current authoring model, but only if it stays
strictly schema-driven. Blender materials should become the authoring source,
but the exporter must still produce a deterministic, boring IR before Jinja and
ini generation.

The highest-risk parts are atlas UV remapping and material-based object
splitting. The safest path is:

```text
Material node group -> collector -> debug IR -> current TexWorks ini
```

then add atlas merging, then add splitting.
