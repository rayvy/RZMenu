# RZMenu/operators/__init__.py

import bpy
import importlib
import os
from pathlib import Path

# A list to hold all classes from all modules for registration.
__all_classes__ = []
__menu_modules__ = []

def register():
    """
    Finds all .py files in this directory (excluding this __init__.py),
    imports them, and registers the classes they contain.
    """
    global __all_classes__
    global __menu_modules__
    __all_classes__ = []
    __menu_modules__ = []

    package_dir = Path(__file__).parent

    for module_path in package_dir.glob("*.py"):
        if module_path.name == "__init__.py":
            continue

        module_name = f".{module_path.stem}"

        try:
            module = importlib.import_module(module_name, __package__)

            if hasattr(module, "classes_to_register"):
                for cls in module.classes_to_register:
                    bpy.utils.register_class(cls)
                    __all_classes__.append(cls)
            if hasattr(module, "register_menus"):
                module.register_menus()
                __menu_modules__.append(module)

        except Exception as e:
            print(f"ERROR: Failed to register module '{module_path.name}': {e}")
            import traceback
            traceback.print_exc()

    # Install XXMI / EFMI export interceptors via timer.
    # Safe and catches addons that load after RZMenu or are enabled later.
    try:
        from . import export_interceptor
        export_interceptor.register()
    except Exception as e:
        print(f"[RZM] [CACHE] Interceptor install skipped: {e}")


def unregister():
    """
    Unregisters all the classes that were registered by this package.
    """
    global __all_classes__
    global __menu_modules__

    # Remove export monkey-patches and timer before unregistering classes
    try:
        from . import export_interceptor
        export_interceptor.unregister()
    except Exception as e:
        print(f"[RZM] [CACHE] Interceptor uninstall skipped: {e}")

    for module in reversed(__menu_modules__):
        try:
            if hasattr(module, "unregister_menus"):
                module.unregister_menus()
        except Exception as e:
            print(f"ERROR: Failed to unregister menus for '{getattr(module, '__name__', module)}': {e}")

    for cls in reversed(__all_classes__):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            print(f"ERROR: Failed to unregister class '{cls.__name__}': {e}")

    __all_classes__ = []
    __menu_modules__ = []
