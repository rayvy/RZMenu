# RZMenu/qt_editor/widgets/outliner.py
from PySide6 import QtWidgets, QtCore, QtGui

class RZMDraggableList(QtWidgets.QListWidget):
    """
    Кастомный список с поддержкой Drag&Drop.
    Не меняет порядок элементов сам, а сообщает контроллеру,
    как изменился порядок, чтобы обновить Blender.
    """
    # target_id (кого тащим), insert_after_id (после кого ставим, или None если в начало)
    internal_reorder_signal = QtCore.Signal(int, object)

    def __init__(self):
        super().__init__()
        # Включаем D&D
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)
        # Одиночное выделение упрощает логику сортировки
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

    def dropEvent(self, event):
        """
        Переопределяем событие броска.
        Вместо того чтобы дать Qt переставить элементы, вычисляем логику и шлем сигнал.
        """
        if event.source() != self:
            return

        # 1. Определяем, кого перетащили (Target)
        selected_items = self.selectedItems()
        if not selected_items:
            return
        target_item = selected_items[0]
        target_id = target_item.data(QtCore.Qt.UserRole)

        # 2. Определяем, куда бросили
        pos = event.position().toPoint()
        dest_item = self.itemAt(pos)
        
        insert_after_id = -1 # Значение-заглушка

        # Логика определения места вставки
        if dest_item is None:
            # Бросили в пустое место -> ставим в самый конец списка
            count = self.count()
            if count > 0:
                last_item = self.item(count - 1)
                insert_after_id = last_item.data(QtCore.Qt.UserRole)
            else:
                insert_after_id = None
        else:
            # Бросили на какой-то элемент. Смотрим на индикатор (черту).
            indicator = self.dropIndicatorPosition()
            dest_row = self.row(dest_item)
            dest_id = dest_item.data(QtCore.Qt.UserRole)

            if indicator == QtWidgets.QAbstractItemView.AboveItem:
                # Вставка "НАД" элементом dest_item
                if dest_row == 0:
                    insert_after_id = None # Вставка в самый верх
                else:
                    # Вставка после предыдущего
                    prev_item = self.item(dest_row - 1)
                    insert_after_id = prev_item.data(QtCore.Qt.UserRole)
            
            elif indicator == QtWidgets.QAbstractItemView.BelowItem or indicator == QtWidgets.QAbstractItemView.OnItem:
                # Вставка "ПОД" элементом dest_item
                insert_after_id = dest_id
            
            elif indicator == QtWidgets.QAbstractItemView.OnViewport:
                # Вставка в конец (если список не пуст)
                if self.count() > 0:
                    insert_after_id = self.item(self.count()-1).data(QtCore.Qt.UserRole)
                else:
                    insert_after_id = None

        # 3. Отправляем сигнал и ИГНОРИРУЕМ стандартное поведение
        # Проверка на самокопирование (target не должен быть равен after)
        if target_id != insert_after_id:
            self.internal_reorder_signal.emit(target_id, insert_after_id)

        # Важно: ignore() предотвращает локальное изменение списка виджетом
        event.ignore() 


class RZMOutlinerPanel(QtWidgets.QWidget):
    # Сигнал: выбран ID элемента
    selection_changed = QtCore.Signal(int)
    # Сигнал: элементы переупорядочены (target_id, insert_after_id)
    items_reordered = QtCore.Signal(int, object)

    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        # Заменяем стандартный QListWidget на наш Draggable
        self.list_widget = RZMDraggableList()
        self.list_widget.itemClicked.connect(self._on_click)
        
        # Прокидываем сигнал из списка наружу через панель
        self.list_widget.internal_reorder_signal.connect(self.items_reordered)
        
        # Стилизация, чтобы выглядело приятнее
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #333;
                color: #e0e0e0;
            }
            QListWidget::item:selected {
                background-color: #405560;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #353535;
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
        found = False
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(QtCore.Qt.UserRole) == elem_id:
                self.list_widget.setCurrentItem(item)
                found = True
                break
        # Если не нашли - сброс
        if not found:
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