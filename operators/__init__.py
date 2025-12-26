# RZMenu/operators/__init__.py

import bpy
import importlib
import os
from pathlib import Path

# A list to hold all classes from all modules for registration.
__all_classes__ = []

def register():
    """
    Finds all .py files in this directory (excluding this __init__.py),
    imports them, and registers the classes they contain.
    """
    global __all_classes__
    __all_classes__ = []
    
    package_dir = Path(__file__).parent
    
    for module_path in package_dir.glob("*.py"):
        if module_path.name == "__init__.py":
            continue
            
        module_name = f".{module_path.stem}"
        
        try:
            # Import the module relative to this package
            module = importlib.import_module(module_name, __package__)

            # If the module has a list of classes, register them
            if hasattr(module, "classes_to_register"):
                for cls in module.classes_to_register:
                    bpy.utils.register_class(cls)
                    __all_classes__.append(cls)

            # Also call the module's own register function if it exists
            # (for properties, etc.)
            if hasattr(module, "register"):
                module.register()

        except Exception as e:
            print(f"ERROR: Failed to register module '{module_path.name}': {e}")
            import traceback
            traceback.print_exc()

def unregister():
    """
    Unregisters all the classes that were registered by this package.
    """
    global __all_classes__

    # Unregister in reverse order to handle dependencies correctly.
    for cls in reversed(__all_classes__):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            print(f"ERROR: Failed to unregister class '{cls.__name__}': {e}")
            
    # Clear the list
    __all_classes__ = []

