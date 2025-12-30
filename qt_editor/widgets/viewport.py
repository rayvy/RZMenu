# RZMenu/qt_editor/widgets/viewport.py
from PySide6 import QtWidgets, QtCore, QtGui
from .. import core
from ..utils.image_cache import ImageCache

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
    def __init__(self, uid, w, h, name, elem_type="CONTAINER"):
        # Координаты устанавливаются через setPos снаружи, тут только Rect (размер)
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
        
        # Флаги
        self.setFlags(
            QtWidgets.QGraphicsItem.ItemUsesExtendedStyleOption | 
            QtWidgets.QGraphicsItem.ItemIsSelectable
            # ItemIsMovable отключен, мы двигаем вручную через mouseMoveEvent сцены
        )

    def set_data_state(self, locked, img_id, is_selectable, text_content):
        self.is_locked = locked
        self.image_id = img_id
        self.is_selectable = is_selectable
        self.text_content = text_content if text_content else self.name
        
        # Ghosting effect for non-selectable items
        self.setOpacity(0.4 if not is_selectable else 1.0)
        
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
            
        self.update() 
    
    def update_size(self, w, h):
        self.setRect(0, 0, w, h)
    
    def paint(self, painter, option, widget):
        rect = self.rect()
        
        # Special case for TEXT: Minimal drawing
        if self.elem_type == 'TEXT':
            painter.setPen(QtGui.QColor(255, 255, 255))
            # Рисуем текст по центру или left-aligned
            painter.drawText(rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, self.text_content)
            
            if self.isSelected():
                 painter.setPen(QtGui.QPen(COLOR_SELECTED, 1, QtCore.Qt.DashLine))
                 painter.drawRect(rect)
            return

        # --- 1. Image Layer ---
        has_image = False
        if self.image_id != -1:
            pix = ImageCache.instance().get_pixmap(self.image_id)
            if pix and not pix.isNull():
                painter.drawPixmap(rect.toRect(), pix)
                has_image = True

        # --- 2. Background Layer ---
        bg_color = COLORS_BY_TYPE.get(self.elem_type, QtGui.QColor(50, 50, 50)).lighter(100)
        
        if has_image:
            bg_color.setAlpha(50) 
        else:
            bg_color.setAlpha(255)

        if self.is_locked:
            bg_color = bg_color.darker(120)
            
        painter.fillRect(rect, bg_color)
        
        # --- 3. Border (Selection / Active) ---
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
        if self.elem_type == "GRID_CONTAINER":
            pen.setStyle(QtCore.Qt.DashLine)
            
        painter.setPen(pen)
        painter.drawRect(rect)

        # --- 4. Text Label (Name) ---
        painter.setPen(QtGui.QColor(0, 0, 0))
        text_rect = rect.adjusted(6, 6, -4, -4)
        painter.drawText(text_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, self.name)
        
        painter.setPen(QtGui.QColor(255, 255, 255))
        text_rect = rect.adjusted(5, 5, -5, -5)
        painter.drawText(text_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, self.name)
        
        # --- 5. Lock Icon ---
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
                # Если элемент не selectable, игнорируем клик (сквозной клик)
                if not item.is_selectable:
                    # Можно добавить логику проброса клика ниже, 
                    # но пока просто игнорим selection logic
                    super().mousePressEvent(event)
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
        # Находим все элементы под курсором
        items_under = [i for i in self.items(event.scenePos()) if isinstance(i, RZElementItem) and i.is_selectable]
        if not items_under: return
        
        target_uid = clicked_item.uid
        # Cycling selection (если несколько объектов друг над другом)
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
            qt_delta = current_pos - self._drag_start_pos
            
            dx_bl, dy_bl = core.to_blender_delta(qt_delta.x(), qt_delta.y())
            
            self.item_moved_signal.emit(dx_bl, dy_bl)
            self._drag_start_pos = current_pos
            
            # Визуальный сдвиг в Qt
            # ВАЖНО: При parented items moveBy работает в локальных координатах.
            # Если мы двигаем родителя, дети едут сами.
            # Если мы выбрали ребенка, moveBy сдвинет его локально.
            for item in self.selectedItems():
                if isinstance(item, RZElementItem) and not item.is_locked:
                    item.moveBy(qt_delta.x(), qt_delta.y())
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_dragging_items:
            self._is_dragging_items = False
            self._drag_start_pos = None
            self.interaction_end_signal.emit()
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        # TODO: Реализовать полноценное меню через ActionManager
        print("Context Menu Requested (Stub)")
        super().contextMenuEvent(event)

    def item_at_event(self, event):
        return self.itemAt(event.scenePos(), QtGui.QTransform())

    def update_scene(self, elements_data, selected_ids, active_id):
        if self._is_user_interaction: return
        
        incoming_ids = {d['id'] for d in elements_data}
        current_ids = set(self._items_map.keys())

        # 1. Pre-cache images
        cache = ImageCache.instance()
        for data in elements_data:
            img_id = data.get('image_id', -1)
            if img_id != -1:
                cache.pre_cache_image(img_id)

        # 2. Cleanup
        for uid in (current_ids - incoming_ids):
            item = self._items_map[uid]
            self.removeItem(item)
            del self._items_map[uid]

        # 3. Create / Update Items (Pass 1: Geometry & Attributes)
        # Мы сохраняем абсолютные позиции из Blender для расчета локальных
        abs_positions = {} # {uid: (qx, qy)}

        for data in elements_data:
            uid = data['id']
            # Конвертируем Blender Abs -> Qt Abs (Y Down)
            qx, qy = core.to_qt_coords(data['pos_x'], data['pos_y'])
            abs_positions[uid] = (qx, qy)

            ctype = data.get('class_type', 'CONTAINER')
            is_locked = data.get('is_locked', False)
            is_hidden = data.get('is_hidden', False)
            is_sel_able = data.get('is_selectable', True)
            img_id = data.get('image_id', -1)
            text_content = data.get('text_content', '')
            
            if uid in self._items_map:
                item = self._items_map[uid]
                item.name = data['name']
                item.elem_type = ctype
            else:
                # В конструктор передаем только размеры, позицию зададим ниже
                item = RZElementItem(uid, data['width'], data['height'], data['name'], ctype)
                self.addItem(item)
                self._items_map[uid] = item
            
            item.update_size(data['width'], data['height'])
            item.set_data_state(is_locked, img_id, is_sel_able, text_content)
            
            # Visibility
            item.setVisible(not is_hidden)

            is_sel = uid in selected_ids
            is_act = uid == active_id
            item.set_visual_state(is_sel, is_act)

        # 4. Parenting & Positioning (Pass 2)
        # Теперь, когда все элементы созданы, настроим иерархию и локальные координаты
        for data in elements_data:
            uid = data['id']
            pid = data.get('parent_id', -1)
            item = self._items_map[uid]
            abs_x, abs_y = abs_positions[uid]

            if pid != -1 and pid in self._items_map:
                parent_item = self._items_map[pid]
                item.setParentItem(parent_item)
                
                # Calculate Local Pos: Child Abs - Parent Abs
                p_abs_x, p_abs_y = abs_positions[pid]
                local_x = abs_x - p_abs_x
                local_y = abs_y - p_abs_y
                item.setPos(local_x, local_y)
            else:
                item.setParentItem(None) # Root item
                item.setPos(abs_x, abs_y)


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

    # ... (Остальные методы mousePress/wheelEvent без изменений) ...
    # Дублирую mousePressEvent чтобы код был полным
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