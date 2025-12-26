# RZMenu/panels/__init__.py

import bpy
import importlib
from pathlib import Path

# Keep track of all registered classes to unregister them later.
__all_classes__ = []

def register():
    """
    Finds all .py files in this directory (excluding this __init__.py),
    imports them, and registers the classes they contain.
    """
    global __all_classes__
    __all_classes__ = []
    
    package_dir = Path(__file__).parent
    
    # Special handling for dependencies_panel to get the are_dependencies_met function
    dep_panel_module = None
    
    for module_path in package_dir.glob("*.py"):
        if module_path.name == "__init__.py":
            continue
            
        module_name = f".{module_path.stem}"
        
        try:
            module = importlib.import_module(module_name, __package__)
            
            if module_path.stem == "dependencies_panel":
                dep_panel_module = module

            if hasattr(module, "classes_to_register"):
                for cls in module.classes_to_register:
                    bpy.utils.register_class(cls)
                    __all_classes__.append(cls)

        except Exception as e:
            print(f"ERROR: Failed to register panel module '{module_path.name}': {e}")
            import traceback
            traceback.print_exc()

    # Register the dependency check function
    if dep_panel_module and hasattr(dep_panel_module, "are_dependencies_met"):
        bpy.types.Scene.rzm_dependencies_met = dep_panel_module.are_dependencies_met

def unregister():
    """
    Unregisters all the classes that were registered by this package.
    """
    global __all_classes__
    
    # Unregister the dependency check function
    if hasattr(bpy.types.Scene, "rzm_dependencies_met"):
        del bpy.types.Scene.rzm_dependencies_met

    # Unregister in reverse order
    for cls in reversed(__all_classes__):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            print(f"ERROR: Failed to unregister panel class '{cls.__name__}': {e}")
            
    __all_classes__ = []