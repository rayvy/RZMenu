# RZMenu/qt_editor/widgets/outliner.py
from PySide6 import QtWidgets, QtCore, QtGui

class RZDraggableTree(QtWidgets.QTreeWidget):
    """Иерархическое дерево с поддержкой перетаскивания (Re-parenting)"""
    internal_reorder_signal = QtCore.Signal(int, object) # moved_id, new_parent_id

    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setHeaderLabels(["Name", "Vis"])
        
        # Настройка колонок
        self.setColumnWidth(0, 200)
        self.setColumnWidth(1, 30)
        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.header().setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)

    def dropEvent(self, event):
        # Стандартная обработка перемещения внутри дерева
        # Qt сам обработает визуальное перемещение, но нам нужно отправить сигнал
        # в backend, чтобы обновить реальные данные.
        
        source_items = self.selectedItems()
        if not source_items: return

        # Определяем цель
        target_item = self.itemAt(event.position().toPoint())
        drop_indicator = self.dropIndicatorPosition()
        
        target_id = None # Root
        if target_item:
            target_id = target_item.data(0, QtCore.Qt.UserRole)
            
            # Если кидаем "между" элементами, родителем становится родитель таргета
            if drop_indicator != QtWidgets.QAbstractItemView.OnItem:
                parent = target_item.parent()
                target_id = parent.data(0, QtCore.Qt.UserRole) if parent else None

        # Вызываем базовый метод, чтобы Qt обновил UI (опционально, можно блокировать)
        super().dropEvent(event)

        # Эмитим сигнал для каждого перемещенного элемента
        # (Упрощенно: считаем, что перемещаем под нового родителя)
        for item in source_items:
            moved_id = item.data(0, QtCore.Qt.UserRole)
            # Внимание: здесь мы предполагаем изменение родителя.
            # Если нужно точное изменение порядка (index), потребуется более сложная логика.
            # Для заглушки достаточно смены родителя.
            self.internal_reorder_signal.emit(moved_id, target_id)


class RZMOutlinerPanel(QtWidgets.QWidget):
    # (Список выбранных ID, Активный ID)
    selection_changed = QtCore.Signal(list, int)
    items_reordered = QtCore.Signal(int, object) # id, new_parent

    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        self.tree = RZDraggableTree()
        self.tree.itemSelectionChanged.connect(self._on_qt_selection_changed)
        self.tree.internal_reorder_signal.connect(self.items_reordered)
        
        # Стили
        self.tree.setStyleSheet("""
            QTreeWidget { background-color: #2b2b2b; border: none; font-size: 12px; }
            QTreeWidget::item { padding: 4px; color: #e0e0e0; }
            QTreeWidget::item:selected { background-color: #405560; color: white; }
            QTreeWidget::item:hover { background-color: #333; }
        """)
        layout.addWidget(self.tree)
        
        self._block_signals = False

    def _on_qt_selection_changed(self):
        if self._block_signals: return
        
        selected_items = self.tree.selectedItems()
        ids = [item.data(0, QtCore.Qt.UserRole) for item in selected_items]
        
        current = self.tree.currentItem()
        active_id = -1
        if current and current.isSelected():
            active_id = current.data(0, QtCore.Qt.UserRole)
        elif ids:
            active_id = ids[0]
            
        self.selection_changed.emit(ids, active_id)

    def set_selection_silent(self, ids_set, active_id):
        self._block_signals = True
        self.tree.clearSelection()
        
        iterator = QtWidgets.QTreeWidgetItemIterator(self.tree)
        item_to_focus = None
        
        while iterator.value():
            item = iterator.value()
            uid = item.data(0, QtCore.Qt.UserRole)
            if uid in ids_set:
                item.setSelected(True)
                if uid == active_id:
                    item_to_focus = item
            iterator += 1
        
        if item_to_focus:
            self.tree.setCurrentItem(item_to_focus)
            self.tree.scrollToItem(item_to_focus)
            
        self._block_signals = False

    def update_ui(self, elements_list):
        """
        Builds the tree hierarchy.
        Expects elements_list to contain dicts with 'id', 'name', 'parent_id', 'class_type', 'is_hidden'.
        """
        self._block_signals = True
        
        # Сохраняем состояние разворачивания (expanded)
        expanded_ids = set()
        iterator = QtWidgets.QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            if item.isExpanded():
                expanded_ids.add(item.data(0, QtCore.Qt.UserRole))
            iterator += 1

        self.tree.clear()
        
        # 1. Map id -> data
        data_map = {d['id']: d for d in elements_list}
        # 2. Map id -> QTreeWidgetItem
        item_map = {}
        
        # Создаем все айтемы
        for data in elements_list:
            item = QtWidgets.QTreeWidgetItem()
            item.setText(0, data.get('name', 'Unnamed'))
            item.setData(0, QtCore.Qt.UserRole, data['id'])
            
            # Icon setup based on type
            ctype = data.get('class_type', 'CONTAINER')
            icon = QtWidgets.QStyle.SP_FileIcon
            if "CONTAINER" in ctype:
                icon = QtWidgets.QStyle.SP_DirIcon
            elif "BUTTON" in ctype:
                icon = QtWidgets.QStyle.SP_DialogOkButton
            elif "TEXT" in ctype:
                icon = QtWidgets.QStyle.SP_FileDialogDetailedView
            
            item.setIcon(0, self.style().standardIcon(icon))
            
            # Visibility Column
            vis_text = "👁" if not data.get('is_hidden', False) else "❌"
            item.setText(1, vis_text)
            item.setTextAlignment(1, QtCore.Qt.AlignCenter)
            
            item_map[data['id']] = item

        # 3. Build Hierarchy
        for data in elements_list:
            uid = data['id']
            pid = data.get('parent_id') # Может быть None или -1
            
            item = item_map[uid]
            
            if pid is not None and pid in item_map:
                parent_item = item_map[pid]
                parent_item.addChild(item)
            else:
                self.tree.addTopLevelItem(item)
                
        # Восстанавливаем Expanded
        for uid, item in item_map.items():
            if uid in expanded_ids:
                item.setExpanded(True)
            # Всегда разворачиваем рут, если это удобно
            if item.parent() is None:
                item.setExpanded(True)

        self._block_signals = False