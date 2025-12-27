# RZMenu/qt_editor/rz_data_manager.py

from PySide6.QtCore import QObject, Signal

class RZDataManager(QObject):
    """
    Центральный хаб данных на стороне Qt.
    """
    # Сигнал: Свойства конкретного элемента изменились (id)
    element_changed = Signal(int)
    
    # Сигнал: Выделение изменилось (id или None)
    selection_changed = Signal(object) 
    
    # Сигнал: Данные полностью перезагружены
    data_reset = Signal()

    # Сигнал: Блендер просит нас обновиться
    external_update_needed = Signal()

    def __init__(self, bridge):
        super().__init__()
        self.bridge = bridge
        self.elements = {} # {id: dict_data}
        self.selected_id = None

        self.bridge.inspector_data_ready.connect(self.sync_from_blender)
        self.bridge.data_changed.connect(self.request_full_sync)

    # --- SETTERS (UI -> Data) ---
    
    def set_selection(self, element_id):
        if self.selected_id != element_id:
            self.selected_id = element_id
            self.selection_changed.emit(element_id)

    def update_element_property(self, element_id, prop_name, value):
        """
        Обновление свойства из Инспектора.
        """
        if element_id not in self.elements: return

        current_data = self.elements[element_id]
        
        # Оптимизация: если значение не поменялось, не шумим
        if prop_name in current_data:
            old_val = current_data[prop_name]
            if old_val == value:
                return

        # 1. Обновляем основное значение
        current_data[prop_name] = value

        # [CRITICAL FIX] Синхронизация вспомогательных ключей (x,y,w,h)
        # ElementItem использует x,y,w,h, а Инспектор шлет position/size.
        # Нам нужно держать их в синхроне.
        if prop_name == 'position' and len(value) >= 2:
            current_data['x'] = value[0]
            current_data['y'] = value[1]
        elif prop_name == 'size' and len(value) >= 2:
            current_data['w'] = value[0]
            current_data['h'] = value[1]

        # 2. Уведомляем UI (Вьюпорт увидит новые x/y/w/h)
        self.element_changed.emit(element_id)

        # 3. Шлем в Блендер
        self.bridge.enqueue_update_property(element_id, prop_name, value)

    def update_element_position(self, element_id, x, y):
        """Обновление позиции от мыши (Вьюпорт)."""
        if element_id not in self.elements: return
        
        # Тут мы обновляем все сразу, так что проблем нет
        self.elements[element_id]['position'] = [x, y]
        self.elements[element_id]['x'] = x
        self.elements[element_id]['y'] = y
        
        # Сигнал для Инспектора
        self.element_changed.emit(element_id)
        
        # В Блендер
        self.bridge.enqueue_update_element(element_id, x, y)

    # --- SYNC (Blender -> Data) ---

    def request_full_sync(self):
        self.external_update_needed.emit()

    def sync_from_blender(self, data):
        if not data: return
        eid = data.get('id')
        if eid:
            # При обновлении от Блендера тоже нужно убедиться, что хелперы есть
            # Но rebuild_scene обычно их создает. На всякий случай:
            if 'position' in data:
                data['x'] = data['position'][0]
                data['y'] = data['position'][1]
            if 'size' in data:
                data['w'] = data['size'][0]
                data['h'] = data['size'][1]
                
            self.elements[eid] = data
            self.element_changed.emit(eid)

    def load_initial_data(self, all_elements_list):
        self.elements = {d['id']: d for d in all_elements_list}
        self.data_reset.emit()
    
    def get_data(self, element_id):
        return self.elements.get(element_id)
    
    def get_all_elements(self):
        return list(self.elements.values())