# 📘 RZMenu (RZM) Technical Documentation
**Version:** 4.0 (Public Beta)  
**Target:** 3DMigoto-Based UI Development Suite

---

## 1. Introduction
**RZMenu (RZM)** is an Integrated Development Environment (IDE) built as a Blender addon. It facilitates the creation of complex, interactive UI mods for 3DMigoto-supported games (Genshin Impact, Zenless Zone Zero, Arknights: Endfield, etc.).

### ⚙️ Core Concept
RZM acts as a **smart compiler**. Instead of manually writing 3DMigoto `.ini` files, you design the UI visually. RZM then "bakes" all logic, event listeners, and rendering instructions directly into the mod's configuration, resulting in a **zero-dependency** final output for the end player.

---

## 2. Installation & Environment
- **Addon Path:** Install via standard Blender Addon installation (`Edit > Preferences > Add-ons > Install`).
- **Dependencies:** 
    - **PySide6:** Required for the external Qt-based GUI.
    - **Pillow:** Required for image processing and previewing.
    - *Note: These are installed via the "Dependency Manager" panel in the Addon Preferences.*

---

## 3. Project Configuration
Before launching the editor, you must configure the environment in the Blender N-Panel (**RZ Constructor**):
1.  **Game Selection:** Choose the target environment (e.g., GIMI, ZZMI, EFMI).
2.  **Dump Path:** Path to the raw extracted game assets for reference.
3.  **Export Path:** The destination folder for the generated mod.

---

## 4. The Data System (Variables & Symbols)
RZM uses a symbolic system to manage data flow between the UI and the Game.

### 🔡 Symbol Reference
| Symbol | Usage | Description |
| :---: | :--- | :--- |
| `$` | **Variable** | standard logic variables (e.g., `$position`, `$alpha`). |
| `@` | **Toggle** | State-based variables with a defined fixed length (e.g., `@CharacterSelector`). |
| `#` | **Shape** | Used specifically for shapekey morphing and vertex-based animations. |
| `~` | **System** | Built-in macros for hierarchical data flow. |

### 🛠 System Variables (`~`)
- `~PV` (**Parent Value**): Automatically inherits the variable name from the immediate parent element.
- `~PVmin` / `~PVmax`: Inherits the minimum/maximum bounds from the parent's variable.

---

## 5. Visual Editor (qt_editor) Reference
The Qt-based interface is the primary workspace for UI design.

### 🖼 Workspace Layout
- **Outliner:** Manages the element hierarchy. Supports drag-and-drop parenting and visibility toggles.
- **Inspector:** The "Control Tower" for element properties (dimensions, colors, logic links, textures).
- **Asset Browser:** Registry for textures (.png, .dds, .svg) and pre-made snippets (.rzmt).
- **Variables Panel:** Global registry for all Toggles, Variables, and Shapes used in the project.

### 📐 Alignment Tools
Alignment is calculated based on groups.
- **Min. 2 items:** Horizontal/Vertical alignment.
- **Min. 3 items:** "Relax" modes (equal spacing between elements).

---

## 6. Element Class Reference

| Class | Profile | Use Case |
| :--- | :--- | :--- |
| **Anchor** | *The Foundation* | Recommended as the root of all other elements. It is draggable and handles relative positioning efficiently. |
| **Container** | *The Decorator* | A blank canvas with no logic. Use for background frames, decorative lines, or as a wrapper for scripts. |
| **Button** | *The Actor* | Primary interaction point. Includes pre-baked logic for hovering, clicking, and variable state switching. |
| **Slider** | *The Controller* | Returns a float value (0.0 - 1.0). Fully customizable; can be styled to look like simple bars or complex knobs. |
| **TEXT** | *The Interface* | Uses a specialized drawing engine for font rendering. Note: Text elements do not support standard image overlays. |
| **Grid Counter** | *The Auto-Layout* | (Experimental) Automatically sorts nested buttons or sliders into rows/columns. |

---

## 7. Logic & Interaction
### `+ Add Link`
Used to bind a UI element (like a Button) to a variable. When clicked/dragged, the element will update the linked variable state based on its configuration.

### 🧬 Presets & Helpers
- **Presets:** Elements marked as `is_preset` act as templates. Modifying the master preset updates all linked elements instantly.
- **Helpers:** Advanced presets that allow for complex formula-based logic. Useful for creating custom navigation (Arrows), specialized sliders, or triggered animations.

---

## 8. Shapekey Export System
RZM handles shapekey data through the `#Shape` variable system.
- **Implementation:** Linked to meshes in the Blender N-panel. 
- **Triggering:** A `#Shape` variable must be linked to a Button or Slider to be manipulated in-game.
- **Mode:** **Simple** is recommended for standard morphs. **Advanced** (experimental) supports complex animation pre-sets like Jiggle or Hummer effects.

---

## 9. Best Practices
- **Backups:** RZM is in Beta. Always maintain snapshots of your project.
- **Image Formats:** Use **.png** for general UI. **.dds** is supported but may encounter ICC profile issues in some environments.
- **Isolation Root:** Use the **Is Page** toggle in the Inspector to isolate a complex container. This improves performance and focus by hiding all non-relevant elements in the editor viewport.
- **Save Strategy:** Always save your project before closing the editor to commit modifications to the Blender data block.
