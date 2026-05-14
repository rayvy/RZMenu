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

import os
import sys
import site
import bpy
import importlib
from bpy.app.handlers import persistent

# --- НАСТРОЙКА СРЕДЫ ---
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_API"] = "pyside6"

try:
    user_site = site.getusersitepackages()
    if user_site not in sys.path:
        sys.path.insert(0, user_site)
except Exception:
    pass

# --- ПРОВЕРКА ЗАВИСИМОСТЕЙ ---
try:
    import PySide6
    libs_ok = True
except ImportError:
    libs_ok = False

# --- ИМПОРТ МОДУЛЕЙ ---
# Импортируем безопасные модули (которые не требуют PySide6)
from .data import properties
from . import operators
from . import panels
from . import core 

# Формируем список модулей для загрузки
modules = [
    properties,
    core,       # Тут лежит deps_manager, он нужен всегда
    operators,
    panels,     # Тут должен быть интерфейс кнопки "Установить"
]

# --- ОПАСНЫЙ ИМПОРТ ---
# Пытаемся импортировать qt_editor только если библиотеки на месте
if libs_ok:
    try:
        from . import qt_editor
        modules.append(qt_editor)
    except ImportError as e:
        print(f"RZMenu Warning: Could not import qt_editor despite PySide6 presence: {e}")
else:
    print("RZMenu: PySide6 not found. Running in installation mode.")

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
    # Регистрируем модули по списку
    for mod in modules:
        if hasattr(mod, "register"):
            try:
                mod.register()
            except RuntimeError as e:
                print(f"RZMenu Error registering {mod}: {e}")

    # Хендлер добавляем всегда
    if auto_check_dependencies not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(auto_check_dependencies)
    
    if not libs_ok:
        print("RZMenu Constructor: Started in DEPENDENCY MISSING mode.")
    else:
        print("RZMenu Constructor: Registered successfully.")

    # Populate default tiers if none defined yet (first run for this user)
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

if __name__ == "__main__":
    register()