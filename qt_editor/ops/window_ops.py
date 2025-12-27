# RZMenu/qt_editor/ops/window_ops.py
from ..core.base_operator import RZOperator

class RZ_OT_RefreshData(RZOperator):
    bl_idname = "wm.refresh_data"
    bl_label = "Refresh Data from Blender"
    bl_description = "Reloads all scene data from Blender"

    def execute(self, context):
        # Оператор вызывает метод окна, но сам вызов теперь стандартизирован
        # и может быть вызван откуда угодно (кнопка, хоткей, меню)
        if hasattr(context.window, 'on_refresh'):
            context.window.on_refresh()
            return {'FINISHED'}
        return {'CANCELLED'}

# Регистрация
def register(wm):
    wm.register_operator(RZ_OT_RefreshData)