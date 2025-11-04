# rz_gui_constructor/__init__.py
bl_info = {
    "name": "RZMenu Constructor",
    "author": "Rayvich & Gemini",
    "version": (2, 9, 0),
    "blender": (4, 1, 0),
    "location": "View3D > N Panel > RZ Constructor & RZ Construct Debug",
    "description": "A comprehensive scene-based UI editor with an integrated toggle management system.",
    "category": "UI",
}

import bpy
import sys
import importlib

# Новый, строгий порядок загрузки модулей
module_names = [
    'properties',
    'captures',
    'rzm_atlas',
    'helpers',
    'operators',
    'panels',
    'ui_debug_panel',
]

_modules = {}

def reload_modules():
    global _modules
    base_path = __name__
    for name in module_names:
        full_module_name = f"{base_path}.{name}"
        if full_module_name in sys.modules:
            _modules[name] = importlib.reload(sys.modules[full_module_name])
        else:
            _modules[name] = importlib.import_module(full_module_name)

def register():
    # PySide6 зависимости можно добавить обратно при необходимости
    reload_modules()
    for name in module_names:
        module = _modules.get(name)
        if module and hasattr(module, "register"):
            module.register()

def unregister():
    for name in reversed(module_names):
        module = _modules.get(name)
        if module and hasattr(module, "unregister"):
            module.unregister()
    _modules.clear()