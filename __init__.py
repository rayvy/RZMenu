# RZMenu/__init__.py
# Lasciate ogni speranza, voi ch'entrate
bl_info = {
    "name": "RZMenu Constructor",
    "author": "Rayvich & Gemini",
    "version": (4, 0, 2),
    "blender": (4, 1, 0),
    "location": "View3D > N Panel > RZ Constructor",
    "description": "Comprehensive scene-based UI editor (Refactored Core).",
    "category": "UI",
}

import bpy
import site
import sys
import os
from bpy.app.handlers import persistent

from .data import properties
from . import operators
from . import panels
from . import core
from . import shaitan_toolbox
from .utils import overlay_pdiddy
from . import translation

# Keep Qt optional, but still register the Qt editor when available.
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_API"] = "pyside6"

try:
    user_site = site.getusersitepackages()
    if user_site not in sys.path:
        sys.path.insert(0, user_site)
except Exception:
    pass

try:
    import PySide6
    libs_ok = True
except ImportError:
    libs_ok = False


modules = [
    properties,
    core,
    shaitan_toolbox,
    operators,
    panels,
    overlay_pdiddy,
]

if libs_ok:
    try:
        from . import qt_editor
        modules.append(qt_editor)
    except ImportError as e:
        print(f"RZMenu Warning: Could not import qt_editor despite PySide6 presence: {e}")
else:
    print("RZMenu: PySide6 not found. Running in installation mode.")


@persistent
def auto_check_dependencies(dummy):
    def _run_check():
        if hasattr(bpy.ops.rzm, "check_dependencies"):
            try:
                bpy.ops.rzm.check_dependencies()
            except Exception as e:
                print(f"RZMenu Auto-Check Error: {e}")

    bpy.app.timers.register(_run_check, first_interval=1.0)


def register():
    translation.register()

    for mod in modules:
        if hasattr(mod, "register"):
            try:
                mod.register()
            except RuntimeError as e:
                print(f"RZMenu Error registering {mod}: {e}")

    if auto_check_dependencies not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(auto_check_dependencies)

    print("RZMenu Constructor: Registered successfully.")

    try:
        addon_name = __package__.split(".")[0] if "." in __package__ else __package__
        prefs_entry = bpy.context.preferences.addons.get(addon_name)
        if prefs_entry and hasattr(prefs_entry.preferences, "ensure_default_tiers"):
            prefs_entry.preferences.ensure_default_tiers()
    except Exception as e:
        print(f"RZMenu: Could not init default tiers: {e}")


def unregister():
    if auto_check_dependencies in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(auto_check_dependencies)

    for mod in reversed(modules):
        if hasattr(mod, "unregister"):
            mod.unregister()

    translation.unregister()


if __name__ == "__main__":
    register()
