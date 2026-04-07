# Implementation Plan - In-Game Profile System

This plan finalizes the architecture for the **In-Game Profile** system, ensuring deep integration with the RZMenu data model and high-performance synchronization between Blender and the Qt Editor.

## User Review Required

> [!IMPORTANT]
> **Variable-Level Profiles**: Each variable (Value, Toggle, Shape) will now store its own set of default values for each in-game profile slot. This allows authors to define "Starting States" for specific profiles directly within the variable definitions.
>
> **Naming Consistency**: The system uses the term **In-Game Profile** to distinguish from "Build Profiles".
>
> **Safety**: All new properties are added as native RNA properties in `p_logic.py`, ensuring they are compatible with the existing Undo/Redo system and `PROP_MAP` paradigms.

## Proposed Changes

### 1. Core Data Model (`p_logic.py`)

#### [MODIFY] [data/p_logic.py](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/data/p_logic.py)
- **[NEW] `RZMVProfileValue`**: PropertyGroup containing a single `value: FloatProperty`.
- **`ValueProperty`**, **`ToggleDefinition`**, **`RZMShape`**:
    - Add `value_min`, `value_max` (Float).
    - Add `value_default` (Float).
    - Add `include_in_randomization` (Bool).
    - Add `in_game_profiles: CollectionProperty(type=RZMVProfileValue)` to store per-slot values.

### 2. Addon Configuration (`p_settings.py`)

#### [MODIFY] [data/p_settings.py](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/data/p_settings.py)
- Add `use_in_game_profiles` (Bool) and `in_game_profile_count` (Int) to `RZMenuAddonSettings`.
- Implement an update callback for `in_game_profile_count` that automatically resizes the `in_game_profiles` collections on all variables to match the new count.

### 3. Qt Editor Integration

#### [NEW] [qt_editor/widgets/in_game_profiles_tab.py](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/qt_editor/widgets/in_game_profiles_tab.py)
- A new tab in the Configurator for managing mod-wide variable states.
- High-density table/list showing all project variables.
- Columns for: Include in Random, Default, Min, Max, and Profile Slots (Slot 1, Slot 2, ...).

#### [MODIFY] [qt_editor/core/props.py](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/qt_editor/core/props.py)
- Implement `update_variable_property(var_type, index, prop_path, value)`: A centralized function that calls the corresponding Blender operators (`rzm.update_value`, `rzm.update_shape`, etc.) with correct pathing.

### 4. Template Engine (`rztemplate/`)

#### [MODIFY] [rztemplate/modules/data.j2](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/rztemplate/modules/data.j2)
- Inject `ResourceRZProfiles` buffer using the new `in_game_profiles` data.
- Size calculation: `(Total Vars) * (in_game_profile_count) * sizeof(float)`.

#### [MODIFY] [rztemplate/modules/core.j2](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/rztemplate/modules/core.j2)
- Update `CommandListRZRandomize` to use variable-specific `value_min` and `value_max` for randomization.
- Update `CommandListRZResetToDefault` to use `value_default`.

## Tracing & Compatibility

- **Pathing**: `rzm.rzm_values[i].in_game_profiles[j].value`.
- **Signals**: Updates will emit `signals.SIGNALS.data_changed` to ensure the Qt UI stays in sync.
- **Undo**: All changes wrapped in `safe_undo_push` via existing operators.

## Verification Plan

### Automated Tests
- Change `in_game_profile_count` in Blender and verify all values/toggles/shapes have the updated collection size.
- Export and verify the `[Constants]` default values match the Blender editor.

### Manual Verification
- In the Qt Editor, change a variable's `value_min` and verify it reflects in the Blender N-panel.
- Test the "Randomize" API in-game to ensure it stays within the new bounds.
