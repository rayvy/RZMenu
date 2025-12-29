# RZMenu/qt_editor/widgets/viewport.py
from PySide6 import QtWidgets, QtCore, QtGui

class RZElementItem(QtWidgets.QGraphicsRectItem):
    def __init__(self, uid, x, y, w, h, name):
        super().__init__(0, 0, w, h)
        self.uid = uid
        self.setPos(x, y)
        # Отключаем встроенный Movable, так как мы реализуем свой драг-н-дроп через сцену
        self.setFlags(QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.setBrush(QtGui.QBrush(QtGui.QColor(60, 60, 60, 200)))
        self.setPen(QtGui.QPen(QtGui.QColor(200, 200, 200), 1))
        
        self.text_item = QtWidgets.QGraphicsSimpleTextItem(name, self)
        self.text_item.setBrush(QtGui.QBrush(QtCore.Qt.white))

class RZViewportScene(QtWidgets.QGraphicsScene):
    # Signal: delta_x, delta_y
    item_moved_signal = QtCore.Signal(float, float) 
    # Signal: active_id, modifier_string (CTRL/SHIFT/None)
    selection_changed_signal = QtCore.Signal(int, object)
    interaction_start_signal = QtCore.Signal()
    interaction_end_signal = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self._is_user_interaction = False
        self._drag_start_pos = None
        self._is_dragging = False

    def mousePressEvent(self, event):
        # --- FIX: Используем QtGui.QTransform вместо QtWidgets.QTransform ---
        item = self.itemAt(event.scenePos(), QtGui.QTransform())
        
        # ЛОГИКА ВЫДЕЛЕНИЯ
        modifier = None
        if event.modifiers() & QtCore.Qt.ShiftModifier: modifier = 'SHIFT'
        elif event.modifiers() & QtCore.Qt.ControlModifier: modifier = 'CTRL'

        if isinstance(item, RZElementItem):
            # Сообщаем окну, что кликнули по элементу
            self.selection_changed_signal.emit(item.uid, modifier)
            
            # Подготовка к драгу (только левой кнопкой)
            if event.button() == QtCore.Qt.LeftButton:
                self._is_dragging = True
                self._drag_start_pos = event.scenePos()
                self.interaction_start_signal.emit()
        else:
            # Клик в пустоту -> Сброс выделения
            self.selection_changed_signal.emit(-1, modifier)
            
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_dragging and self._drag_start_pos:
            current_pos = event.scenePos()
            delta = current_pos - self._drag_start_pos
            
            # Эмитим дельту перемещения в Window -> Core
            self.item_moved_signal.emit(delta.x(), delta.y())
            
            # Обновляем старт для следующего шага
            self._drag_start_pos = current_pos
            
            # Визуально двигаем ВСЕ выделенные айтемы (чтобы было плавно)
            for item in self.selectedItems():
                item.moveBy(delta.x(), delta.y())
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_dragging:
            self._is_dragging = False
            self._drag_start_pos = None
            self.interaction_end_signal.emit()
        super().mouseReleaseEvent(event)

    def update_scene(self, elements_data, selected_ids, active_id):
        # Если юзер тащит мышкой, не перерисовываем, иначе объект выскочит из рук
        if self._is_user_interaction: return

        self.clear()
        # Сетка/Фон
        self.addRect(0, 0, 4000, 4000, QtGui.QPen(QtCore.Qt.black))
        
        for data in elements_data:
            item = RZElementItem(
                data['id'], data['pos_x'], data['pos_y'], 
                data['width'], data['height'], data['name']
            )
            self.addItem(item)
            
            if data['id'] in selected_ids:
                item.setSelected(True)
                if data['id'] == active_id:
                    # Подсветим активный элемент яркой рамкой
                    item.setPen(QtGui.QPen(QtGui.QColor(255, 200, 50), 2))

class RZViewportPanel(QtWidgets.QGraphicsView):
    def __init__(self):
        super().__init__()
        self.rz_scene = RZViewportScene()
        self.setScene(self.rz_scene)
        
        # Настройки рендера
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setRenderHint(QtGui.QPainter.TextAntialiasing)
        
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(30, 30, 30)))
        self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)