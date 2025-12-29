# RZMenu/operators/element_ops.py
import bpy
from ..core.utils import get_next_available_id

class RZM_OT_AddElement(bpy.types.Operator):
    bl_idname = "rzm.add_element"
    bl_label = "Add UI Element"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rzm = context.scene.rzm
        elements = rzm.elements
        active_idx = context.scene.rzm_active_element_index
        
        new_element = elements.add()
        new_id = get_next_available_id(elements)
        new_element.id = new_id
        new_element.elem_class = rzm.element_to_add_class
        new_element.element_name = f"{new_element.elem_class.capitalize()}{new_id}"
        
        if 0 <= active_idx < len(elements):
            parent_element = elements[active_idx]
            new_element.parent_id = parent_element.id
        else:
            new_element.parent_id = -1
            
        if new_element.elem_class == 'GRID_CONTAINER':
            new_element.grid_min_cells = (1, 1)
            new_element.grid_max_cells = (5, 5)
            new_element.grid_cell_size = 64

        context.scene.rzm_active_element_index = len(elements) - 1
        return {'FINISHED'}

class RZM_OT_RemoveElement(bpy.types.Operator):
    bl_idname = "rzm.remove_element"
    bl_label = "Remove UI Element"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        idx = context.scene.rzm_active_element_index
        return 0 <= idx < len(context.scene.rzm.elements)

    def execute(self, context):
        elements = context.scene.rzm.elements
        index = context.scene.rzm_active_element_index
        
        elements.remove(index)
        if index > 0:
            context.scene.rzm_active_element_index = index - 1
        
        
        return {'FINISHED'}

class RZM_OT_DuplicateElement(bpy.types.Operator):
    """Creates a duplicate of the active element with a slight offset."""
    bl_idname = "rzm.duplicate_element"
    bl_label = "Duplicate UI Element"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        idx = context.scene.rzm_active_element_index
        return 0 <= idx < len(context.scene.rzm.elements)

    def execute(self, context):
        rzm = context.scene.rzm
        elements = rzm.elements
        active_idx = context.scene.rzm_active_element_index
        
        source_elem = elements[active_idx]
        new_elem = elements.add()
        
        # Copy properties
        for prop in source_elem.bl_rna.properties:
            if prop.identifier == 'id' or prop.is_readonly:
                continue
            try:
                setattr(new_elem, prop.identifier, getattr(source_elem, prop.identifier))
            except:
                pass 

        # Deep copy collections
        for sub_item in source_elem.fx:
            new_sub = new_elem.fx.add()
            new_sub.value = sub_item.value
        for sub_item in source_elem.fn:
            new_sub = new_elem.fn.add()
            new_sub.function_name = sub_item.function_name
        for sub_item in source_elem.properties:
            new_sub = new_elem.properties.add()
            new_sub.key = sub_item.key
            new_sub.value_type = sub_item.value_type
            new_sub.string_value = sub_item.string_value
            new_sub.int_value = sub_item.int_value
            new_sub.float_value = sub_item.float_value

        new_elem.id = get_next_available_id(elements)
        new_elem.element_name = f"{source_elem.element_name}_Copy"
        
        new_pos = list(source_elem.position)
        new_pos[0] += 25
        new_elem.position = new_pos
        
        context.scene.rzm_active_element_index = len(elements) - 1
        
        return {'FINISHED'}

class RZM_OT_DeselectElement(bpy.types.Operator):
    """Deselects the active element in the list."""
    bl_idname = "rzm.deselect_element"
    bl_label = "Deselect Element"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.scene.rzm_active_element_index != -1

    def execute(self, context):
        context.scene.rzm_active_element_index = -1
        return {'FINISHED'}

class RZM_OT_MoveElementUp(bpy.types.Operator):
    """Swaps the active element with the one above it in the list."""
    bl_idname = "rzm.move_element_up"
    bl_label = "Move Element Up"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.rzm_active_element_index > 0

    def execute(self, context):
        scene = context.scene
        elements = scene.rzm.elements
        idx = scene.rzm_active_element_index
        
        elements.move(idx, idx - 1)
        scene.rzm_active_element_index = idx - 1
        
        
        return {'FINISHED'}

class RZM_OT_MoveElementDown(bpy.types.Operator):
    """Swaps the active element with the one below it in the list."""
    bl_idname = "rzm.move_element_down"
    bl_label = "Move Element Down"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        idx = context.scene.rzm_active_element_index
        return 0 <= idx < len(context.scene.rzm.elements) - 1

    def execute(self, context):
        scene = context.scene
        elements = scene.rzm.elements
        idx = scene.rzm_active_element_index

        elements.move(idx, idx + 1)
        scene.rzm_active_element_index = idx + 1
        
        
        return {'FINISHED'}
    
class RZM_OT_SetElementPosition(bpy.types.Operator):
    """API Operator: Sets position for a specific element ID"""
    bl_idname = "rzm.set_element_position"
    bl_label = "Set Position"
    bl_options = {'REGISTER', 'UNDO'} # <-- ВАЖНО: UNDO включено

    element_id: bpy.props.IntProperty()
    x: bpy.props.IntProperty()
    y: bpy.props.IntProperty()

    def execute(self, context):
        rzm = context.scene.rzm
        # Ищем элемент по ID
        target = next((e for e in rzm.elements if e.id == self.element_id), None)
        
        if not target:
            return {'CANCELLED'}
        
        # Меняем данные (Блендер запомнит это состояние)
        target.position[0] = self.x
        target.position[1] = self.y
        
        # Сообщаем всем, что данные изменились
        # (В реальном проекте тут будет более умная система событий)
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_AddElement,
    RZM_OT_RemoveElement,
    RZM_OT_DuplicateElement,
    RZM_OT_DeselectElement,
    RZM_OT_MoveElementUp,
    RZM_OT_MoveElementDown,
    RZM_OT_SetElementPosition
]
