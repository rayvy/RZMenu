# RZMenu/qt_editor/widgets/viewport.py
from PySide6 import QtWidgets, QtCore, QtGui
# from ..systems import operators # Не используем (Mock)

# Цветовая схема
COLORS_BY_TYPE = {
    'CONTAINER': QtGui.QColor(60, 60, 60),
    'GRID_CONTAINER': QtGui.QColor(50, 50, 55),
    'BUTTON': QtGui.QColor(70, 90, 110),
    'SLIDER': QtGui.QColor(70, 110, 90),
    'TEXT': QtGui.QColor(0, 0, 0, 0), # Transparentish
    'ANCHOR': QtGui.QColor(255, 0, 0, 100)
}

COLOR_SELECTED = QtGui.QColor(255, 255, 255)
COLOR_ACTIVE = QtGui.QColor(255, 140, 0)
COLOR_LOCKED = QtGui.QColor(255, 50, 50)

class RZElementItem(QtWidgets.QGraphicsRectItem):
    def __init__(self, uid, x, y, w, h, name, elem_type="CONTAINER"):
        super().__init__(0, 0, w, h)
        self.uid = uid
        self.elem_type = elem_type
        self.name = name
        
        # State
        self.is_active = False
        self.is_locked = False
        self.image_id = None
        
        self.setPos(x, y)
        
        # Флаги
        self.setFlags(
            QtWidgets.QGraphicsItem.ItemUsesExtendedStyleOption | 
            QtWidgets.QGraphicsItem.ItemIsSelectable
            # ItemIsMovable контролируется через locked состояние
        )

    def set_data_state(self, locked, img_id):
        self.is_locked = locked
        self.image_id = img_id
        # Если залочен, сцена не должна его двигать, 
        # но мы также можем отключить флаг для надежности (хотя движение обрабатывает Scene mouseMove)
        self.update()

    def set_visual_state(self, is_selected, is_active):
        """Обновляем внутреннее состояние и вызываем перерисовку"""
        if self.isSelected() != is_selected:
            self.setSelected(is_selected)
        
        self.is_active = is_active
        
        # Z-Index: Active > Selected > Normal
        if is_active: self.setZValue(20)
        elif is_selected: self.setZValue(10)
        else: self.setZValue(1)
            
        self.update() # Trigger paint
    
    def update_geometry(self, x, y, w, h):
        self.setPos(x, y)
        self.setRect(0, 0, w, h)
    
    def paint(self, painter, option, widget):
        """Кастомная отрисовка в стиле 'Legacy'"""
        rect = self.rect()
        
        # 1. Background
        bg_color = COLORS_BY_TYPE.get(self.elem_type, QtGui.QColor(50, 50, 50))
        if self.is_locked:
            # Слегка затемняем залоченные
            bg_color = bg_color.darker(120)
            
        painter.fillRect(rect, bg_color)
        
        # 2. Image Placeholder
        if self.image_id and str(self.image_id).strip() != "":
            painter.save()
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 50), 2, QtCore.Qt.DashLine))
            painter.drawLine(rect.topLeft(), rect.bottomRight())
            painter.drawLine(rect.topRight(), rect.bottomLeft())
            
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(255, 255, 255, 100))
            painter.drawText(rect, QtCore.Qt.AlignCenter, "IMG")
            painter.restore()

        # 3. Border (Selection / Active)
        border_width = 1.0
        border_color = QtGui.QColor(0, 0, 0)
        
        if self.is_active:
            border_color = COLOR_ACTIVE
            border_width = 3.0
        elif self.isSelected():
            border_color = COLOR_SELECTED
            border_width = 2.0
        elif self.is_locked:
            border_color = QtGui.QColor(50, 0, 0)
            
        pen = QtGui.QPen(border_color, border_width)
        
        # Пунктир для контейнеров (для стиля)
        if self.elem_type == "GRID_CONTAINER":
            pen.setStyle(QtCore.Qt.DashLine)
            
        painter.setPen(pen)
        painter.drawRect(rect)

        # 4. Text Label (Name)
        painter.setPen(QtGui.QColor(255, 255, 255))
        # Рисуем текст в левом верхнем углу с небольшим отступом
        text_rect = rect.adjusted(5, 5, -5, -5)
        painter.drawText(text_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, self.name)
        
        # 5. Lock Icon Indicator
        if self.is_locked:
            painter.setPen(COLOR_LOCKED)
            painter.drawText(text_rect, QtCore.Qt.AlignRight | QtCore.Qt.AlignTop, "🔒")


class RZViewportScene(QtWidgets.QGraphicsScene):
    item_moved_signal = QtCore.Signal(float, float) 
    selection_changed_signal = QtCore.Signal(object, object)
    interaction_start_signal = QtCore.Signal()
    interaction_end_signal = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self._is_user_interaction = False
        self._drag_start_pos = None
        self._is_dragging_items = False
        self._items_map = {} 
        self._init_background()

    def _init_background(self):
        self.setSceneRect(-10000, -10000, 20000, 20000)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(30, 30, 30)))
        # Grid logic can be added here if needed

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MiddleButton:
            return 
        
        if event.button() == QtCore.Qt.LeftButton:
            item = self.item_at_event(event)
            modifiers = event.modifiers()
            modifier_str = None
            if modifiers & QtCore.Qt.ControlModifier: modifier_str = 'CTRL'
            elif modifiers & QtCore.Qt.ShiftModifier: modifier_str = 'SHIFT'

            if isinstance(item, RZElementItem):
                self._handle_item_click(item, event, modifier_str)
                
                # Check Lock before dragging
                if not item.is_locked:
                    self._is_dragging_items = True
                    self._drag_start_pos = event.scenePos()
                    self.interaction_start_signal.emit()
                
                event.accept() 
            else:
                super().mousePressEvent(event)

    def _handle_item_click(self, clicked_item, event, modifier_str):
        # ... (Код аналогичен прошлой версии, логика циклического выделения)
        items_under = [i for i in self.items(event.scenePos()) if isinstance(i, RZElementItem)]
        if not items_under: return
        
        # Mocking parent window access for logical correctness in standalone
        # В реальном коде: current_ids = self.views()[0].parent_window.selected_ids
        # Здесь упростим, предполагая, что RZElementItem знает, выбран он или нет (Qt state)
        current_selected = [i for i in self.items() if i.isSelected()]
        
        target_uid = clicked_item.uid
        if modifier_str is None and len(items_under) > 1:
            current_index = -1
            for idx, item in enumerate(items_under):
                if item.isSelected():
                    current_index = idx
                    break
            
            if current_index != -1:
                next_index = (current_index + 1) % len(items_under)
                target_uid = items_under[next_index].uid
            else:
                target_uid = items_under[0].uid
        
        self.selection_changed_signal.emit(target_uid, modifier_str)

    def mouseMoveEvent(self, event):
        if self._is_dragging_items and self._drag_start_pos:
            current_pos = event.scenePos()
            delta = current_pos - self._drag_start_pos
            
            # Фильтруем перемещение только для незалоченных элементов
            # (Логика backend'а тоже должна это проверять, но здесь для визуала)
            # В данном примере просто эмитим дельту
            
            self.item_moved_signal.emit(delta.x(), delta.y())
            self._drag_start_pos = current_pos
            
            # Визуальный сдвиг
            # (В реальном приложении лучше ждать ответа от backend, но для плавности двигаем сами)
            for item in self.selectedItems():
                if isinstance(item, RZElementItem) and not item.is_locked:
                    item.moveBy(delta.x(), delta.y())
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_dragging_items:
            self._is_dragging_items = False
            self._drag_start_pos = None
            self.interaction_end_signal.emit()
        super().mouseReleaseEvent(event)

    def item_at_event(self, event):
        return self.itemAt(event.scenePos(), QtGui.QTransform())

    def update_scene(self, elements_data, selected_ids, active_id):
        if self._is_user_interaction: return
        
        incoming_ids = {d['id'] for d in elements_data}
        current_ids = set(self._items_map.keys())

        # Remove
        for uid in (current_ids - incoming_ids):
            item = self._items_map[uid]
            self.removeItem(item)
            del self._items_map[uid]

        # Update / Create
        for data in elements_data:
            uid = data['id']
            # Получаем расширенные данные
            ctype = data.get('class_type', 'CONTAINER')
            is_locked = data.get('is_locked', False)
            img_id = data.get('image_id', None)
            
            if uid in self._items_map:
                item = self._items_map[uid]
                item.update_geometry(data['pos_x'], data['pos_y'], data['width'], data['height'])
                item.name = data['name']
                item.elem_type = ctype
            else:
                item = RZElementItem(
                    uid, data['pos_x'], data['pos_y'], 
                    data['width'], data['height'], data['name'],
                    ctype
                )
                self.addItem(item)
                self._items_map[uid] = item
            
            # Обновляем специфичные свойства
            item.set_data_state(is_locked, img_id)
            
            is_sel = uid in selected_ids
            is_act = uid == active_id
            item.set_visual_state(is_sel, is_act)

# Класс RZViewportPanel остается без существенных изменений, так как он просто контейнер для сцены
class RZViewportPanel(QtWidgets.QGraphicsView):
    def __init__(self):
        super().__init__()
        self.rz_scene = RZViewportScene()
        self.setScene(self.rz_scene)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
        
        self._is_panning = False
        self._pan_start_pos = QtCore.QPoint()

    # ... Остальные методы (wheelEvent, mousePressEvent для Pan/BoxSelect) аналогичны предыдущей версии
    # ... Важно сохранить BoxSelect logic из прошлого ответа
    
    def wheelEvent(self, event):
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor
        current_scale = self.transform().m11()
        if event.angleDelta().y() > 0:
            if current_scale < 5.0: self.scale(zoom_in_factor, zoom_in_factor)
        else:
            if current_scale > 0.1: self.scale(zoom_out_factor, zoom_out_factor)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MiddleButton:
            self._is_panning = True
            self._pan_start_pos = event.pos()
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            event.accept()
            return
        
        # Box Select Logic Check
        if event.button() == QtCore.Qt.LeftButton:
            item = self.rz_scene.itemAt(self.mapToScene(event.pos()), QtGui.QTransform())
            if not isinstance(item, RZElementItem):
                self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)
            else:
                self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_panning:
            delta = event.pos() - self._pan_start_pos
            self._pan_start_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MiddleButton:
            self._is_panning = False
            self.setCursor(QtCore.Qt.ArrowCursor)
            event.accept()
            return
            
        if self.dragMode() == QtWidgets.QGraphicsView.RubberBandDrag:
            selected_items = self.scene().selectedItems()
            ids = [item.uid for item in selected_items if isinstance(item, RZElementItem)]
            
            modifier_str = None
            if event.modifiers() & QtCore.Qt.ShiftModifier: modifier_str = 'SHIFT'
            
            if not ids and modifier_str is None:
                self.rz_scene.selection_changed_signal.emit(-1, None)
            elif ids:
                self.rz_scene.selection_changed_signal.emit(ids, modifier_str)

            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
            self.scene().clearSelection()
        
        super().mouseReleaseEvent(event)