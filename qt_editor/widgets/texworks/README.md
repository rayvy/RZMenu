# TexWorks Modular Package (Experimental)

State as of March 10, 2026.

## Current Setup
- **Primary Widget**: `qt_editor/widgets/texworks_panel.py` (Stable, Legacy).
- **Experimental Widget**: `qt_editor/widgets/texworks/` (Modular package, Registered as `TexWorks (Test)`).

## Work Completed
- [x] Full refactor into a python package (`panel.py`, `tabs.py`, `utils.py`).
- [x] Modular tab system (Main, Resources, Overrides, Materials, Test, Test-Slots).
- [x] Recursive `.png` scanning in `TexWorks/` mod subfolder for decals.
- [x] Asynchronous thumbnail loading for file system items.
- [x] Memory-based thumbnail caching.
- [x] Enhanced Main Tab with Backdrop/Base/Morph previews and Total Block composite.
- [x] Improved DDS format detection and 4-color grid placeholders (BC5 support).
- [x] Intelligent path resolution (checks mod root and `Textures/` folder).

## Known Bugs (TexWorks Test)
- **Floating Windows**: Some buttons or sections may still detach from the main UI (Partially fixed by parenting `RZGroupBox` and `RZTabRow` items).
- **Black Previews**: Thumbnails on the Resources tab are sometimes black even when the path is correctly resolved.
- **UI Rendering**: The Main tab occasionally fails to render all sections (likely due to layout sync issues or state change handling).
- **Performance**: Large mods with many textures can still cause brief hangs during initial cataloging (needs more throttling).

## Future Plans
- **Fix Parenting**: Audit all dynamic widget creation to ensure `parent` is always passed.
- **Disk Cache**: Implement persistent thumbnail storage on disk to eliminate re-loading hangs.
- **Parity**: Bring the modular `TexWorks` to full feature parity and stability with the legacy panel, then deprecate the legacy file.
- **DDS Debugging**: Investigate why certain resolutions or formats result in black thumbnails despite correct paths.

---
*Created by Antigravity during the TexWorks Refactor session.*
