# RZMenu/qt_editor/rz_bridge.py

import bpy
import queue
import traceback
from PySide6.QtCore import QObject, Signal

class RZBridge(QObject):
    """
    Bridge between external PySide6 View and Blender Internal Data.
    Implements 'Smart Queue' for property updates to prevent flooding.
    """
    # Notify UI that general data changed (triggers Canvas/Tree rebuild)
    data_changed = Signal()
    # Return specific data for the Inspector
    inspector_data_ready = Signal(dict)

    def __init__(self):
        super().__init__()
        self._task_queue = queue.Queue() # Для действий (Create, Delete)
        self._property_cache = {}      # Для значений {(id, prop): value} - BATCHING
        self._is_running = False

    def start(self):
        if not self._is_running:
            self._is_running = True
            # Запускаем таймер почаще (0.01), чтобы интерфейс был отзывчивым
            bpy.app.timers.register(self._process_queue, first_interval=0.01)
            print("RZBridge: Started (Smart Queue Mode)")

    def stop(self):
        self._is_running = False
        print("RZBridge: Stopped")

    def _process_queue(self):
        """Executed by Blender's Main Thread."""
        if not self._is_running:
            return None

        try:
            # 1. BATCH PROCESS PROPERTIES
            # Обрабатываем накопившиеся изменения свойств одним пакетом
            if self._property_cache:
                # Копируем и очищаем кэш, чтобы не блокировать новые поступления
                current_batch = self._property_cache.copy()
                self._property_cache.clear()
                
                self._apply_properties_batch(current_batch)

            # 2. PROCESS TASKS
            # Обрабатываем задачи создания/удаления (их нельзя схлопывать)
            while not self._task_queue.empty():
                try:
                    func = self._task_queue.get_nowait()
                    func()
                except queue.Empty:
                    break
        except Exception:
            traceback.print_exc()

        return 0.01 # Keep running fast

    def _apply_properties_batch(self, batch):
        """Применяет пакет изменений к сцене."""
        scene = bpy.context.scene
        if not hasattr(scene, "rzm"): return
        
        # Оптимизация: Сначала найдем все нужные объекты, чтобы не искать их в цикле 100 раз
        # batch keys: (element_id, prop_name)
        
        # Собираем ID, которые нужно обновить
        target_ids = set(eid for eid, _ in batch.keys())
        
        # Создаем карту {id: blender_object}
        element_map = {}
        for el in scene.rzm.elements:
            if el.id in target_ids:
                element_map[el.id] = el
        
        # Применяем значения
        data_was_changed = False
        
        for (eid, prop_name), value in batch.items():
            target = element_map.get(eid)
            if target and hasattr(target, prop_name):
                try:
                    # Вектора (Color/Pos/Size)
                    if prop_name in ['color', 'position', 'size'] and isinstance(value, (list, tuple)):
                        if getattr(target, prop_name)[:] != value: # Проверка на изменение
                            getattr(target, prop_name)[:] = value
                            data_was_changed = True
                    else:
                        # Скаляры (Int, String, Enum)
                        if getattr(target, prop_name) != value:
                            setattr(target, prop_name, value)
                            data_was_changed = True
                except Exception as e:
                    print(f"RZBridge Error setting {prop_name} on ID {eid}: {e}")

        # Если что-то реально поменялось, можно (но не обязательно) пнуть UI
        # Но так как UI сам инициировал это изменение, ему сигнал не нужен.
        # Сигнал нужен только если изменение пришло извне (скрипт блендера).
        pass

    # --- DATA FETCHING ---
    def fetch_inspector_data(self, element_id):
        def task():
            scene = bpy.context.scene
            target = None
            if hasattr(scene, "rzm"):
                for el in scene.rzm.elements:
                    if el.id == element_id:
                        target = el
                        break
            
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
                    'visibility_condition': target.visibility_condition
                }
                self.inspector_data_ready.emit(data)
            else:
                self.inspector_data_ready.emit({})

        self._task_queue.put(task)

    # --- ACTIONS (Queue) ---
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
        self._task_queue.put(task)

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
        self._task_queue.put(task)

    # --- UPDATES (Smart Cache) ---
    def enqueue_update_element(self, element_id, x, y):
        """
        Optimized position update using cache.
        Overwrites previous pending update for this ID.
        """
        # Кладём сразу в кэш, минуя очередь задач
        self._property_cache[(element_id, 'position')] = [int(x), int(y)]

    def enqueue_update_property(self, element_id, prop_name, value):
        """Generic update using cache."""
        self._property_cache[(element_id, prop_name)] = value