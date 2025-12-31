# RZMenu/qt_editor/backend/commands.py
import bpy
from typing import List, Any, Tuple

# --- UTILITY FUNCTIONS (inspired by core.py) ---

def _refresh_viewports():
    """Redraw all 3D viewports."""
    if not bpy.context.window_manager:
        return
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

def _get_stable_context():
    """Finds a stable 3D View context to run operators in."""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                if region:
                    return {'window': window, 'screen': window.screen, 'area': area, 'region': region}
    return None

def _safe_undo_push(message: str):
    """Adds an undo step, running in a stable context."""
    ctx = _get_stable_context()
    if not ctx:
        return
    
    # Use temp_override for modern Blender versions
    if hasattr(bpy.context, "temp_override"):
        with bpy.context.temp_override(**ctx):
            bpy.ops.ed.undo_push(message=message)
    else: # Fallback for older versions
        bpy.ops.ed.undo_push(ctx, message=message)

    _refresh_viewports()

def _get_next_available_id(elements) -> int:
    """Finds the next available unique ID for a new element."""
    if not elements:
        return 1
    return max(el.id for el in elements) + 1


# --- SERVICE CLASS ---

class SceneService:
    """
    Encapsulates all write operations (commands) to the Blender scene data.
    Each public method should be an atomic, undoable operation.
    """

    def create_element(self, elem_type: str, pos: Tuple[float, float], parent_id: int = -1) -> int:
        """
        Creates a new element in the scene.
        Returns the ID of the newly created element.
        """
        try:
            rzm = bpy.context.scene.rzm
            elements = rzm.elements
            
            new_id = _get_next_available_id(elements)
            new_element = elements.add()
            new_element.id = new_id
            new_element.elem_class = elem_type
            new_element.element_name = f"{elem_type.capitalize()}_{new_id}"
            new_element.position = pos
            
            # Default sizes based on type
            if elem_type == 'BUTTON': new_element.size = (120, 30)
            else: new_element.size = (150, 100)
            
            if parent_id != -1:
                new_element.parent_id = parent_id
                
            _safe_undo_push(f"RZM: Create {elem_type}")
            return new_id
        except (AttributeError, RuntimeError) as e:
            print(f"Error creating element: {e}")
            return -1

    def update_transform(self, elem_id: int, x: float, y: float, w: float, h: float):
        """Updates the position and size of a single element."""
        try:
            elements = bpy.context.scene.rzm.elements
            target = next((e for e in elements if e.id == elem_id), None)
            if target:
                target.position = (x, y)
                target.size = (w, h)
                _safe_undo_push("RZM: Update Transform")
        except (AttributeError, RuntimeError) as e:
            print(f"Error updating transform: {e}")

    def delete_elements(self, ids: List[int]):
        """Deletes one or more elements from the scene."""
        if not ids:
            return
        try:
            elements = bpy.context.scene.rzm.elements
            indices_to_remove = [i for i, elem in enumerate(elements) if elem.id in ids]
            
            if not indices_to_remove:
                return

            for idx in sorted(indices_to_remove, reverse=True):
                elements.remove(idx)
            
            _safe_undo_push("RZM: Delete Elements")
        except (AttributeError, RuntimeError) as e:
            print(f"Error deleting elements: {e}")

    def set_parent(self, child_id: int, parent_id: int):
        """Sets the parent for a given element."""
        try:
            elements = bpy.context.scene.rzm.elements
            target = next((e for e in elements if e.id == child_id), None)
            if target:
                target.parent_id = parent_id
                _safe_undo_push("RZM: Reparent Element")
        except (AttributeError, RuntimeError) as e:
            print(f"Error setting parent: {e}")

    def reorder_element(self, target_id: int, insert_after_id: int):
        """Moves an element in the collection list for display order."""
        try:
            elements = bpy.context.scene.rzm.elements
            
            target_idx = next((i for i, el in enumerate(elements) if el.id == target_id), -1)
            if target_idx == -1: return

            # If moving to the top of the list
            if insert_after_id is None:
                to_index = 0
            else:
                anchor_idx = next((i for i, el in enumerate(elements) if el.id == insert_after_id), -1)
                if anchor_idx == -1 or target_idx == anchor_idx: return
                to_index = anchor_idx if target_idx < anchor_idx else anchor_idx + 1

            max_idx = len(elements) - 1
            if to_index > max_idx: to_index = max_idx
            
            if target_idx != to_index:
                elements.move(target_idx, to_index)
                _safe_undo_push("RZM: Reorder Element")
        except (AttributeError, RuntimeError) as e:
            print(f"Error reordering element: {e}")

    def update_property(self, elem_id: int, key: str, value: Any):
        """Updates a single property on a single element."""
        try:
            elements = bpy.context.scene.rzm.elements
            target = next((e for e in elements if e.id == elem_id), None)
            if not target:
                return

            # Simple direct mapping for now, can be expanded like in core.py
            if hasattr(target, key):
                current_val = getattr(target, key)
                # Handle Blender's property array access
                if hasattr(current_val, 'copy'): # It's a collection like position, size, color
                    setattr(target, key, value)
                else: # It's a simple property
                    if current_val != value:
                        setattr(target, key, value)
                
                _safe_undo_push(f"RZM: Update {key}")
            else:
                print(f"Warning: Property '{key}' not found on element {elem_id}")

        except (AttributeError, RuntimeError) as e:
            print(f"Error updating property: {e}")
