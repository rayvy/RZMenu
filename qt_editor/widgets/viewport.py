# RZMenu/qt_editor/widgets/viewport.py
from PySide6 import QtWidgets, QtCore, QtGui

class RZElementItem(QtWidgets.QGraphicsRectItem):
    def __init__(self, uid, x, y, w, h, name):
        super().__init__(0, 0, w, h)
        self.uid = uid
        self.setPos(x, y)
        self.setFlags(
            QtWidgets.QGraphicsItem.ItemIsMovable | 
            QtWidgets.QGraphicsItem.ItemIsSelectable |
            QtWidgets.QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setBrush(QtGui.QBrush(QtGui.QColor(60, 60, 60, 200)))
        self.setPen(QtGui.QPen(QtGui.QColor(200, 200, 200), 1))
        
        self.text_item = QtWidgets.QGraphicsSimpleTextItem(name, self)
        self.text_item.setBrush(QtGui.QBrush(QtCore.Qt.white))
        
        self._is_dragging = False

    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.ItemPositionHasChanged:
            # Если это программное перемещение (из Блендера) - игнорируем
            if self.scene() and self.scene()._is_user_interaction:
                self.scene().item_moved_signal.emit(self.uid, value.x(), value.y())
        return super().itemChange(change, value)

    # Перехватываем события мыши, чтобы знать, когда начали и закончили
    def mousePressEvent(self, event):
        self._is_dragging = True
        if self.scene():
            self.scene().interaction_start_signal.emit()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        super().mouseReleaseEvent(event)
        if self.scene():
            self.scene().interaction_end_signal.emit()


class RZViewportScene(QtWidgets.QGraphicsScene):
    item_moved_signal = QtCore.Signal(int, float, float)
    selection_changed_signal = QtCore.Signal(int)
    
    # Новые сигналы для блокировки таймера
    interaction_start_signal = QtCore.Signal()
    interaction_end_signal = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.selectionChanged.connect(self.on_qt_selection)
        self._ignore_selection_signal = False
        self._is_user_interaction = False # Флаг: юзер сейчас трогает сцену?

    def on_qt_selection(self):
        if self._ignore_selection_signal: return
        items = self.selectedItems()
        if items:
            self.selection_changed_signal.emit(items[0].uid)
        else:
            self.selection_changed_signal.emit(-1)

    def update_scene(self, elements_data, selected_id):
        # Если юзер сейчас тянет мышкой - НЕ ПЕРЕРИСОВЫВАЕМ сцену,
        # иначе предмет выпрыгнет из под мышки.
        if self._is_user_interaction:
            return

        self._ignore_selection_signal = True
        self.clear()
        
        # Сетка
        self.addRect(0, 0, 2000, 2000, QtGui.QPen(QtCore.Qt.black))
        
        to_select = None
        for data in elements_data:
            item = RZElementItem(
                data['id'], 
                data['pos_x'], data['pos_y'], 
                data['width'], data['height'], 
                data['name']
            )
            self.addItem(item)
            if data['id'] == selected_id:
                to_select = item
        
        if to_select:
            to_select.setSelected(True)
            
        self._ignore_selection_signal = False

class RZViewportPanel(QtWidgets.QGraphicsView):
    def __init__(self):
        super().__init__()
        self.rz_scene = RZViewportScene()
        self.setScene(self.rz_scene)
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(30, 30, 30)))
        # Важно: выключаем скроллбары, если мешают, или настраиваем сцену
        self.setSceneRect(0, 0, 2000, 2000)