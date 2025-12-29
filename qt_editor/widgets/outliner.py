# RZMenu/qt_editor/widgets/outliner.py
from PySide6 import QtWidgets, QtCore, QtGui

class RZMDraggableList(QtWidgets.QListWidget):
    internal_reorder_signal = QtCore.Signal(int, object)

    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)
        
        # ВКЛЮЧАЕМ МУЛЬТИ-ВЫДЕЛЕНИЕ
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

    def dropEvent(self, event):
        if event.source() != self: return

        # Reorder разрешаем только если тащим ОДИН элемент (для упрощения)
        selected_items = self.selectedItems()
        if len(selected_items) != 1:
            event.ignore()
            return

        target_item = selected_items[0]
        target_id = target_item.data(QtCore.Qt.UserRole)
        
        pos = event.position().toPoint()
        dest_item = self.itemAt(pos)
        insert_after_id = -1 

        if dest_item is None:
            count = self.count()
            if count > 0:
                insert_after_id = self.item(count - 1).data(QtCore.Qt.UserRole)
            else:
                insert_after_id = None
        else:
            indicator = self.dropIndicatorPosition()
            dest_row = self.row(dest_item)
            dest_id = dest_item.data(QtCore.Qt.UserRole)

            if indicator == QtWidgets.QAbstractItemView.AboveItem:
                if dest_row == 0: insert_after_id = None
                else: insert_after_id = self.item(dest_row - 1).data(QtCore.Qt.UserRole)
            elif indicator == QtWidgets.QAbstractItemView.BelowItem or indicator == QtWidgets.QAbstractItemView.OnItem:
                insert_after_id = dest_id
            elif indicator == QtWidgets.QAbstractItemView.OnViewport:
                if self.count() > 0:
                    insert_after_id = self.item(self.count()-1).data(QtCore.Qt.UserRole)
                else:
                    insert_after_id = None

        if target_id != insert_after_id:
            self.internal_reorder_signal.emit(target_id, insert_after_id)
        event.ignore() 


class RZMOutlinerPanel(QtWidgets.QWidget):
    # (Список выбранных ID, Активный ID)
    selection_changed = QtCore.Signal(list, int)
    items_reordered = QtCore.Signal(int, object)

    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        self.list_widget = RZMDraggableList()
        
        # Подключаем сигнал изменения выделения
        self.list_widget.itemSelectionChanged.connect(self._on_qt_selection_changed)
        
        self.list_widget.internal_reorder_signal.connect(self.items_reordered)
        
        # Стили
        self.list_widget.setStyleSheet("""
            QListWidget { background-color: #2b2b2b; border: none; }
            QListWidget::item { padding: 5px; color: #e0e0e0; }
            QListWidget::item:selected { background-color: #405560; color: white; }
        """)
        layout.addWidget(self.list_widget)
        
        self._block_signals = False

    def _on_qt_selection_changed(self):
        if self._block_signals: return
        
        selected_items = self.list_widget.selectedItems()
        ids = [item.data(QtCore.Qt.UserRole) for item in selected_items]
        
        # Определяем активный (последний в списке current)
        current = self.list_widget.currentItem()
        active_id = -1
        if current and current.isSelected():
            active_id = current.data(QtCore.Qt.UserRole)
        elif ids:
            active_id = ids[0]
            
        self.selection_changed.emit(ids, active_id)

    def set_selection_silent(self, ids_set, active_id):
        """Программно ставит выделение (из window.py)"""
        self._block_signals = True
        self.list_widget.clearSelection()
        
        item_to_focus = None
        
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            uid = item.data(QtCore.Qt.UserRole)
            if uid in ids_set:
                item.setSelected(True)
                if uid == active_id:
                    item_to_focus = item
        
        if item_to_focus:
            self.list_widget.setCurrentItem(item_to_focus)
            
        self._block_signals = False

    def update_ui(self, elements_list):
        self._block_signals = True # Блокируем сигналы при перестройке
        scroll_pos = self.list_widget.verticalScrollBar().value()
        
        self.list_widget.clear()
        
        for item_data in elements_list:
            text = f"[{item_data['id']}] {item_data['name']}"
            w_item = QtWidgets.QListWidgetItem(text)
            w_item.setData(QtCore.Qt.UserRole, item_data['id'])
            self.list_widget.addItem(w_item)
            
        self.list_widget.verticalScrollBar().setValue(scroll_pos)
        self._block_signals = False