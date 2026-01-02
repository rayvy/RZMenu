# RZM (RZMenu)

![Version](https://img.shields.io/badge/version-3.1-blueviolet)
![Blender](https://img.shields.io/badge/Blender-4.0%2B-orange)
![Output](https://img.shields.io/badge/Output-Standalone_%2F_Zero_Dep-success)
![Target](https://img.shields.io/badge/Target-Genshin_%7C_HSR_%7C_ZZZ_%7C_WuWa-green)

**The ultimate Integrated Development Environment (IDE) for 3DMigoto-based UI modding, running natively inside Blender.**

---

## 🌌 Introduction

**RZMenu (RZM)** is a specialized **development suite** designed to revolutionize how UI mods are created for anime-style rendering games.

Unlike traditional methods that require manual config editing or external runtime libraries, RZM acts as a **smart compiler**. It takes high-level visual concepts (Qt widgets, nodes) and **injects** all necessary logic directly into the mod's native `.ini` files.

**The result?** A complex, feature-rich mod that requires **zero extra steps** for the end user.

**What does "RZ" stand for?**
* **R** — Rayvich (Me, Author, coder, but mostly vibe-coder)
* **Z** — Zlevir (Original inspiration & legacy tribute)

---

## 🚀 Key Features

RZM is built on a "One-Click" philosophy: complex under the hood, simple on the surface.

### 🎨 The Visual Editor (Qt Engine)
RZM launches a custom **PySide6** window that acts as a bridge between you and the raw code:
* **WYSIWYG Interface:** Drag-and-drop elements, resize handles, and alignment tools.
* **Hierarchy Management:** Dedicated Outliner for UI elements.
* **Inspector:** Real-time property editing.
* **Theme Engine:** Customizable workspace themes (Frutiger Aero included!).

### ⚡ Smart Compilation (The Magic)
* **Direct Injection:** The tool automatically generates and embeds all logic into the `.ini` file.
* **No Dependencies:** The final mod does not require the player to install RZM, python libraries, or any third-party loaders. It just works.
* **Autopilot Mode:** Automated generation for standard menu setups — from zero to working mod in seconds.

### 🛠 Advanced Tooling
* **Shader Snippets:** Pre-baked advanced effects (Trails, Texture Morphing, runtime Color Management).
* **Image Capture:** Auto-render blender scenes and inject them directly into the `.blend` file storage.
* **Seamless Integration:** Designed to work alongside **XXMI** for a unified export pipeline.

---

## 🏗 Architecture

RZM 3.1 utilizes a robust **Event-Driven MVC (Model-View-Controller)** architecture to manage the complexity of UI generation.

### The Stack
* **Language:** Pure Python 3.11 (Embedded in Blender).
* **GUI Library:** PySide 6.10.1 (Qt for Python).
* **Core:** Custom logic generator that translates Python objects into 3DMigoto configuration.

### Data Flow
1.  **Model:** Blender Scene holds the "Source of Truth" in `bpy.scene_data`.
2.  **View:** The PySide6 Editor allows visual manipulation of this data.
3.  **Compiler:** Upon export, the system serializes the data and "bakes" it into the final mod format.

```mermaid
graph TD
    User[User Interaction] -->|Visual Edit| Qt[Qt Editor]
    Qt -->|Update| Blender[Blender Data]
    Blender -->|One-Click Export| Compiler[Logic Compiler]
    Compiler -->|Inject| Ini[.ini Config File]
    Ini -->|Play| Game[Game Runtime (Zero Deps)]
📦 Installation
RZM is designed to be effortless.

Download the latest release .zip.

Open Blender -> Edit -> Preferences -> Add-ons.

Click Install... and select the zip file.

Enable the addon.

RZM automatically handles environment setup and PySide6 dependencies.

🖼 Gallery
The Qt Editor
[Insert Screenshot of your custom PySide Window here]

The Workflow
[Insert Screenshot showing the 'Autopilot' or Export process]

🤝 Credits & Acknowledgements
Rayvich: Core Architect, UI/UX Design, Python Engineering.

Zlevir: For the original concept and permission that started this journey.

Community: The 100k+ modding community for feedback and testing.

Project is currently in active development (v3.1 Beta).


### Что изменилось:
* **Badge:** Добавил `Output: Standalone / Zero Dep`. Это сразу говорит технарям: "О, мне не нужно будет объяснять юзерам, как ставить библиотеки".
* **Smart Compilation:** Теперь это ключевое описание. Ты "компилируешь" сложное в простое.
* **Direct Injection:** Описал процесс как "Встраивание", а не использование API.

Теперь это звучит как мощный, профессиональный инструмент, который уважает время и созда
