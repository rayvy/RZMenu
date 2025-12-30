
# RZMenu/qt_editor/widgets/viewport.py
from PySide6 import QtWidgets, QtCore, QtGui
import shiboken6
from .. import core
from ..utils.image_cache import ImageCache

# Цвета
COLORS_BY_TYPE = {
    'CONTAINER': QtGui.QColor(60, 60, 60, 200),
    'GRID_CONTAINER': QtGui.QColor(50, 50, 55, 200),
    'BUTTON': QtGui.QColor(70, 90, 110, 255),
    'SLIDER': QtGui.QColor(70, 110, 90, 255),
    'TEXT': QtGui.QColor(0, 0, 0, 0), 
    'ANCHOR': QtGui.QColor(255, 0, 0, 100)
}
COLOR_SELECTED = QtGui.QColor(255, 255, 255)
COLOR_ACTIVE = QtGui.QColor(255, 140, 0)
COLOR_LOCKED = QtGui.QColor(255, 50, 50)
HANDLE_SIZE = 8

class RZHandleItem(QtWidgets.QGraphicsRectItem):
    """
    Ручка для изменения размера (Gizmo Handle).
    """
    # Типы ручек
    TOP_LEFT = 0
    TOP = 1
    TOP_RIGHT = 2
    RIGHT = 3
    BOTTOM_RIGHT = 4
    BOTTOM = 5
    BOTTOM_LEFT = 6
    LEFT = 7

    def __init__(self, handle_type, parent):
        super().__init__(0, 0, HANDLE_SIZE, HANDLE_SIZE, parent)
        self.handle_type = handle_type
        self.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))
        self.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), 1))
        self.setZValue(100) # Поверх элемента
        
        # Определяем курсор
        cursors = {
            self.TOP_LEFT: QtCore.Qt.SizeFDiagCursor,
            self.BOTTOM_RIGHT: QtCore.Qt.SizeFDiagCursor,
            self.TOP_RIGHT: QtCore.Qt.SizeBDiagCursor,
            self.BOTTOM_LEFT: QtCore.Qt.SizeBDiagCursor,
            self.TOP: QtCore.Qt.SizeVerCursor,
            self.BOTTOM: QtCore.Qt.SizeVerCursor,
            self.LEFT: QtCore.Qt.SizeHorCursor,
            self.RIGHT: QtCore.Qt.SizeHorCursor,
        }
        self.setCursor(cursors.get(handle_type, QtCore.Qt.ArrowCursor))
        self.setAcceptHoverEvents(True)

    def hoverEnterEvent(self, event):
        self.setBrush(QtGui.QBrush(COLOR_ACTIVE))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        # Начинаем перетаскивание, блокируем событие, чтобы родитель не двигался
        event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & QtCore.Qt.LeftButton:
            # Передаем дельту родительскому элементу
            delta = event.scenePos() - event.lastScenePos()
            self.parentItem().handle_resize(self.handle_type, delta)
            event.accept()
        else:
            super().mouseMoveEvent(event)

class RZElementItem(QtWidgets.QGraphicsRectItem):
    def __init__(self, uid, w, h, name, elem_type="CONTAINER"):
        super().__init__(0, 0, w, h)
        self.uid = uid
        self.elem_type = elem_type
        self.name = name
        self.text_content = name
        
        # State
        self.is_active = False
        self.is_locked = False
        self.image_id = -1
        self.is_selectable = True
        self.custom_color = None 
        
        self.handles = {} # {type: RZHandleItem}

        self.setFlags(
            QtWidgets.QGraphicsItem.ItemUsesExtendedStyleOption | 
            QtWidgets.QGraphicsItem.ItemIsSelectable
        )

    def create_handles(self):
        """Создает 8 ручек, если их еще нет"""
        if self.handles: return
        
        for h_type in range(8):
            handle = RZHandleItem(h_type, self)
            self.handles[h_type] = handle
        self.update_handles_pos()

    def update_handles_pos(self):
        """Расставляет ручки по краям текущего rect"""
        if not self.handles: return
        
        rect = self.rect()
        w, h = rect.width(), rect.height()
        hs = HANDLE_SIZE
        hh = hs / 2 # half handle
        
        # Координаты ручек (центры)
        # 0 1 2
        # 7   3
        # 6 5 4
        
        positions = {
            RZHandleItem.TOP_LEFT:     (-hh, -hh),
            RZHandleItem.TOP:          (w/2 - hh, -hh),
            RZHandleItem.TOP_RIGHT:    (w - hh, -hh),
            RZHandleItem.RIGHT:        (w - hh, h/2 - hh),
            RZHandleItem.BOTTOM_RIGHT: (w - hh, h - hh),
            RZHandleItem.BOTTOM:       (w/2 - hh, h - hh),
            RZHandleItem.BOTTOM_LEFT:  (-hh, h - hh),
            RZHandleItem.LEFT:         (-hh, h/2 - hh),
        }
        
        for h_type, (x, y) in positions.items():
            if h_type in self.handles:
                self.handles[h_type].setPos(x, y)

    def set_handles_visible(self, visible):
        if not self.handles and visible:
            self.create_handles()
        
        for handle in self.handles.values():
            handle.setVisible(visible)

    def handle_resize(self, h_type, delta):
        """
        Логика изменения размера при перетаскивании ручки.
        h_type: тип ручки
        delta: QPointF смещения мыши
        """
        if self.is_locked: return

        r = self.rect()
        cur_pos = self.pos()
        
        dx = delta.x()
        dy = delta.y()
        
        new_x = cur_pos.x()
        new_y = cur_pos.y()
        new_w = r.width()
        new_h = r.height()
        
        # Min size
        MIN_SIZE = 10
        
        # Logic depends on handle type
        # Top/Left handles affect Position AND Size (Qt coords: Y down)
        
        # Horizontal
        if h_type in (RZHandleItem.TOP_LEFT, RZHandleItem.LEFT, RZHandleItem.BOTTOM_LEFT):
            # Тянем влево: x уменьшается, w увеличивается
            # Но мы не можем просто уменьшить x, если w достигнет минимума
            if new_w - dx < MIN_SIZE:
                dx = new_w - MIN_SIZE
            
            new_x += dx
            new_w -= dx
            
        elif h_type in (RZHandleItem.TOP_RIGHT, RZHandleItem.RIGHT, RZHandleItem.BOTTOM_RIGHT):
            # Тянем вправо: w увеличивается
            if new_w + dx < MIN_SIZE:
                dx = MIN_SIZE - new_w
            new_w += dx

        # Vertical
        if h_type in (RZHandleItem.TOP_LEFT, RZHandleItem.TOP, RZHandleItem.TOP_RIGHT):
            # Тянем вверх: y уменьшается, h увеличивается
            if new_h - dy < MIN_SIZE:
                dy = new_h - MIN_SIZE
            new_x += 0 # Y handled below, X handled above
            new_y += dy
            new_h -= dy
            
        elif h_type in (RZHandleItem.BOTTOM_LEFT, RZHandleItem.BOTTOM, RZHandleItem.BOTTOM_RIGHT):
            # Тянем вниз: h увеличивается
            if new_h + dy < MIN_SIZE:
                dy = MIN_SIZE - new_h
            new_h += dy

        # 1. Визуальное обновление (мгновенно)
        self.setRect(0, 0, new_w, new_h)
        self.setPos(new_x, new_y)
        self.update_handles_pos() # Двигаем ручки следом
        
        # 2. Сигнал в систему (для записи в Blender)
        # Конвертация координат обратно в Blender (Y up) не требуется для Width/Height,
        # но требуется для PosX/PosY.
        # Однако, RZViewportScene обычно отправляет Qt координаты, а core конвертирует.
        # Проверим core.resize_element: он принимает Qt X/Y? Нет, он пишет в Blender.
        # Значит нам нужно сконвертировать X/Y здесь перед отправкой.
        
        bl_x, bl_y = core.to_blender_delta(new_x, new_y) 
        # Стоп. to_blender_delta конвертирует дельту. А нам нужны абсолютные координаты.
        # core.to_qt_coords: QtX = BlX, QtY = -BlY.
        # Значит BlX = QtX, BlY = -QtY.
        
        final_bl_x = int(new_x)
        final_bl_y = int(-new_y)
        
        # Сигнал идет через сцену
        self.scene().element_resized_signal.emit(self.uid, final_bl_x, final_bl_y, int(new_w), int(new_h))

    def set_data_state(self, locked, img_id, is_selectable, text_content, color=None):
        self.is_locked = locked
        self.image_id = img_id
        self.is_selectable = is_selectable
        self.text_content = text_content if text_content else self.name
        self.custom_color = color
        
        self.setOpacity(0.5 if not is_selectable else 1.0)
        self.update()

    def set_visual_state(self, is_selected, is_active):
        if self.isSelected() != is_selected:
            self.setSelected(is_selected)
        self.is_active = is_active
        
        if is_active: self.setZValue(20)
        elif is_selected: self.setZValue(10)
        else: self.setZValue(1)
        
        # Показываем ручки только если выделен, активен и не залочен
        show_handles = is_selected and not self.is_locked
        self.set_handles_visible(show_handles)
        
        self.update() 
    
    def update_size(self, w, h):
        self.setRect(0, 0, w, h)
        self.update_handles_pos()
        self.update() 
    
    def paint(self, painter, option, widget):
        rect = self.rect()
        
        if self.elem_type == 'TEXT':
            painter.setPen(QtGui.QColor(255, 255, 255))
            painter.drawText(rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, self.text_content)
            if self.isSelected():
                 painter.setPen(QtGui.QPen(COLOR_SELECTED, 1, QtCore.Qt.DashLine))
                 painter.drawRect(rect)
            return

        has_image = False
        if self.image_id != -1:
            pix = ImageCache.instance().get_pixmap(self.image_id)
            if pix and not pix.isNull():
                painter.drawPixmap(rect.toRect(), pix)
                has_image = True

        if self.custom_color and len(self.custom_color) >= 3:
            r, g, b = [int(c*255) for c in self.custom_color[:3]]
            a = int(self.custom_color[3]*255) if len(self.custom_color) > 3 else 255
            bg_color = QtGui.QColor(r, g, b, a)
        else:
            bg_color = COLORS_BY_TYPE.get(self.elem_type, QtGui.QColor(50, 50, 50, 200))
        
        if has_image and not self.custom_color:
            bg_color.setAlpha(30)

        if self.is_locked:
            bg_color = bg_color.darker(120)
            
        painter.fillRect(rect, bg_color)
        
        border_width = 1.0
        border_color = QtGui.QColor(0, 0, 0, 150)
        
        if self.is_active:
            border_color = COLOR_ACTIVE
            border_width = 2.0
        elif self.isSelected():
            border_color = COLOR_SELECTED
            border_width = 1.0
        elif self.is_locked:
            border_color = QtGui.QColor(50, 0, 0)
            
        pen = QtGui.QPen(border_color, border_width)
        if self.elem_type == "GRID_CONTAINER":
            pen.setStyle(QtCore.Qt.DashLine)
            
        painter.setPen(pen)
        painter.drawRect(rect)

        painter.setPen(QtGui.QColor(0, 0, 0))
        text_rect = rect.adjusted(6, 6, -4, -4)
        painter.drawText(text_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, self.name)
        
        painter.setPen(QtGui.QColor(255, 255, 255))
        text_rect = rect.adjusted(5, 5, -5, -5)
        painter.drawText(text_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, self.name)
        
        if self.is_locked:
            painter.setPen(COLOR_LOCKED)
            painter.drawText(text_rect, QtCore.Qt.AlignRight | QtCore.Qt.AlignTop, "🔒")


class RZViewportScene(QtWidgets.QGraphicsScene):
    item_moved_signal = QtCore.Signal(float, float) 
    element_resized_signal = QtCore.Signal(int, int, int, int, int) # uid, x, y, w, h
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

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MiddleButton:
            return 
        
        if event.button() == QtCore.Qt.LeftButton:
            item = self.item_at_event(event)
            modifiers = event.modifiers()
            modifier_str = None
            if modifiers & QtCore.Qt.ControlModifier: modifier_str = 'CTRL'
            elif modifiers & QtCore.Qt.ShiftModifier: modifier_str = 'SHIFT'

            # Если клик попал в ручку (RZHandleItem), отдаем событие ей, не меняя выделение
            if isinstance(item, RZHandleItem):
                self.interaction_start_signal.emit() # Начало изменения размера
                super().mousePressEvent(event)
                return

            if isinstance(item, RZElementItem):
                if not item.is_selectable:
                    event.ignore() 
                    return

                self._handle_item_click(item, event, modifier_str)
                
                if not item.is_locked:
                    self._is_dragging_items = True
                    self._drag_start_pos = event.scenePos()
                    self.interaction_start_signal.emit()
                
                event.accept() 
            else:
                super().mousePressEvent(event)

    def _handle_item_click(self, clicked_item, event, modifier_str):
        items_under = [i for i in self.items(event.scenePos()) if isinstance(i, RZElementItem) and i.is_selectable]
        if not items_under: return
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
        # Если тащим сам элемент
        if self._is_dragging_items and self._drag_start_pos:
            current_pos = event.scenePos()
            qt_delta = current_pos - self._drag_start_pos
            
            dx_bl, dy_bl = core.to_blender_delta(qt_delta.x(), qt_delta.y())
            self.item_moved_signal.emit(dx_bl, dy_bl)
            
            self._drag_start_pos = current_pos
            
            for item in self.selectedItems():
                if isinstance(item, RZElementItem) and not item.is_locked:
                    item.moveBy(qt_delta.x(), qt_delta.y())
                    # При перемещении ручки тоже должны двигаться (они дети, двигаются сами)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_dragging_items:
            self._is_dragging_items = False
            self._drag_start_pos = None
            self.interaction_end_signal.emit()
        
        # Если тянули ручку
        # RZHandleItem перехватывает mousePress, но Release может прийти в сцену
        # Проверяем флаг интеракции
        if self._is_user_interaction and not self._is_dragging_items:
             self.interaction_end_signal.emit()
             
        super().mouseReleaseEvent(event)

    def item_at_event(self, event):
        return self.itemAt(event.scenePos(), QtGui.QTransform())

    def update_scene(self, elements_data, selected_ids, active_id):
        if self._is_user_interaction: return
        
        incoming_ids = {d['id'] for d in elements_data}
        current_ids = set(self._items_map.keys())

        cache = ImageCache.instance()
        for data in elements_data:
            img_id = data.get('image_id', -1)
            if img_id != -1: cache.pre_cache_image(img_id)

        for uid in (current_ids - incoming_ids):
            item = self._items_map.get(uid)
            if item and shiboken6.isValid(item):
                self.removeItem(item)
            del self._items_map[uid]
        
        for uid in incoming_ids:
            if uid in self._items_map:
                item = self._items_map[uid]
                if not shiboken6.isValid(item):
                    del self._items_map[uid]

        for data in elements_data:
            uid = data['id']
            qx, qy = core.to_qt_coords(data['pos_x'], data['pos_y'])
            
            ctype = data.get('class_type', 'CONTAINER')
            is_locked = data.get('is_locked', False)
            is_hidden = data.get('is_hidden', False)
            is_sel_able = data.get('is_selectable', True)
            img_id = data.get('image_id', -1)
            text_content = data.get('text_content', '')
            color = data.get('color', None)
            
            if uid in self._items_map:
                item = self._items_map[uid]
                item.name = data['name']
                item.elem_type = ctype
            else:
                item = RZElementItem(uid, data['width'], data['height'], data['name'], ctype)
                self.addItem(item)
                self._items_map[uid] = item
            
            item.update_size(data['width'], data['height'])
            item.setPos(qx, qy)
            item.set_data_state(is_locked, img_id, is_sel_able, text_content, color)
            item.setVisible(not is_hidden)

            is_sel = uid in selected_ids
            is_act = uid == active_id
            item.set_visual_state(is_sel, is_act)

        for data in elements_data:
            uid = data['id']
            pid = data.get('parent_id', -1)
            if uid not in self._items_map: continue
            item = self._items_map[uid]
            if pid != -1 and pid in self._items_map:
                parent_item = self._items_map[pid]
                if item.parentItem() != parent_item:
                    item.setParentItem(parent_item)
            else:
                if item.parentItem() is not None:
                    item.setParentItem(None)
        
        self.update()


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
        
        self.parent_window = None 

    def contextMenuEvent(self, event):
        if not self.parent_window or not hasattr(self.parent_window, "action_manager"):
            return

        menu = QtWidgets.QMenu(self)
        
        def add_op(op_id):
            if op_id in self.parent_window.action_manager.q_actions:
                action = self.parent_window.action_manager.q_actions[op_id]
                menu.addAction(action)

        item = self.rz_scene.itemAt(self.mapToScene(event.pos()), QtGui.QTransform())
        hit_element = isinstance(item, RZElementItem)

        if hit_element:
            menu.addSection("Element Actions")
            add_op("rzm.toggle_hide")
            add_op("rzm.toggle_lock")
            add_op("rzm.toggle_selectable")
            menu.addSeparator()
            add_op("rzm.delete")
        else:
            menu.addSection("General")
            add_op("rzm.select_all")
            add_op("rzm.view_reset")
            add_op("rzm.unhide_all")
            
        menu.addSeparator()
        add_op("rzm.undo")
        add_op("rzm.redo")
        
        menu.exec(event.globalPos())

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
        if event.button() == QtCore.Qt.LeftButton:
            # Если кликаем по ручке, View не должен включать RubberBand
            item = self.rz_scene.itemAt(self.mapToScene(event.pos()), QtGui.QTransform())
            is_gizmo = isinstance(item, RZHandleItem)
            
            if not isinstance(item, RZElementItem) and not is_gizmo:
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