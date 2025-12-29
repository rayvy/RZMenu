# RZMenu/__init__.py
bl_info = {
    "name": "RZMenu Constructor",
    "author": "Rayvich & Gemini",
    "version": (3, 0, 0),
    "blender": (4, 1, 0), # Blender 5.0 alpha обычно совместим с манифестом 4.x
    "location": "View3D > N Panel > RZ Constructor",
    "description": "Comprehensive scene-based UI editor (Refactored Core).",
    "category": "UI",
}

import os
import sys
import site
import bpy
from bpy.app.handlers import persistent

# --- НАСТРОЙКА СРЕДЫ ---
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_API"] = "pyside6"

try:
    user_site = site.getusersitepackages()
    if user_site not in sys.path:
        sys.path.append(user_site)
except Exception:
    pass

# --- ИМПОРТ НОВОЙ СТРУКТУРЫ ---
# Важен порядок: Сначала Data (свойства), потом Core/Operators/Panels
from .data import properties
from . import operators
from . import panels

# Core не требует регистрации классов bpy, но нужен для работы операторов
from . import core 

modules = [
    properties, # Свойства (PropertyGroups)
    operators,  # Операторы
    panels,     # Интерфейс
]

# --- АВТОЗАПУСК ПРОВЕРКИ ---
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
    for mod in modules:
        if hasattr(mod, "register"):
            mod.register()

    if auto_check_dependencies not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(auto_check_dependencies)
    
    print("RZMenu Constructor (Refactored): Registered successfully.")

def unregister():
    if auto_check_dependencies in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(auto_check_dependencies)

    for mod in reversed(modules):
        if hasattr(mod, "unregister"):
            mod.unregister()

if __name__ == "__main__":
    register()