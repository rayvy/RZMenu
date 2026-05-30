# RZMenu/shaitan_toolbox/__init__.py
import bpy
from . import ops_uv
from . import ops_vg_sym
from . import ops_color_attr
from . import base_mesh_setup

# Собираем все классы для регистрации из подмодулей
classes = []
for module in (ops_uv, ops_vg_sym, ops_color_attr, base_mesh_setup):
    if hasattr(module, "classes_to_register"):
        classes.extend(module.classes_to_register)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
