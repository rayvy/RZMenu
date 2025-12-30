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
        
        # --- FIX BOX SELECT: Flag ItemIsSelectable ---
        # Чтобы RubberBandDrag видел элементы, они должны быть Selectable.
        # Но мы отключим системную отрисовку выделения, переопределив paint (или полагаясь на наш update).
        self.setFlags(
            QtWidgets.QGraphicsItem.ItemUsesExtendedStyleOption | 
            QtWidgets.QGraphicsItem.ItemIsSelectable
        )
        
        self.setBrush(QtGui.QBrush(QtGui.QColor(60, 60, 60, 200)))
        
        self.text_item = QtWidgets.QGraphicsSimpleTextItem(name, self)
        self.text_item.setBrush(QtGui.QBrush(QtCore.Qt.white))
        self.text_item.setPos(5, 5)

    def set_visual_state(self, is_selected, is_active):
        """Ручное управление стилем, игнорируя нативное выделение Qt"""
        # Снимаем нативный селект визуально, чтобы не было пунктирной рамки поверх нашей
        if self.isSelected() != is_selected:
            self.setSelected(is_selected)

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
        self.setPos(x, y)
        self.setRect(0, 0, w, h)
    
    def itemChange(self, change, value):
        # Блокируем нативное изменение позиции, если оно пришло не от нас
        # (Хотя в NoDrag режиме это и так не должно происходить)
        return super().itemChange(change, value)


class RZViewportScene(QtWidgets.QGraphicsScene):
    item_moved_signal = QtCore.Signal(float, float) 
    selection_changed_signal = QtCore.Signal(object, object) # id (int) OR ids (list), modifiers
    interaction_start_signal = QtCore.Signal()
    interaction_end_signal = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self._is_user_interaction = False
        
        self._drag_start_pos = None
        self._is_dragging_items = False
        
        # Кэш элементов
        self._items_map = {} 
        
        self._init_background()

    def _init_background(self):
        self.setSceneRect(-10000, -10000, 20000, 20000)
        self.addRect(-10000, -10000, 20000, 20000, QtGui.QPen(QtCore.Qt.NoPen), QtGui.QBrush(QtGui.QColor(30, 30, 30)))
        
        grid_step = 100
        pen = QtGui.QPen(QtGui.QColor(50, 50, 50))
        for x in range(0, 4000, grid_step):
            self.addLine(x, 0, x, 4000, pen)
        for y in range(0, 4000, grid_step):
            self.addLine(0, y, 4000, y, pen)

    def mousePressEvent(self, event):
        # 1. Пропускаем Middle Button (Pan) и Right Button (Context Menu)
        if event.button() == QtCore.Qt.MiddleButton:
            return # Ignore -> Parent View handles Pan
        
        # 2. Логика выделения (Left Button)
        if event.button() == QtCore.Qt.LeftButton:
            item = self.item_at_event(event)
            modifiers = event.modifiers()
            
            modifier_str = None
            if modifiers & QtCore.Qt.ControlModifier: modifier_str = 'CTRL'
            elif modifiers & QtCore.Qt.ShiftModifier: modifier_str = 'SHIFT'

            # Если кликнули по элементу
            if isinstance(item, RZElementItem):
                self._handle_item_click(item, event, modifier_str)
                
                # Начинаем драг (перемещение)
                self._is_dragging_items = True
                self._drag_start_pos = event.scenePos()
                self.interaction_start_signal.emit()
                event.accept() 
            else:
                # Кликнули в пустоту -> Это обработает RZViewportPanel (Box Select)
                # Но мы должны убедиться, что драг не начнется здесь
                super().mousePressEvent(event)
                # Отправляем сигнал отмены выделения, только если нет модификаторов.
                # Но ViewportPanel перехватит это для RubberBand, так что здесь можно ничего не делать.
                pass

    def _handle_item_click(self, clicked_item, event, modifier_str):
        """
        FIX CYCLIC SELECTION:
        Алгоритм: Получаем стэк элементов под мышью.
        Если текущий выделенный элемент находится в этом стэке, выбираем СЛЕДУЮЩИЙ за ним.
        Иначе выбираем верхний.
        """
        # Получаем все элементы под курсором
        items_under = [i for i in self.items(event.scenePos()) if isinstance(i, RZElementItem)]
        
        if not items_under: 
            return # Should not happen based on caller

        # Получаем текущие выделенные ID из родительского окна
        # (Костыль, но эффективный способ узнать текущее состояние)
        current_selected_ids = self.views()[0].parent_window.selected_ids
        
        target_uid = clicked_item.uid

        # Логика цикличности применяется только если нет модификаторов (простой клик)
        # И если под мышью больше 1 элемента
        if modifier_str is None and len(items_under) > 1:
            # Ищем, есть ли в текущем выделении элементы из стэка под мышью
            # Приоритет: ищем первый попавшийся выделенный элемент в стэке
            current_index = -1
            for idx, item in enumerate(items_under):
                if item.uid in current_selected_ids:
                    current_index = idx
                    break
            
            if current_index != -1:
                # Если нашли выделенный, берем следующий (циклически)
                next_index = (current_index + 1) % len(items_under)
                target_uid = items_under[next_index].uid
            else:
                # Если ничего из стэка не выделено, берем самый верхний (0)
                target_uid = items_under[0].uid
        
        # Эмитим сигнал
        self.selection_changed_signal.emit(target_uid, modifier_str)


    def mouseMoveEvent(self, event):
        if self._is_dragging_items and self._drag_start_pos:
            current_pos = event.scenePos()
            delta = current_pos - self._drag_start_pos
            
            self.item_moved_signal.emit(delta.x(), delta.y())
            self._drag_start_pos = current_pos
            
            # Визуальный сдвиг (для плавности)
            for item in self.items():
                if isinstance(item, RZElementItem) and item.uid in self.views()[0].parent_window.selected_ids:
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
        
        self.setSceneRect(-10000, -10000, 20000, 20000)

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
            if uid in self._items_map:
                item = self._items_map[uid]
                item.update_geometry(data['pos_x'], data['pos_y'], data['width'], data['height'])
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
        
        # --- FIX BOX SELECT: Init State ---
        self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
        
        self._is_panning = False
        self._pan_start_pos = QtCore.QPoint()
        self.MIN_ZOOM = 0.1
        self.MAX_ZOOM = 5.0

    def pan_view(self, delta_x, delta_y):
        h_bar = self.horizontalScrollBar()
        v_bar = self.verticalScrollBar()
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
        # MMB PAN
        if event.button() == QtCore.Qt.MiddleButton:
            self._is_panning = True
            self._pan_start_pos = event.pos()
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            event.accept()
            return
        
        # LMB Logic
        if event.button() == QtCore.Qt.LeftButton:
            item = self.rz_scene.itemAt(self.mapToScene(event.pos()), QtGui.QTransform())
            
            # --- FIX BOX SELECT START ---
            # Если под мышкой НЕТ RZElementItem -> Включаем Box Select
            if not isinstance(item, RZElementItem):
                self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)
            else:
                self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
            # --- FIX BOX SELECT END ---

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
        # MMB Release
        if event.button() == QtCore.Qt.MiddleButton:
            self._is_panning = False
            self.setCursor(QtCore.Qt.ArrowCursor)
            event.accept()
            return

        # --- FIX BOX SELECT FINISH ---
        # Если мы отпускаем ЛКМ и был режим RubberBand -> Собираем урожай
        if self.dragMode() == QtWidgets.QGraphicsView.RubberBandDrag:
            # Получаем выделенные элементы (Qt сам их нашел)
            selected_items = self.scene().selectedItems()
            
            # Извлекаем ID
            ids = []
            for item in selected_items:
                if isinstance(item, RZElementItem):
                    ids.append(item.uid)
            
            # Отправляем сигнал (modifier передаем от события)
            modifier_str = None
            modifiers = event.modifiers()
            if modifiers & QtCore.Qt.ControlModifier: modifier_str = 'CTRL' # Replace/Deselect logic could be implemented here
            elif modifiers & QtCore.Qt.ShiftModifier: modifier_str = 'SHIFT' # Add logic
            
            # Если бокс селект был в пустоту (ничего не задел) и без шифта -> это сброс выделения
            if not ids and modifier_str is None:
                self.rz_scene.selection_changed_signal.emit(-1, None)
            elif ids:
                self.rz_scene.selection_changed_signal.emit(ids, modifier_str)

            # Выключаем режим и сбрасываем Qt-шное выделение (мы рисуем сами)
            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
            self.scene().clearSelection()
        
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
        else:
            # Преобразуем координаты
            scene_pos = self.mapToScene(event.pos())
            x, y = int(scene_pos.x()), int(scene_pos.y())

            # --- ИСПРАВЛЕННОЕ МЕНЮ СОЗДАНИЯ ---
            add_menu = menu.addMenu("Add Element")
            
            # 1. Containers
            add_menu.addAction("Container").triggered.connect(
                lambda: self.parent_window.action_manager.run("rzm.create", class_type="CONTAINER", x=x, y=y)
            )
            add_menu.addAction("Grid Container").triggered.connect(
                lambda: self.parent_window.action_manager.run("rzm.create", class_type="GRID_CONTAINER", x=x, y=y)
            )
            
            add_menu.addSeparator()
            
            # 2. Widgets
            add_menu.addAction("Button").triggered.connect(
                lambda: self.parent_window.action_manager.run("rzm.create", class_type="BUTTON", x=x, y=y)
            )
            add_menu.addAction("Slider").triggered.connect(
                lambda: self.parent_window.action_manager.run("rzm.create", class_type="SLIDER", x=x, y=y)
            )
            add_menu.addAction("Text Label").triggered.connect(
                lambda: self.parent_window.action_manager.run("rzm.create", class_type="TEXT", x=x, y=y)
            )
            
            add_menu.addSeparator()
            
            # 3. Misc
            add_menu.addAction("Anchor").triggered.connect(
                lambda: self.parent_window.action_manager.run("rzm.create", class_type="ANCHOR", x=x, y=y)
            )

            menu.addSeparator()

            if self.parent_window:
                menu.addAction("Reset View").triggered.connect(lambda: self.parent_window.action_manager.run("rzm.view_reset"))

        menu.exec(event.globalPos())