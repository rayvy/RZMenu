# RZMenu/qt_editor/rz_bridge.py

import bpy
import queue
import traceback
import copy
from PySide6.QtCore import QObject, Signal

class RZBridge(QObject):
    data_changed = Signal()
    inspector_data_ready = Signal(dict)

    def __init__(self):
        super().__init__()
        self._task_queue = queue.Queue()
        self._property_cache = {} 
        self._clipboard = None # [NEW]
        self._is_running = False

    def start(self):
        if not self._is_running:
            self._is_running = True
            bpy.app.timers.register(self._process_queue, first_interval=0.01)
            print("RZBridge: Started (Smart Queue Mode)")

    def stop(self):
        self._is_running = False
        print("RZBridge: Stopped")

    def _process_queue(self):
        if not self._is_running: return None
        try:
            if self._property_cache:
                current_batch = self._property_cache.copy()
                self._property_cache.clear()
                self._apply_properties_batch(current_batch)

            while not self._task_queue.empty():
                try:
                    func = self._task_queue.get_nowait()
                    func()
                except queue.Empty: break
        except Exception: traceback.print_exc()
        return 0.01

    def _apply_properties_batch(self, batch):
        scene = bpy.context.scene
        if not hasattr(scene, "rzm"): return
        target_ids = set(eid for eid, _ in batch.keys())
        element_map = {}
        for el in scene.rzm.elements:
            if el.id in target_ids: element_map[el.id] = el
        
        for (eid, prop_name), value in batch.items():
            target = element_map.get(eid)
            if target and hasattr(target, prop_name):
                try:
                    if prop_name in ['color', 'position', 'size'] and isinstance(value, (list, tuple)):
                        if getattr(target, prop_name)[:] != value: getattr(target, prop_name)[:] = value
                    else:
                        if getattr(target, prop_name) != value: setattr(target, prop_name, value)
                except Exception as e: print(f"RZBridge Error: {e}")

    def fetch_inspector_data(self, element_id):
        def task():
            scene = bpy.context.scene
            target = None
            if hasattr(scene, "rzm"):
                for el in scene.rzm.elements:
                    if el.id == element_id: target = el; break
            if target:
                data = {
                    'id': target.id,
                    'element_name': target.element_name,
                    'elem_class': target.elem_class,
                    'position': [target.position[0], target.position[1]],
                    'size': [target.size[0], target.size[1]],
                    'color': [target.color[0], target.color[1], target.color[2], target.color[3]],
                    'image_mode': target.image_mode,
                    'image_id': target.image_id,
                    'text_id': target.text_id,
                    'visibility_mode': target.visibility_mode,
                    'visibility_condition': target.visibility_condition,
                    'qt_hide': target.qt_hide,
                    'qt_lock_pos': getattr(target, 'qt_lock_pos', False),
                    'qt_lock_size': getattr(target, 'qt_lock_size', False),
                }
                self.inspector_data_ready.emit(data)
            else: self.inspector_data_ready.emit({})
        self._task_queue.put(task)

    def create_element(self, element_type, parent_id=-1, x=0, y=0):
        def task():
            scene = bpy.context.scene
            if not hasattr(scene, "rzm"): return
            elements = scene.rzm.elements
            new_id = (max([e.id for e in elements]) + 1) if elements else 1
            new_item = elements.add()
            new_item.id = new_id
            new_item.element_name = f"New {element_type.capitalize()}"
            new_item.elem_class = element_type
            new_item.parent_id = parent_id
            new_item.position = (int(x), int(y))
            new_item.size = (100, 100)
            self.data_changed.emit()
        self._task_queue.put(task)

    def delete_element(self, element_id):
        def task():
            scene = bpy.context.scene
            if not hasattr(scene, "rzm"): return
            idx = -1
            for i, el in enumerate(scene.rzm.elements):
                if el.id == element_id: idx = i; break
            if idx != -1:
                scene.rzm.elements.remove(idx)
                self.data_changed.emit()
        self._task_queue.put(task)

    def duplicate_element(self, element_id):
        def task():
            scene = bpy.context.scene
            if not hasattr(scene, "rzm"): return
            source = next((el for el in scene.rzm.elements if el.id == element_id), None)
            if source:
                new_id = (max([e.id for e in scene.rzm.elements]) + 1) if scene.rzm.elements else 1
                new_item = scene.rzm.elements.add()
                new_item.id = new_id
                
                # Copy properties
                new_item.element_name = source.element_name + "_Copy"
                new_item.elem_class = source.elem_class
                new_item.parent_id = source.parent_id
                new_item.position = source.position
                new_item.size = source.size
                new_item.color = source.color
                new_item.image_mode = source.image_mode
                new_item.image_id = source.image_id
                new_item.text_id = source.text_id
                new_item.qt_hide = source.qt_hide
                if hasattr(new_item, 'qt_lock_pos'): new_item.qt_lock_pos = source.qt_lock_pos
                if hasattr(new_item, 'qt_lock_size'): new_item.qt_lock_size = source.qt_lock_size
                
                new_item.position[0] += 20; new_item.position[1] -= 20
                self.data_changed.emit()
        self._task_queue.put(task)

    # --- COPY / PASTE [NEW] ---
    def copy_element(self, element_id):
        """Сохраняет данные элемента в буфер."""
        def task():
            scene = bpy.context.scene
            target = next((el for el in scene.rzm.elements if el.id == element_id), None)
            if target:
                # Сохраняем как словарь (отвязываем от Blender API)
                self._clipboard = {
                    'element_name': target.element_name,
                    'elem_class': target.elem_class,
                    'position': list(target.position),
                    'size': list(target.size),
                    'color': list(target.color),
                    'image_mode': target.image_mode,
                    'image_id': target.image_id,
                    'text_id': target.text_id,
                    'parent_id': target.parent_id # Копируем родителя, но при вставке можно менять
                }
                print(f"Copied: {target.element_name}")
        self._task_queue.put(task)

    def paste_element(self):
        """Создает новый элемент из буфера."""
        def task():
            if not self._clipboard: return
            scene = bpy.context.scene
            
            new_id = (max([e.id for e in scene.rzm.elements]) + 1) if scene.rzm.elements else 1
            new_item = scene.rzm.elements.add()
            new_item.id = new_id
            
            data = self._clipboard
            new_item.element_name = data['element_name'] + "_Paste"
            new_item.elem_class = data['elem_class']
            # Вставляем туда же, где был оригинал (или можно добавить смещение)
            new_item.parent_id = data['parent_id'] 
            new_item.position = data['position']
            new_item.size = data['size']
            new_item.color = data['color']
            new_item.image_mode = data['image_mode']
            new_item.image_id = data['image_id']
            new_item.text_id = data['text_id']
            
            # Сдвиг чтобы видеть
            new_item.position[0] += 20
            new_item.position[1] -= 20
            
            self.data_changed.emit()
        self._task_queue.put(task)

    def enqueue_update_element(self, element_id, x, y):
        self._property_cache[(element_id, 'position')] = [int(x), int(y)]

    def enqueue_update_property(self, element_id, prop_name, value):
        self._property_cache[(element_id, prop_name)] = value