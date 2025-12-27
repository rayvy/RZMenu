# RZMenu/qt_editor/modes/element_mode.py

from PySide6 import QtWidgets, QtGui, QtCore
from ..rz_bridge import RZBridge
from ..utils.image_cache import ImageCache

# --- ITEM CLASS ---
class RZElementItem(QtWidgets.QGraphicsRectItem):
    def __init__(self, data, bridge):
        super().__init__(0, 0, data['w'], data['h'])
        self.bridge = bridge
        self.element_id = data['id']
        self.on_move_callback = None 
        
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges)
        
        self.text_item = QtWidgets.QGraphicsTextItem("", self)
        self.text_item.setZValue(10)
        
        self.update_data(data)

    def update_data(self, data):
        """Обновление данных (Из Блендера или Менеджера)."""
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges, False)
        
        # 1. Размер
        if self.rect().width() != data['w'] or self.rect().height() != data['h']:
            self.setRect(0, 0, data['w'], data['h'])

        # 2. Позиция (Если не тащим мышкой)
        if not (self.isSelected() and QtWidgets.QApplication.mouseButtons() == QtCore.Qt.LeftButton):
            self.setPos(data['x'], data['y'])
        
        # 3. Визуал
        self.image_id = data.get('image_id', -1)
        c = data.get('color', (0.5, 0.5, 0.5, 1.0))
        try:
            self.base_color = QtGui.QColor.fromRgbF(c[0], c[1], c[2], c[3])
        except:
            self.base_color = QtGui.QColor(128, 128, 128)

        # [FIX] Используем правильный ключ 'element_name'
        name = data.get('element_name', 'Unnamed')
        if self.text_item.toPlainText() != name:
            self.text_item.setPlainText(name)
            self.text_item.setDefaultTextColor(QtGui.QColor(255, 255, 255))
            
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges, True)
        self.update()

    def paint(self, painter, option, widget):
        if self.rect().width() < 1 or self.rect().height() < 1: return

        pixmap = ImageCache.instance().get_pixmap(self.image_id)
        rect = self.rect()
        
        if pixmap and not pixmap.isNull():
            painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
            painter.drawPixmap(rect.toRect(), pixmap)
            if self.base_color.alpha() > 0:
                painter.setBrush(QtGui.QBrush(self.base_color))
                painter.setOpacity(0.3)
                painter.drawRect(rect)
                painter.setOpacity(1.0)
        else:
            painter.setBrush(QtGui.QBrush(self.base_color))
            painter.setPen(QtGui.QPen(QtGui.QColor(30, 30, 30), 1))
            painter.drawRect(rect)

        if self.isSelected():
            painter.setBrush(QtCore.Qt.NoBrush)
            pen = QtGui.QPen(QtGui.QColor("#ffaa00"), 2)
            pen.setJoinStyle(QtCore.Qt.MiterJoin)
            painter.setPen(pen)
            painter.drawRect(rect)

    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.ItemPositionHasChanged:
            if self.flags() & QtWidgets.QGraphicsItem.ItemSendsGeometryChanges:
                if self.on_move_callback:
                    self.on_move_callback(self.element_id, int(value.x()), int(value.y()))
        return super().itemChange(change, value)


# --- VIEWPORT ---
class RZViewport(QtWidgets.QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)
        self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#181818")))
        self._middle_pressed = False
        self._last_pan_pos = QtCore.QPoint()

    def wheelEvent(self, event):
        if event.modifiers() & QtCore.Qt.ControlModifier:
            zoom_in = event.angleDelta().y() > 0
            scale = 1.15 if zoom_in else 1 / 1.15
            self.scale(scale, scale)
        else:
            super().wheelEvent(event)
    
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MiddleButton:
            self._middle_pressed = True
            self._last_pan_pos = event.pos()
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            event.accept()
            return
        if event.button() == QtCore.Qt.LeftButton:
            if self.itemAt(event.pos()) is None:
                self.scene().clearSelection()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._middle_pressed:
            delta = event.pos() - self._last_pan_pos
            self._last_pan_pos = event.pos()
            hs = self.horizontalScrollBar()
            vs = self.verticalScrollBar()
            hs.setValue(hs.value() - delta.x())
            vs.setValue(vs.value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MiddleButton:
            self._middle_pressed = False
            self.setCursor(QtCore.Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)
    
    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        grid_size = 50
        painter.setPen(QtGui.QPen(QtGui.QColor(40, 40, 40), 1))
        l = int(rect.left()); t = int(rect.top()); r = int(rect.right()); b = int(rect.bottom())
        first_left = l - (l % grid_size)
        first_top = t - (t % grid_size)
        for x in range(first_left, r, grid_size): painter.drawLine(x, t, x, b)
        for y in range(first_top, b, grid_size): painter.drawLine(l, y, r, y)


# --- CONTROLLER ---
class ElementMode(QtWidgets.QWidget):
    element_selected = QtCore.Signal(object)

    def __init__(self, context, bridge, data_manager):
        super().__init__()
        self.bl_context = context
        self.bridge = bridge 
        self.data_manager = data_manager
        
        self.scene = QtWidgets.QGraphicsScene()
        self.scene.setSceneRect(-10000, -10000, 20000, 20000)
        self.scene.selectionChanged.connect(self.on_selection_changed)
        
        self.view = RZViewport(self.scene)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.view)
        
        self.view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.show_context_menu)
        
        self.items_map = {} # {id: RZElementItem}

    def on_selection_changed(self):
        items = self.scene.selectedItems()
        if len(items) == 1 and isinstance(items[0], RZElementItem):
            self.element_selected.emit(items[0].element_id)
        else:
            self.element_selected.emit(None)

    def on_data_changed(self, element_id):
        """Инспектор (или менеджер) обновил данные. Синхронизируем графику."""
        if element_id in self.items_map:
            data = self.data_manager.get_data(element_id)
            if data:
                self.items_map[element_id].update_data(data)

    def show_context_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        items = self.view.items(pos)
        parent_id = -1
        if items:
            top_item = items[0]
            if isinstance(top_item, RZElementItem):
                parent_id = top_item.element_id

        add_menu = menu.addMenu(f"Add Element (Parent: {parent_id})")
        scene_pos = self.view.mapToScene(pos)
        target_x = scene_pos.x(); target_y = scene_pos.y()
        
        if parent_id != -1 and parent_id in self.items_map:
            parent_item = self.items_map[parent_id]
            local_pos = parent_item.mapFromScene(scene_pos)
            target_x = local_pos.x(); target_y = local_pos.y()

        for type_name in ['CONTAINER', 'BUTTON', 'SLIDER', 'TEXT']:
            action = add_menu.addAction(type_name.capitalize())
            def create_closure(t=type_name, pid=parent_id, x=target_x, y=target_y):
                self.bridge.create_element(t, pid, int(x), int(y))
                QtCore.QTimer.singleShot(50, self.rebuild_scene)
            action.triggered.connect(create_closure)
            
        sel_items = self.scene.selectedItems()
        if sel_items:
            menu.addSeparator()
            del_action = menu.addAction("Delete Selected")
            def delete_closure():
                for i in sel_items:
                    if isinstance(i, RZElementItem):
                        self.bridge.delete_element(i.element_id)
                QtCore.QTimer.singleShot(50, self.rebuild_scene)
            del_action.triggered.connect(delete_closure)
            
        menu.exec(self.view.mapToGlobal(pos))

    def select_item_by_id(self, element_id):
        self.scene.blockSignals(True)
        self.scene.clearSelection()
        if element_id in self.items_map:
            item = self.items_map[element_id]
            item.setSelected(True)
        self.scene.blockSignals(False)

    def rebuild_scene(self):
        """Перестраивает сцену и [ВАЖНО] инициализирует Data Manager."""
        if not hasattr(self.bl_context.scene, "rzm"): return
        
        ImageCache.instance().clear()
        elements = self.bl_context.scene.rzm.elements
        
        # 1. Сбор данных в список словарей
        all_data_list = []
        
        for elem in elements:
            if elem.image_mode == 'SINGLE' and elem.image_id != -1:
                ImageCache.instance().pre_cache_image(elem.image_id)
            
            safe_color = (0.5, 0.5, 0.5, 1.0)
            try: safe_color = tuple(elem.color)
            except: pass
            
            img_id = elem.image_id if elem.image_mode == 'SINGLE' else -1
            
            # [FIX] Используем правильные ключи, соответствующие Blender Property
            data = {
                'id': elem.id,
                'element_name': elem.element_name, # <-- БЫЛО 'name', СТАЛО 'element_name'
                'elem_class': elem.elem_class,     # <-- БЫЛО 'type', СТАЛО 'elem_class'
                'position': [elem.position[0], elem.position[1]],
                'x': elem.position[0],
                'y': elem.position[1],
                'size': [elem.size[0], elem.size[1]],
                'w': elem.size[0],
                'h': elem.size[1],
                'image_id': img_id,
                'color': safe_color,
                'parent_id': elem.parent_id,
                'image_mode': elem.image_mode,
                'text_id': elem.text_id,
                'visibility_mode': elem.visibility_mode,
                'visibility_condition': elem.visibility_condition
            }
            all_data_list.append(data)

        # 2. Загружаем "Правду" в Менеджер
        self.data_manager.load_initial_data(all_data_list)

        # 3. Создание / Обновление Items
        current_data_map = {d['id']: d for d in all_data_list}
        processed_ids = set()
        
        for eid, data in current_data_map.items():
            processed_ids.add(eid)
            
            if eid in self.items_map:
                self.items_map[eid].update_data(data)
            else:
                item = RZElementItem(data, self.bridge)
                item.on_move_callback = self.data_manager.update_element_position
                self.scene.addItem(item)
                self.items_map[eid] = item

        # 4. Удаление устаревших
        existing_ids = list(self.items_map.keys())
        for eid in existing_ids:
            if eid not in processed_ids:
                item = self.items_map.pop(eid)
                self.scene.removeItem(item)

        # 5. Иерархия (Parenting)
        for eid, item in self.items_map.items():
            data = current_data_map[eid]
            pid = data['parent_id']
            
            if pid != -1 and pid in self.items_map:
                parent_item = self.items_map[pid]
                if item.parentItem() != parent_item:
                    item.setParentItem(parent_item)
                    item.setPos(data['x'], data['y'])
            else:
                if item.parentItem() is not None:
                    item.setParentItem(None)
                    item.setPos(data['x'], data['y'])