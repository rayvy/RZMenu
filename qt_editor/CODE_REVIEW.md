# Code Review & Technical Debt Report

This document tracks technical debt, architectural issues, and "dirty hacks" identified in the codebase.

## 🔴 Critical Issues

### 1. Destructive UI Updates (Focus Loss)
**File:** `widgets/configurator.py`, `widgets/variables_panel.py`
**Problem:** `update_ui` methods call `_clear_layout` and rebuild the entire interface on every `data_changed` signal.
**Impact:**
- **Focus Loss:** Typing in a text field triggers an update, which destroys the text field, causing the user to lose focus and input state.
- **Performance:** Recreating widgets (allocating memory, signals) is expensive for 60fps interaction.
- **State Loss:** Scroll positions, collapsed headers, and selection states may reset unexpectedly.
**Recommendation:** Implement "Stateful UI Updates".
- Iterate over existing widgets and properties.
- Only update values (`setText`, `setValue`) if they differ.
- Only add/remove widgets if the underlying list size changes.
- Use `QDataWidgetMapper` or keyed widget caching.

### 2. ActionManager Injection
**File:** `systems/actions.py` (and usage in Window)
**Problem:** `RZActionManager` often requires direct access to `window` or specific contexts, leading to circular dependencies or "injection" hacks like `ctx.window = self.window`.
**Recommendation:** Decouple Actions from the UI implementation. Use signals or a command pattern where the context is passed purely as data, not UI objects.

### 3. PROP_MAP Validation
**File:** `core/props.py`
**Problem:** `PROP_MAP` is the single source of truth. If a property is missing here, the UI will silently fail to write data.
**Recommendation:** Add a startup check that validates `PROP_MAP` keys against the actual Blender RNA properties of `RZElement`, logging warnings for mismatches.

## 🟠 Medium Priority

### 4. Global Signal Scope ("Shotgun Updates")
**File:** `core/signals.py`
**Problem:** `SIGNALS.data_changed` is global. Changing a single boolean in the Configurator triggers a refresh of the Outliner, Viewport, and Inspector.
**Recommendation:** Implement granular signals (e.g., `item_changed(uid)`, `config_changed(section)`).

### 5. Parent Traversal for Context
**File:** `widgets/panel_base.py`, `widgets/viewport.py`
**Problem:** Widgets often hunt for `RZContextManager` or `ActionManager` by traversing `parent()` calls or importing singletons.
**Recommendation:** Use strict Dependency Injection or a Service Locator pattern initialized at the root `RZMEditorWindow`.

### 6. Automatic Operator Registration
**File:** `systems/operators.py`
**Problem:** Manual list usage for registration (`_CLASSES`). Easy to forget new operators.
**Recommendation:** Use `inspect` to auto-discover `RZOperator` subclasses in the module.

## 🟢 Implementation Details / Minor

### 7. "Polish" Hack for Styles
**File:** `widgets/outliner.py`
**Problem:** calling `unpolish`/`polish` to force style updates.
**Status:** Acceptable. This is a standard workaround in Qt for dynamic property styling.

### 8. Type Hinting
**File:** Project-wide
**Problem:** Missing type hints in many core functions.
**Recommendation:** Add `typing` annotations to `core/logic.py` and `context` modules first.

## ✅ Fixed / Improved

- **Viewport Coordinates:** `viewport.py` now consistently uses `core.to_qt_coords` and `to_blender_delta`. The coordinate logic seems centralized.

