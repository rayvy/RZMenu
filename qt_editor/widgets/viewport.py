# RZMenu/qt_editor/widgets/viewport.py
from PySide6 import QtWidgets, QtCore, QtGui
from ..systems import operators

# Константы цветов
COLOR_SELECTED = QtGui.QColor(255, 255, 255)
COLOR_ACTIVE = QtGui.QColor(255, 140, 0)
COLOR_NORMAL = QtGui.QColor(200, 200, 200)

class RZElementItem(QtWidgets.QGraphicsRectItem):
    def __init__(self, uid, x, y, w, h, name, elem_type="box"):
        super().__init__(0, 0, w, h)
        self.uid = uid
        self.elem_type = elem_type
        self.setPos(x, y)
        self.setFlags(QtWidgets.QGraphicsItem.ItemUsesExtendedStyleOption)
        self.setBrush(QtGui.QBrush(QtGui.QColor(60, 60, 60, 200)))
        
        self.text_item = QtWidgets.QGraphicsSimpleTextItem(name, self)
        self.text_item.setBrush(QtGui.QBrush(QtCore.Qt.white))
        self.text_item.setPos(5, 5)

    def set_visual_state(self, is_selected, is_active):
        pen = QtGui.QPen()
        pen.setWidth(2 if (is_selected or is_active) else 1)
        
        if is_active:
            pen.setColor(COLOR_ACTIVE)
            self.setZValue(10) 
        elif is_selected:
            pen.setColor(COLOR_SELECTED)
            self.setZValue(5)
        else:
            pen.setColor(COLOR_NORMAL)
            self.setZValue(0)
            
        self.setPen(pen)
    
    def update_geometry(self, x, y, w, h):
        """Обновление позиции и размеров без пересоздания"""
        self.setPos(x, y)
        self.setRect(0, 0, w, h)


class RZViewportScene(QtWidgets.QGraphicsScene):
    item_moved_signal = QtCore.Signal(float, float) 
    selection_changed_signal = QtCore.Signal(int, object)
    interaction_start_signal = QtCore.Signal()
    interaction_end_signal = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self._is_user_interaction = False
        
        self._drag_start_pos = None
        self._is_dragging_items = False
        
        self._last_click_pos = None
        self._cycle_index = 0
        
        # --- SMART UPDATE CACHE ---
        self._items_map = {} # {uid: RZElementItem}
        
        # Статичный фон/сетка
        self._init_background()

    def _init_background(self):
        # Огромный фон
        self.setSceneRect(-10000, -10000, 20000, 20000)
        self.addRect(-10000, -10000, 20000, 20000, QtGui.QPen(QtCore.Qt.NoPen), QtGui.QBrush(QtGui.QColor(30, 30, 30)))
        
        # Сетка
        grid_step = 100
        pen = QtGui.QPen(QtGui.QColor(50, 50, 50))
        for x in range(0, 4000, grid_step):
            self.addLine(x, 0, x, 4000, pen)
        for y in range(0, 4000, grid_step):
            self.addLine(0, y, 4000, y, pen)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MiddleButton:
            event.ignore()
            return

        if event.button() == QtCore.Qt.RightButton:
            item = self.item_at_event(event)
            if isinstance(item, RZElementItem):
                if item.uid not in self.views()[0].parent_window.selected_ids:
                     self.selection_changed_signal.emit(item.uid, None)
            event.accept()
            return

        if event.button() == QtCore.Qt.LeftButton:
            item = self.item_at_event(event)
            modifiers = event.modifiers()
            
            modifier_str = None
            if modifiers & QtCore.Qt.ControlModifier: modifier_str = 'CTRL'
            elif modifiers & QtCore.Qt.ShiftModifier: modifier_str = 'SHIFT'

            if isinstance(item, RZElementItem):
                scene_pos = event.scenePos()
                items_under = [i for i in self.items(scene_pos) if isinstance(i, RZElementItem)]
                
                is_same_click_spot = False
                if self._last_click_pos:
                    if (scene_pos - self._last_click_pos).manhattanLength() < 10:
                        is_same_click_spot = True
                
                if is_same_click_spot and len(items_under) > 1 and modifier_str is None:
                    self._cycle_index = (self._cycle_index + 1) % len(items_under)
                    target_item = items_under[self._cycle_index]
                    self.selection_changed_signal.emit(target_item.uid, modifier_str)
                else:
                    self._last_click_pos = scene_pos
                    self._cycle_index = 0
                    self.selection_changed_signal.emit(item.uid, modifier_str)

                self._is_dragging_items = True
                self._drag_start_pos = scene_pos
                self.interaction_start_signal.emit()
            else:
                self.selection_changed_signal.emit(-1, modifier_str)
                self._last_click_pos = None

    def mouseMoveEvent(self, event):
        if self._is_dragging_items and self._drag_start_pos:
            current_pos = event.scenePos()
            delta = current_pos - self._drag_start_pos
            
            self.item_moved_signal.emit(delta.x(), delta.y())
            self._drag_start_pos = current_pos
            
            for item in self.items():
                if isinstance(item, RZElementItem) and item.zValue() >= 5:
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
        """
        FIX PERFORMANCE / MEMORY LEAK: Smart Update implementation
        Никогда не вызывает clear().
        """
        if self._is_user_interaction: return
        
        # --- FIX VIEWPORT ARROWS (SceneRect) ---
        # Гарантируем, что сцена большая, чтобы скроллинг работал
        self.setSceneRect(-10000, -10000, 20000, 20000)

        # 1. Анализируем входящие ID
        incoming_ids = {d['id'] for d in elements_data}
        current_ids = set(self._items_map.keys())

        # 2. Удаляем старые
        to_remove = current_ids - incoming_ids
        for uid in to_remove:
            item = self._items_map[uid]
            self.removeItem(item)
            del self._items_map[uid]

        # 3. Обновляем или Создаем новые
        for data in elements_data:
            uid = data['id']
            
            # Create or Get
            if uid in self._items_map:
                item = self._items_map[uid]
                # Обновляем геометрию
                item.update_geometry(data['pos_x'], data['pos_y'], data['width'], data['height'])
                # Обновляем имя
                if item.text_item.text() != data['name']:
                    item.text_item.setText(data['name'])
            else:
                elem_type = data.get('class_type', 'box')
                item = RZElementItem(
                    uid, data['pos_x'], data['pos_y'], 
                    data['width'], data['height'], data['name'],
                    elem_type
                )
                self.addItem(item)
                self._items_map[uid] = item
            
            # Update Selection State
            is_sel = uid in selected_ids
            is_act = uid == active_id
            self._items_map[uid].set_visual_state(is_sel, is_act)


class RZViewportPanel(QtWidgets.QGraphicsView):
    def __init__(self):
        super().__init__()
        self.rz_scene = RZViewportScene()
        self.setScene(self.rz_scene)
        
        self.parent_window = None 
        
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setDragMode(QtWidgets.QGraphicsView.NoDrag) 
        
        self._is_panning = False
        self._pan_start_pos = QtCore.QPoint()

        self._zoom_level = 1.0
        self.MIN_ZOOM = 0.1
        self.MAX_ZOOM = 5.0

    def pan_view(self, delta_x, delta_y):
        """
        FIX VIEWPORT ARROWS:
        Метод для программного сдвига (панорамирования) вида.
        """
        h_bar = self.horizontalScrollBar()
        v_bar = self.verticalScrollBar()
        
        # Прибавляем дельту к текущему значению
        h_bar.setValue(h_bar.value() + delta_x)
        v_bar.setValue(v_bar.value() + delta_y)

    def wheelEvent(self, event):
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor
        current_scale = self.transform().m11()

        if event.angleDelta().y() > 0:
            if current_scale < self.MAX_ZOOM:
                self.scale(zoom_in_factor, zoom_in_factor)
        else:
            if current_scale > self.MIN_ZOOM:
                self.scale(zoom_out_factor, zoom_out_factor)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MiddleButton:
            self._is_panning = True
            self._pan_start_pos = event.pos()
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            event.accept()
            return
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
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        item = self.rz_scene.itemAt(self.mapToScene(event.pos()), QtGui.QTransform())
        menu = QtWidgets.QMenu(self)
        
        if isinstance(item, RZElementItem):
            label_action = menu.addAction(f"Item: {item.text_item.text()}")
            label_action.setEnabled(False)
            menu.addSeparator()
            
            action_del = menu.addAction("Delete")
            if self.parent_window and hasattr(self.parent_window, "action_manager"):
                action_del.triggered.connect(lambda: self.parent_window.action_manager.run("rzm.delete"))
            
            if item.elem_type == "text":
                menu.addSeparator()
                menu.addAction("Change Font...")
                menu.addAction("Font Size...")
            elif item.elem_type == "image":
                menu.addSeparator()
                menu.addAction("Reload Image")
        else:
            menu.addAction("New Rectangle").triggered.connect(lambda: print("TODO: Create Rect"))
            menu.addAction("New Text").triggered.connect(lambda: print("TODO: Create Text"))
            menu.addSeparator()
            if self.parent_window:
                menu.addAction("Reset View").triggered.connect(lambda: self.parent_window.action_manager.run("rzm.view_reset"))

        menu.exec(event.globalPos())