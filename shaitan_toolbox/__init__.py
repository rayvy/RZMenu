# RZMenu/shaitan_toolbox/__init__.py
import bpy
from bpy.props import PointerProperty, CollectionProperty

from . import ops_uv
from . import ops_vg_sym
from . import ops_color_attr
from . import ops_setup_scripts

from . import harmonizer_properties
from . import harmonizer_utils
from . import ops_harmonizer
from . import ui_harmonizer

# Собираем все классы для регистрации из подмодулей
classes = []
for module in (
    ops_uv,
    ops_vg_sym,
    ops_color_attr,
    ops_setup_scripts,
    harmonizer_properties,
    ops_harmonizer,
    ui_harmonizer
):
    if hasattr(module, "classes_to_register"):
        classes.extend(module.classes_to_register)

addon_keymaps = []

def register_keymaps():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name="Weight Paint", space_type="EMPTY")
        kmi = km.keymap_items.new("wm.call_menu", "V", "PRESS", alt=True)
        kmi.properties.name = "RZM_MT_quick_attach"
        addon_keymaps.append((km, kmi))

def unregister_keymaps():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

def register():
    # 1. Регистрация всех классов (PropertyGroups, Operators, UILists)
    for cls in classes:
        bpy.utils.register_class(cls)

    # 2. Привязка PropertyGroups к Scene
    bpy.types.Scene.rzm_weight_settings = PointerProperty(type=harmonizer_properties.RZMWeightSettings)
    bpy.types.Scene.rzm_weight_plan = CollectionProperty(type=harmonizer_properties.RZMWeightPlanItem)
    bpy.types.Scene.rzm_approved_matrix = CollectionProperty(type=harmonizer_properties.RZMApprovedBoneRow)
    bpy.types.Scene.rzm_component_summary = CollectionProperty(type=harmonizer_properties.RZMComponentSummary)

    # 3. Регистрация draw-хэндлеров оверлеев
    harmonizer_utils.OVERLAY_VIEW_HANDLE = bpy.types.SpaceView3D.draw_handler_add(
        harmonizer_utils.draw_weight_overlay_view, (), "WINDOW", "POST_VIEW"
    )
    harmonizer_utils.OVERLAY_PIXEL_HANDLE = bpy.types.SpaceView3D.draw_handler_add(
        harmonizer_utils.draw_weight_overlay_pixel, (), "WINDOW", "POST_PIXEL"
    )

    # 4. Регистрация keymaps
    register_keymaps()

def unregister():
    # 1. Удаление keymaps
    unregister_keymaps()

    # 2. Удаление draw-хэндлеров оверлеев
    if harmonizer_utils.OVERLAY_VIEW_HANDLE is not None:
        bpy.types.SpaceView3D.draw_handler_remove(harmonizer_utils.OVERLAY_VIEW_HANDLE, "WINDOW")
        harmonizer_utils.OVERLAY_VIEW_HANDLE = None
    if harmonizer_utils.OVERLAY_PIXEL_HANDLE is not None:
        bpy.types.SpaceView3D.draw_handler_remove(harmonizer_utils.OVERLAY_PIXEL_HANDLE, "WINDOW")
        harmonizer_utils.OVERLAY_PIXEL_HANDLE = None

    # 3. Удаление Scene свойств
    for prop in ("rzm_component_summary", "rzm_approved_matrix", "rzm_weight_plan", "rzm_weight_settings"):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)

    # 4. Анрегистрация классов
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
