# RZMenu/operators/element_ops.py
import bpy
from ..core.utils import get_next_available_id

class RZM_OT_AddElement(bpy.types.Operator):
    bl_idname = "rzm.add_element"
    bl_label = "Add UI Element"
    bl_options = {'REGISTER', 'UNDO'}

    # Optional argument to override scene property
    type: bpy.props.StringProperty(default="")

    def execute(self, context):
        rzm = context.scene.rzm
        elements = rzm.elements
        active_idx = context.scene.rzm_active_element_index
        
        new_element = elements.add()
        new_id = get_next_available_id(elements)
        new_element.id = new_id
        
        # Use argument if provided, else fall back to scene property
        if self.type:
            new_element.elem_class = self.type
        else:
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
            
        # Value Links (Fix: Copy Min/Max)
        for sub_item in source_elem.value_link:
            new_sub = new_elem.value_link.add()
            new_sub.value_name = sub_item.value_name
            new_sub.value_min = sub_item.value_min
            new_sub.value_max = sub_item.value_max
            
        # Conditional Images
        for sub_item in source_elem.conditional_images:
            new_sub = new_elem.conditional_images.add()
            new_sub.condition = sub_item.condition
            new_sub.image_id = sub_item.image_id
            
        # Conditional Texts
        for sub_item in source_elem.conditional_texts:
            new_sub = new_elem.conditional_texts.add()
            new_sub.condition = sub_item.condition
            new_sub.text_id = sub_item.text_id
            
        # Toggles
        for sub_item in source_elem.toggles:
            new_sub = new_elem.toggles.add()
            new_sub.toggle_name = sub_item.toggle_name
            for bit in sub_item.bits:
                new_bit = new_sub.bits.add()
                new_bit.value = bit.value
                
        # Presets
        for sub_item in source_elem.preset_ids:
            new_sub = new_elem.preset_ids.add()
            new_sub.preset_id = sub_item.preset_id

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
    bl_options = {'REGISTER', 'UNDO'}

    element_id: bpy.props.IntProperty()
    x: bpy.props.IntProperty()
    y: bpy.props.IntProperty()

    def execute(self, context):
        rzm = context.scene.rzm
        target = next((e for e in rzm.elements if e.id == self.element_id), None)
        if not target:
            return {'CANCELLED'}
        target.position[0] = self.x
        target.position[1] = self.y
        return {'FINISHED'}

class RZM_OT_UpdateElementID(bpy.types.Operator):
    """Updates an element ID, handling children and collisions (swapping)."""
    bl_idname = "rzm.update_element_id"
    bl_label = "Update Element ID"
    bl_options = {'REGISTER', 'UNDO'}

    old_id: bpy.props.IntProperty()
    new_id: bpy.props.IntProperty()

    def execute(self, context):
        rzm = context.scene.rzm
        elements = rzm.elements
        debug = rzm.addons.debugger_info
        
        if self.old_id == self.new_id:
            return {'FINISHED'}

        target = next((e for e in elements if e.id == self.old_id), None)
        collision = next((e for e in elements if e.id == self.new_id), None)

        if not target:
            self.report({'ERROR'}, f"Element with ID {self.old_id} not found")
            return {'CANCELLED'}

        if debug:
            print(f"[RZM_DEBUG] Changing ID {self.old_id} -> {self.new_id}")

        if collision:
            if debug:
                print(f"[RZM_DEBUG] Collision detected between ID {self.old_id} and {self.new_id}. Swapping.")
            
            # --- SWAP LOGIC (SAFE) ---
            # Collect children first to avoid circular re-parenting
            target_children = [e for e in elements if e.parent_id == self.old_id]
            collision_children = [e for e in elements if e.parent_id == self.new_id]

            # 1. Swap the IDs of the parents
            target.id = self.new_id
            collision.id = self.old_id

            # 2. Update children to follow their respective parents to their NEW IDs
            for e in target_children:
                e.parent_id = self.new_id
                if debug: print(f"  > Target's Child {e.element_name} parent_id: {self.old_id} -> {self.new_id}")
            
            for e in collision_children:
                e.parent_id = self.old_id
                if debug: print(f"  > Collision's Child {e.element_name} parent_id: {self.new_id} -> {self.old_id}")
            
            if debug:
                print(f"[RZM_DEBUG] Swap complete: {target.element_name}({self.new_id}) and {collision.element_name}({self.old_id})")
            
        else:
            # --- SIMPLE UPDATE LOGIC ---
            # Collect children first
            target_children = [e for e in elements if e.parent_id == self.old_id]

            # 1. Update parent ID
            target.id = self.new_id

            # 2. Update children
            for e in target_children:
                e.parent_id = self.new_id
                if debug: print(f"  > Child {e.element_name} parent_id: {self.old_id} -> {self.new_id}")
            
            if debug:
                print(f"[RZM_DEBUG] ID update complete: {target.element_name}({self.new_id})")

        # Report to Blender UI as well
        self.report({'INFO'}, f"ID Updated: {self.old_id} -> {self.new_id}")

        # Update active index if needed (though Qt usually handles this via ID)
        from ..qt_editor.core.signals import SIGNALS
        SIGNALS.structure_changed.emit()

        return {'FINISHED'}

class RZM_OT_DistributeElements(bpy.types.Operator):
    """Distributes 3+ elements evenly between the first and last element."""
    bl_idname = "rzm.distribute_elements"
    bl_label = "Distribute UI Elements"
    bl_options = {'REGISTER', 'UNDO'}

    target_ids: bpy.props.StringProperty() # Comma-separated IDs
    mode: bpy.props.EnumProperty(
        items=(
            ('X_ORIGIN', 'X Origin', 'Distribute by X center/origin'),
            ('Y_ORIGIN', 'Y Origin', 'Distribute by Y center/origin'),
            ('AUTO_ORIGIN', 'Auto Origin', 'Linear distribution between endpoints'),
            ('X_GAP', 'X Gap', 'Distribute by horizontal gaps'),
            ('Y_GAP', 'Y Gap', 'Distribute by vertical gaps'),
            ('AUTO_GAP', 'Auto Gap', 'Dominant axis gap distribution'),
        ),
        default='Y_ORIGIN'
    )

    def execute(self, context):
        rzm = context.scene.rzm
        all_elements = rzm.elements
        
        # 1. Parse IDs and get elements
        try:
            ids = [int(i.strip()) for i in self.target_ids.split(",") if i.strip()]
        except:
            self.report({'ERROR'}, "Invalid target IDs")
            return {'CANCELLED'}
            
        selection = [e for e in all_elements if e.id in ids]
        if len(selection) < 3:
            self.report({'WARNING'}, "Distribute requires at least 3 elements.")
            return {'CANCELLED'}

        # 2. Determine Axis and Sort
        def get_distribute_axis():
            if "AUTO" in self.mode:
                min_x = min(e.position[0] for e in selection)
                max_x = max(e.position[0] for e in selection)
                min_y = min(e.position[1] for e in selection)
                max_y = max(e.position[1] for e in selection)
                return "X" if (max_x - min_x) > (max_y - min_y) else "Y"
            return "X" if "X" in self.mode else "Y"

        axis = get_distribute_axis()
        # For Y, typically we sort from top to bottom (descending Y)
        # For X, from left to right (ascending X)
        if axis == "Y":
            selection.sort(key=lambda e: e.position[1], reverse=True)
        else:
            selection.sort(key=lambda e: e.position[0])

        e_first = selection[0]
        e_last = selection[-1]
        n = len(selection)

        # 3. Apply Distribution Logic
        if "ORIGIN" in self.mode:
            if self.mode == "AUTO_ORIGIN":
                # Linear interpolation between endpoints for BOTH X and Y
                start_p = (e_first.position[0], e_first.position[1])
                end_p = (e_last.position[0], e_last.position[1])
                for i in range(1, n - 1):
                    t = i / (n - 1)
                    selection[i].position[0] = int(start_p[0] + (end_p[0] - start_p[0]) * t)
                    selection[i].position[1] = int(start_p[1] + (end_p[1] - start_p[1]) * t)
            elif axis == "X":
                start_x = e_first.position[0]
                total_w = e_last.position[0] - start_x
                for i in range(1, n - 1):
                    selection[i].position[0] = int(start_x + (total_w * i / (n - 1)))
            else: # axis == "Y"
                start_y = e_first.position[1]
                total_h = e_last.position[1] - start_y
                for i in range(1, n - 1):
                    selection[i].position[1] = int(start_y + (total_h * i / (n - 1)))

        else: # GAP Mode
            # Dominant axis for AUTO_GAP is already determined
            if axis == "X":
                # Left-to-right sorting
                total_range = e_last.position[0] - (e_first.position[0] + e_first.size[0])
                sum_mid_w = sum(selection[i].size[0] for i in range(1, n - 1))
                avg_gap = (total_range - sum_mid_w) / (n - 1)
                
                curr_x = e_first.position[0] + e_first.size[0] + avg_gap
                for i in range(1, n - 1):
                    selection[i].position[0] = int(curr_x)
                    curr_x += selection[i].size[0] + avg_gap
            else: # axis == "Y"
                # Top-to-bottom sorting (Y is top edge, Y-size[1] is bottom edge)
                total_range = (e_first.position[1] - e_first.size[1]) - e_last.position[1]
                sum_mid_h = sum(selection[i].size[1] for i in range(1, n - 1))
                avg_gap = (total_range - sum_mid_h) / (n - 1)
                
                curr_y = e_first.position[1] - e_first.size[1] - avg_gap
                for i in range(1, n - 1):
                    selection[i].position[1] = int(curr_y)
                    curr_y -= selection[i].size[1] + avg_gap

        return {'FINISHED'}

classes_to_register = [
    RZM_OT_AddElement,
    RZM_OT_RemoveElement,
    RZM_OT_DuplicateElement,
    RZM_OT_DeselectElement,
    RZM_OT_MoveElementUp,
    RZM_OT_MoveElementDown,
    RZM_OT_SetElementPosition,
    RZM_OT_UpdateElementID,
    RZM_OT_DistributeElements
]
