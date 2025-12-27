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
    
    # Сигнал [NEW]: Данные полностью перезагружены (нужно обновить Hierarchy/Inspector)
    data_reset = Signal()

    # Сигнал [NEW]: Блендер просит нас обновиться (нужно вызвать on_refresh)
    external_update_needed = Signal()

    def __init__(self, bridge):
        super().__init__()
        self.bridge = bridge
        self.elements = {} # {id: dict_data}
        self.selected_id = None

        # Подключаемся к Bridge
        self.bridge.inspector_data_ready.connect(self.sync_from_blender)
        # Если Блендер кричит "Data Changed", мы просим окно сделать Refresh
        self.bridge.data_changed.connect(self.request_full_sync)

    # --- SETTERS (UI -> Data) ---
    
    def set_selection(self, element_id):
        if self.selected_id != element_id:
            self.selected_id = element_id
            self.selection_changed.emit(element_id)

    def update_element_property(self, element_id, prop_name, value):
        if element_id not in self.elements: return

        current_data = self.elements[element_id]
        if prop_name in current_data and current_data[prop_name] == value:
            return

        # Обновляем локально
        current_data[prop_name] = value
        # Уведомляем UI
        self.element_changed.emit(element_id)
        # Шлем в Блендер
        self.bridge.enqueue_update_property(element_id, prop_name, value)

    def update_element_position(self, element_id, x, y):
        if element_id not in self.elements: return
        pos = self.elements[element_id].get('position', [0, 0])
        if pos[0] == x and pos[1] == y: return
        
        self.elements[element_id]['position'] = [x, y]
        # Для удобства обновляем и 'x', 'y' если они есть
        self.elements[element_id]['x'] = x
        self.elements[element_id]['y'] = y
        
        self.element_changed.emit(element_id)
        self.bridge.enqueue_update_element(element_id, x, y)

    # --- SYNC (Blender -> Data) ---

    def request_full_sync(self):
        """Блендер сообщил об изменениях. Просим Main Window запустить refresh."""
        self.external_update_needed.emit()

    def sync_from_blender(self, data):
        """Точечное обновление от Блендера (для Инспектора)."""
        if not data: return
        eid = data.get('id')
        if eid:
            self.elements[eid] = data
            self.element_changed.emit(eid)

    def load_initial_data(self, all_elements_list):
        """
        Загрузка полной базы данных.
        ВЫЗЫВАЕТСЯ ИЗ on_refresh. НЕ ДОЛЖЕН ВЫЗЫВАТЬ on_refresh СНОВА!
        """
        self.elements = {d['id']: d for d in all_elements_list}
        # Испускаем сигнал, что данные готовы. UI может перерисоваться.
        self.data_reset.emit()
    
    def get_data(self, element_id):
        return self.elements.get(element_id)
    
    def get_all_elements(self):
        """Возвращает список всех элементов (для построения дерева)."""
        return list(self.elements.values())