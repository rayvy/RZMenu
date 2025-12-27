import bpy
import queue
import traceback
from PySide6.QtCore import QObject

class RZBridge(QObject):
    """
    Bridge between external PySide6 View and Blender Internal Data.
    """
    def __init__(self):
        super().__init__()
        self._queue = queue.Queue()
        self._is_running = False

    def start(self):
        if not self._is_running:
            self._is_running = True
            # Run immediately (0.0 interval)
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

    def enqueue_update_element(self, element_id, x, y):
        """Update position."""
        def task():
            scene = bpy.context.scene
            target = None
            if hasattr(scene, "rzm"):
                for el in scene.rzm.elements:
                    if el.id == element_id:
                        target = el
                        break
            
            if target:
                target.position[0] = int(x)
                target.position[1] = int(y)
                
        self._queue.put(task)

    def enqueue_update_property(self, element_id, prop_name, value):
        """
        Generic method to update any property of an RZElement.
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
                # Check if property exists to avoid crashes
                if hasattr(target, prop_name):
                    try:
                        setattr(target, prop_name, value)
                    except Exception as e:
                        print(f"RZBridge Error setting {prop_name}: {e}")
                
        self._queue.put(task)