# RZMenu/qt_editor/widgets/outliner.py
from PySide6 import QtWidgets, QtCore

class RZMOutlinerPanel(QtWidgets.QWidget):
    # Сигнал: выбран ID элемента
    selection_changed = QtCore.Signal(int)

    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.itemClicked.connect(self._on_click)
        
        # Стилизация, чтобы выглядело приятнее
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                border: none;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #333;
            }
            QListWidget::item:selected {
                background-color: #405560;
            }
        """)
        
        layout.addWidget(self.list_widget)
        
        self.current_selected_id = -1

    def _on_click(self, item):
        elem_id = item.data(QtCore.Qt.UserRole)
        self.current_selected_id = elem_id
        self.selection_changed.emit(elem_id)
        
    def set_selection_silent(self, elem_id):
        """Устанавливает выделение без вызова сигнала (чтобы избежать циклов)"""
        self.current_selected_id = elem_id
        # Ищем итем и выделяем визуально
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(QtCore.Qt.UserRole) == elem_id:
                self.list_widget.setCurrentItem(item)
                return
        # Если не нашли - сброс
        self.list_widget.clearSelection()

    def update_ui(self, elements_list):
        """
        Брутфорс обновление списка. 
        Срабатывает только если изменилась структура (сигнатура).
        """
        scroll_pos = self.list_widget.verticalScrollBar().value()
        
        self.list_widget.clear()
        selected_item = None
        
        for item_data in elements_list:
            text = f"[{item_data['id']}] {item_data['name']}"
            w_item = QtWidgets.QListWidgetItem(text)
            w_item.setData(QtCore.Qt.UserRole, item_data['id'])
            self.list_widget.addItem(w_item)
            
            if item_data['id'] == self.current_selected_id:
                selected_item = w_item
        
        if selected_item:
            self.list_widget.setCurrentItem(selected_item)
            
        self.list_widget.verticalScrollBar().setValue(scroll_pos)