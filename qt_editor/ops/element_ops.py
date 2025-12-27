# RZMenu/qt_editor/ops/element_ops.py
from ..core.base_operator import RZOperator

class RZ_OT_DeleteElement(RZOperator):
    bl_idname = "element.delete"
    bl_label = "Delete Element"

    @classmethod
    def poll(cls, context):
        return context.selected_id is not None

    def execute(self, context):
        # Логика теперь обращается к Bridge через context
        context.bridge.delete_element(context.selected_id)
        context.data_manager.set_selection(None)
        return {'FINISHED'}

class RZ_OT_DuplicateElement(RZOperator):
    bl_idname = "element.duplicate"
    bl_label = "Duplicate Element"

    @classmethod
    def poll(cls, context):
        return context.selected_id is not None

    def execute(self, context):
        context.bridge.duplicate_element(context.selected_id)
        return {'FINISHED'}

class RZ_OT_CopyElement(RZOperator):
    bl_idname = "element.copy"
    
    @classmethod
    def poll(cls, context):
        return context.selected_id is not None
        
    def execute(self, context):
        context.bridge.copy_element(context.selected_id)
        return {'FINISHED'}

class RZ_OT_PasteElement(RZOperator):
    bl_idname = "element.paste"
    
    def execute(self, context):
        context.bridge.paste_element()
        return {'FINISHED'}
    
class RZ_OT_HideElement(RZOperator):
    bl_idname = "element.hide"
    bl_label = "Hide Selected"

    @classmethod
    def poll(cls, context):
        return bool(context.selected_ids)

    def execute(self, context):
        # Проходимся по списку (подготовка к мульти-выделению)
        for eid in context.selected_ids:
            data = context.data_manager.get_data(eid)
            if data:
                current_state = data.get('qt_hide', False)
                # Инвертируем состояние
                new_state = not current_state
                context.data_manager.update_element_property(eid, 'qt_hide', new_state)
        
        return {'FINISHED'}

class RZ_OT_UnhideAll(RZOperator):
    bl_idname = "element.unhide_all"
    bl_label = "Unhide All Elements"

    def execute(self, context):
        all_elements = context.data_manager.get_all_elements()
        count = 0
        for elem in all_elements:
            if elem.get('qt_hide', False):
                context.data_manager.update_element_property(elem['id'], 'qt_hide', False)
                count += 1
        
        # Можно вывести в консоль или статус бар сколько открыли
        print(f"Unhidden {count} elements")
        return {'FINISHED'}

# Регистрация
classes = [RZ_OT_DeleteElement, RZ_OT_DuplicateElement, RZ_OT_CopyElement, RZ_OT_PasteElement, RZ_OT_HideElement, RZ_OT_UnhideAll]

def register(wm):
    for cls in classes:
        wm.register_operator(cls)