# RZMenu/qt_editor/rz_bridge.py

import bpy
import queue
import traceback
from PySide6.QtCore import QObject, Signal

class RZBridge(QObject):
    """
    Bridge between external PySide6 View and Blender Internal Data.
    """
    # Notify UI that general data changed (triggers Canvas/Tree rebuild)
    data_changed = Signal()
    # Return specific data for the Inspector
    inspector_data_ready = Signal(dict)

    def __init__(self):
        super().__init__()
        self._queue = queue.Queue()
        self._is_running = False

    def start(self):
        if not self._is_running:
            self._is_running = True
            bpy.app.timers.register(self._process_queue, first_interval=0.0)
            print("RZBridge: Started")

    def stop(self):
        self._is_running = False
        print("RZBridge: Stopped")

    def _process_queue(self):
        """Executed by Blender's Main Thread."""
        if not self._is_running:
            return None

        while not self._queue.empty():
            try:
                func = self._queue.get_nowait()
                func()
            except queue.Empty:
                break
            except Exception:
                traceback.print_exc()

        return 0.0

    # --- DATA FETCHING ---
    def fetch_inspector_data(self, element_id):
        """
        Gathers all properties of an element and emits inspector_data_ready.
        """
        def task():
            scene = bpy.context.scene
            target = None
            if hasattr(scene, "rzm"):
                for el in scene.rzm.elements:
                    if el.id == element_id:
                        target = el
                        break
            
            if target:
                # Convert Blender types to Python natives for Qt
                data = {
                    'id': target.id,
                    'element_name': target.element_name,
                    'elem_class': target.elem_class, # Enum string
                    'position': [target.position[0], target.position[1]],
                    'size': [target.size[0], target.size[1]],
                    'color': [target.color[0], target.color[1], target.color[2], target.color[3]],
                    'image_mode': target.image_mode,
                    'image_id': target.image_id,
                    'text_id': target.text_id,
                    'visibility_mode': target.visibility_mode,
                    'visibility_condition': target.visibility_condition
                }
                self.inspector_data_ready.emit(data)
            else:
                # Element might have been deleted
                self.inspector_data_ready.emit({})

        self._queue.put(task)

    # --- ACTIONS ---
    def create_element(self, element_type, parent_id=-1, x=0, y=0):
        def task():
            scene = bpy.context.scene
            if not hasattr(scene, "rzm"): return
            elements = scene.rzm.elements
            
            existing_ids = [e.id for e in elements]
            new_id = (max(existing_ids) + 1) if existing_ids else 1
            
            new_item = elements.add()
            new_item.id = new_id
            new_item.element_name = f"New {element_type.capitalize()}"
            new_item.elem_class = element_type
            new_item.parent_id = parent_id
            new_item.position = (int(x), int(y))
            new_item.size = (100, 100)
            
            self.data_changed.emit()
        self._queue.put(task)

    def delete_element(self, element_id):
        def task():
            scene = bpy.context.scene
            if not hasattr(scene, "rzm"): return
            elements = scene.rzm.elements
            
            idx = -1
            for i, el in enumerate(elements):
                if el.id == element_id:
                    idx = i
                    break
            
            if idx != -1:
                elements.remove(idx)
                self.data_changed.emit()
        self._queue.put(task)

    # --- UPDATES ---
    def enqueue_update_element(self, element_id, x, y):
        """Optimized position update for dragging."""
        def task():
            scene = bpy.context.scene
            if hasattr(scene, "rzm"):
                for el in scene.rzm.elements:
                    if el.id == element_id:
                        el.position[0] = int(x)
                        el.position[1] = int(y)
                        break
        self._queue.put(task)

    def enqueue_update_property(self, element_id, prop_name, value):
        """
        Generic update. Handles Scalars, Vectors (Color/Pos/Size), and Enums.
        """
        def task():
            scene = bpy.context.scene
            target = None
            if hasattr(scene, "rzm"):
                for el in scene.rzm.elements:
                    if el.id == element_id:
                        target = el
                        break
            
            if target and hasattr(target, prop_name):
                try:
                    # Handle Color/Vector assignment
                    if prop_name in ['color', 'position', 'size'] and isinstance(value, (list, tuple)):
                        # Assign by slice to copy values into Blender vector property
                        getattr(target, prop_name)[:] = value
                    else:
                        # Simple assignment for Strings, Ints, Enums
                        setattr(target, prop_name, value)
                    
                    # Notify UI (Tree/Canvas might need update if Name/Size/Color changed)
                    self.data_changed.emit()
                except Exception as e:
                    print(f"RZBridge Error setting {prop_name}: {e}")
                
        self._queue.put(task)