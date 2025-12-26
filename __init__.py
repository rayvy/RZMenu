# RZMenu/__init__.py
bl_info = {
    "name": "RZMenu Constructor",
    "author": "Rayvich & Gemini",
    "version": (2, 9, 3),
    "blender": (4, 1, 0),
    "location": "View3D > N Panel > RZ Constructor",
    "description": "Comprehensive scene-based UI editor with dependency management.",
    "category": "UI",
}

# --- [CRITICAL FIX] НАСТРОЙКА СРЕДЫ ДО ЗАГРУЗКИ МОДУЛЕЙ ---
import os
import sys
import site

# 1. Защита от конфликта DPI в Blender 5.0 + Qt 6.10
# Это должно быть выполнено ДО любого импорта PySide внутри аддона
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_API"] = "pyside6"

# 2. Гарантируем, что Blender видит пакеты пользователя (AppData)
try:
    user_site = site.getusersitepackages()
    if user_site not in sys.path:
        sys.path.append(user_site)
except Exception:
    pass
# -----------------------------------------------------------

import bpy
from bpy.app.handlers import persistent

# --- ПОРЯДОК ИМПОРТА ---
# Теперь можно смело импортировать остальные части, среда уже настроена
from . import properties
from . import dependencies
from . import operators
from . import rzm_atlas
from . import captures
from . import helpers
from . import panels
from . import ui_debug_panel

modules = [
    properties,
    dependencies,
    operators,
    rzm_atlas,
    captures,
    helpers,
    panels,
    ui_debug_panel,
]

# --- АВТОЗАПУСК ПРОВЕРКИ ---
@persistent
def auto_check_dependencies(dummy):
    """Запускает проверку зависимостей с небольшой задержкой после старта."""
    def _run_check():
        # Проверяем, существует ли оператор (на случай если регистрация не прошла)
        if hasattr(bpy.ops.rzm, "check_dependencies"):
            try:
                bpy.ops.rzm.check_dependencies()
            except Exception as e:
                print(f"RZMenu Auto-Check Error: {e}")
    
    # 1.0 секунда надежнее, чем 0.5, чтобы UI успел прогрузиться
    bpy.app.timers.register(_run_check, first_interval=1.0)

def register():
    # Регистрируем модули
    for mod in modules:
        if hasattr(mod, "register"):
            mod.register()

    # Добавляем хендлер на загрузку файла/старт блендера
    if auto_check_dependencies not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(auto_check_dependencies)

    print("RZMenu Constructor: Registered successfully.")

def unregister():
    if auto_check_dependencies in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(auto_check_dependencies)

    for mod in reversed(modules):
        if hasattr(mod, "unregister"):
            mod.unregister()

if __name__ == "__main__":
    register()