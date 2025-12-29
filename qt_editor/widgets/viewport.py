# RZMenu/qt_editor/widgets/viewport.py
from PySide6 import QtWidgets, QtCore, QtGui
from ..systems import operators # Для вызова команд из контекстного меню

# Константы цветов
COLOR_SELECTED = QtGui.QColor(255, 255, 255) # Белый
COLOR_ACTIVE = QtGui.QColor(255, 140, 0)     # Оранжевый (Blender-like)
COLOR_NORMAL = QtGui.QColor(200, 200, 200)   # Серый

class RZElementItem(QtWidgets.QGraphicsRectItem):
    def __init__(self, uid, x, y, w, h, name, elem_type="box"):
        super().__init__(0, 0, w, h)
        self.uid = uid
        self.elem_type = elem_type # Тип элемента (text, image, box...)
        self.setPos(x, y)
        
        # Флаги: ItemIsSelectable позволяет Qt самому трекать выделение,
        # но мы управляем этим вручную через Scene, поэтому отключаем системное,
        # чтобы не было конфликтов отрисовки.
        self.setFlags(QtWidgets.QGraphicsItem.ItemUsesExtendedStyleOption)
        
        self.setBrush(QtGui.QBrush(QtGui.QColor(60, 60, 60, 200)))
        
        # Текст (Имя)
        self.text_item = QtWidgets.QGraphicsSimpleTextItem(name, self)
        self.text_item.setBrush(QtGui.QBrush(QtCore.Qt.white))
        # Сдвиг текста чуть внутрь
        self.text_item.setPos(5, 5)

    def set_visual_state(self, is_selected, is_active):
        """Обновляет цвет рамки в зависимости от статуса"""
        pen = QtGui.QPen()
        pen.setWidth(2 if (is_selected or is_active) else 1)
        
        if is_active:
            pen.setColor(COLOR_ACTIVE)
            # Чтобы активный был поверх остальных визуально (Z-index)
            self.setZValue(10) 
        elif is_selected:
            pen.setColor(COLOR_SELECTED)
            self.setZValue(5)
        else:
            pen.setColor(COLOR_NORMAL)
            self.setZValue(0)
            
        self.setPen(pen)


class RZViewportScene(QtWidgets.QGraphicsScene):
    # Сигналы остаются те же
    item_moved_signal = QtCore.Signal(float, float) 
    selection_changed_signal = QtCore.Signal(int, object) # id, modifier
    interaction_start_signal = QtCore.Signal()
    interaction_end_signal = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self._is_user_interaction = False # Флаг "Юзер тащит мышкой"
        
        # Для драга объектов (ЛКМ)
        self._drag_start_pos = None
        self._is_dragging_items = False
        
        # Для циклического выделения
        self._last_click_pos = None
        self._cycle_index = 0

    def mousePressEvent(self, event):
        # 1. СРЕДНЯЯ КНОПКА (MMB) - обрабатывается во View, тут игнорим
        if event.button() == QtCore.Qt.MiddleButton:
            event.ignore()
            return

        # 2. ПРАВАЯ КНОПКА (RMB) - Контекстное меню (вызывается само Qt), 
        # но нам нужно выделить объект под кнопкой перед вызовом меню, если он там есть
        if event.button() == QtCore.Qt.RightButton:
            item = self.item_at_event(event)
            if isinstance(item, RZElementItem):
                # Если кликнули ПКМ по невыделенному - выделяем его (как в винде)
                # Если по уже выделенному - оставляем группу
                if item.uid not in self.views()[0].parent_window.selected_ids:
                     self.selection_changed_signal.emit(item.uid, None)
            event.accept()
            return

        # 3. ЛЕВАЯ КНОПКА (LMB)
        if event.button() == QtCore.Qt.LeftButton:
            item = self.item_at_event(event)
            modifiers = event.modifiers()
            
            modifier_str = None
            if modifiers & QtCore.Qt.ControlModifier: modifier_str = 'CTRL'
            elif modifiers & QtCore.Qt.ShiftModifier: modifier_str = 'SHIFT'

            # --- ЛОГИКА ВЫДЕЛЕНИЯ ---
            if isinstance(item, RZElementItem):
                # Циклическое выделение (Cyclic Selection)
                # Работает только если кликаем БЕЗ модификаторов или с CTRL в "особом" режиме
                # Если клик близко к предыдущему - перебираем глубину
                scene_pos = event.scenePos()
                items_under = [i for i in self.items(scene_pos) if isinstance(i, RZElementItem)]
                
                # Проверка "тот же клик"
                is_same_click_spot = False
                if self._last_click_pos:
                    if (scene_pos - self._last_click_pos).manhattanLength() < 10:
                        is_same_click_spot = True
                
                if is_same_click_spot and len(items_under) > 1 and modifier_str is None:
                    # Инкремент цикла
                    self._cycle_index = (self._cycle_index + 1) % len(items_under)
                    target_item = items_under[self._cycle_index]
                    # Шлем сигнал на конкретный UID из стопки
                    self.selection_changed_signal.emit(target_item.uid, modifier_str)
                else:
                    # Новый клик
                    self._last_click_pos = scene_pos
                    self._cycle_index = 0
                    self.selection_changed_signal.emit(item.uid, modifier_str)

                # Подготовка к драгу
                self._is_dragging_items = True
                self._drag_start_pos = scene_pos
                self.interaction_start_signal.emit()
            else:
                # Клик в пустоту
                self.selection_changed_signal.emit(-1, modifier_str)
                self._last_click_pos = None

    def mouseMoveEvent(self, event):
        if self._is_dragging_items and self._drag_start_pos:
            current_pos = event.scenePos()
            delta = current_pos - self._drag_start_pos
            
            # Эмитим дельту
            self.item_moved_signal.emit(delta.x(), delta.y())
            
            # Обновляем старт и двигаем визуал
            self._drag_start_pos = current_pos
            
            # Визуально двигаем выбранное (UI Feedback)
            # Важно: двигаем только те айтемы, которые реально выделены в бэкенде
            # Но так как scene.selectedItems() мы не используем стандартный,
            # мы итерируемся по визуальным айтемам
            # (Оптимизация: лучше хранить список визуальных айтемов, но пока так)
            for item in self.items():
                if isinstance(item, RZElementItem) and item.zValue() >= 5: # >=5 значит selected
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
        """Возвращает верхний RZElementItem под мышью"""
        # Используем QtGui.QTransform()
        return self.itemAt(event.scenePos(), QtGui.QTransform())

    def update_scene(self, elements_data, selected_ids, active_id):
        """Перерисовка сцены на основе данных из core"""
        if self._is_user_interaction: return

        self.clear()
        # Огромный фон (для событий клика)
        self.addRect(-10000, -10000, 20000, 20000, QtGui.QPen(QtCore.Qt.NoPen), QtGui.QBrush(QtGui.QColor(30, 30, 30)))
        
        # Сетка (можно вынести в отдельный класс)
        self._draw_grid()

        for data in elements_data:
            # Получаем тип (если он есть в данных, иначе заглушка)
            elem_type = data.get('class_type', 'box') 
            
            item = RZElementItem(
                data['id'], data['pos_x'], data['pos_y'], 
                data['width'], data['height'], data['name'],
                elem_type
            )
            self.addItem(item)
            
            is_sel = data['id'] in selected_ids
            is_act = data['id'] == active_id
            
            item.set_visual_state(is_sel, is_act)

    def _draw_grid(self):
        # Простая сетка
        grid_step = 100
        pen = QtGui.QPen(QtGui.QColor(50, 50, 50))
        for x in range(0, 4000, grid_step):
            self.addLine(x, 0, x, 4000, pen)
        for y in range(0, 4000, grid_step):
            self.addLine(0, y, 4000, y, pen)


class RZViewportPanel(QtWidgets.QGraphicsView):
    def __init__(self):
        super().__init__()
        self.rz_scene = RZViewportScene()
        self.setScene(self.rz_scene)
        
        # Ссылка на родителя (RZMEditorWindow), чтобы доставать selected_ids для меню
        # Будет установлена при создании окна, но лучше иметь property
        self.parent_window = None 
        
        # Настройки навигации
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setDragMode(QtWidgets.QGraphicsView.NoDrag) # Мы реализуем свой драг
        
        # State для MMB Pan
        self._is_panning = False
        self._pan_start_pos = QtCore.QPoint()

        # Zoom limits
        self._zoom_level = 1.0
        self.MIN_ZOOM = 0.1
        self.MAX_ZOOM = 5.0

    def wheelEvent(self, event):
        """Зум колесиком"""
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor

        # Сохраняем текущий scale
        current_scale = self.transform().m11()

        if event.angleDelta().y() > 0:
            # Zoom In
            if current_scale < self.MAX_ZOOM:
                self.scale(zoom_in_factor, zoom_in_factor)
        else:
            # Zoom Out
            if current_scale > self.MIN_ZOOM:
                self.scale(zoom_out_factor, zoom_out_factor)

    def mousePressEvent(self, event):
        # MMB PAN START
        if event.button() == QtCore.Qt.MiddleButton:
            self._is_panning = True
            self._pan_start_pos = event.pos()
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            event.accept()
            return
            
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # MMB PAN MOVE
        if self._is_panning:
            delta = event.pos() - self._pan_start_pos
            self._pan_start_pos = event.pos()
            
            # Двигаем скроллбары
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
            
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # MMB PAN END
        if event.button() == QtCore.Qt.MiddleButton:
            self._is_panning = False
            self.setCursor(QtCore.Qt.ArrowCursor)
            event.accept()
            return
            
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        """ПКМ Меню"""
        # Определяем, над чем кликнули
        item = self.rz_scene.itemAt(self.mapToScene(event.pos()), QtGui.QTransform())
        
        menu = QtWidgets.QMenu(self)
        
        # --- СЦЕНАРИЙ 1: Клик по Элементу ---
        if isinstance(item, RZElementItem):
            # Заголовок (Имя элемента)
            label_action = menu.addAction(f"Item: {item.text_item.text()}")
            label_action.setEnabled(False) # Просто текст
            menu.addSeparator()
            
            # Общие действия
            action_del = menu.addAction("Delete")
            # Подключаем через лямбду к ActionManager родителя (если есть доступ)
            # Или напрямую вызываем оператор через input_manager (но тут UI)
            # Лучший способ - вызвать метод action_manager.run("rzm.delete")
            if self.parent_window and hasattr(self.parent_window, "action_manager"):
                action_del.triggered.connect(lambda: self.parent_window.action_manager.run("rzm.delete"))
            
            # Типо-зависимые действия (Placeholder)
            if item.elem_type == "text":
                menu.addSeparator()
                menu.addAction("Change Font...")
                menu.addAction("Font Size...")
            elif item.elem_type == "image":
                menu.addSeparator()
                menu.addAction("Reload Image")
                
        # --- СЦЕНАРИЙ 2: Клик по пустоте ---
        else:
            menu.addAction("New Rectangle").triggered.connect(lambda: print("TODO: Create Rect"))
            menu.addAction("New Text").triggered.connect(lambda: print("TODO: Create Text"))
            menu.addSeparator()
            if self.parent_window:
                menu.addAction("Reset View").triggered.connect(lambda: self.parent_window.action_manager.run("rzm.view_reset"))

        # Показываем меню
        menu.exec(event.globalPos())