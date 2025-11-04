# rz_gui_constructor/dependencies.py
import bpy
import importlib.metadata

# Этот файл максимально упрощен, так как нам нужен только PySide6
# Сложная логика установки убрана для ясности, ее можно вернуть при необходимости.

pyside_installed = False
try:
    importlib.metadata.version("PySide6")
    pyside_installed = True
except importlib.metadata.PackageNotFoundError:
    pyside_installed = False

def check_dependencies():
    """Простая проверка, установлен ли PySide6."""
    return pyside_installed

# Функции register/unregister здесь не нужны, так как нет операторов или панелей.
# Этот модуль просто проверяет зависимость при импорте.