# RZMenu/qt_editor/widgets/hierarchy.py

from PySide6 import QtWidgets, QtCore, QtGui

class HierarchyWidget(QtWidgets.QTreeWidget):
    element_selected = QtCore.Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setIndentation(15)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.bridge = None # Set externally

        self.setStyleSheet("QTreeWidget { background-color: #222; border: none; color: #ccc; } QTreeWidget::item { padding: 4px; } QTreeWidget::item:selected { background-color: #444; }")
        
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.currentItemChanged.connect(self._on_current_item_changed)

    def show_context_menu(self, pos):
        if not self.bridge: return
        item = self.itemAt(pos)
        menu = QtWidgets.QMenu(self)
        
        parent_id = -1
        if item:
            parent_id = item.data(0, QtCore.Qt.UserRole)
        
        menu.addAction("Container").triggered.connect(lambda: self.bridge.create_element('CONTAINER', parent_id))
        menu.addAction("Button").triggered.connect(lambda: self.bridge.create_element('BUTTON', parent_id))
        
        if item:
            menu.addSeparator()
            menu.addAction("Delete").triggered.connect(lambda: self.bridge.delete_element(parent_id))
            
        menu.exec(self.mapToGlobal(pos))

    def rebuild(self, elements):
        """
        Builds the tree. 
        'elements' can be a list of Blender Objects OR a list of dicts from DataManager.
        """
        self.blockSignals(True)
        self.clear()
        
        item_map = {}
        raw_map = {} 
        
        # 1. Create all items
        for el in elements:
            # Handle both Dict and Object access
            if isinstance(el, dict):
                el_id = el['id']
                el_name = el['element_name']
                el_type = el['elem_class']
                parent_id = el.get('parent_id', -1)
            else:
                el_id = el.id
                el_name = el.element_name
                el_type = el.elem_class
                parent_id = el.parent_id
            
            item = QtWidgets.QTreeWidgetItem([el_name])
            item.setData(0, QtCore.Qt.UserRole, el_id)
            
            # Icons
            icon_type = QtWidgets.QStyle.SP_FileIcon
            if el_type == 'CONTAINER': icon_type = QtWidgets.QStyle.SP_DirIcon
            elif el_type == 'BUTTON': icon_type = QtWidgets.QStyle.SP_DialogOkButton
            
            item.setIcon(0, self.style().standardIcon(icon_type))
            
            item_map[el_id] = item
            raw_map[el_id] = {'parent_id': parent_id}

        # 2. Build Hierarchy
        for el_id, item in item_map.items():
            pid = raw_map[el_id]['parent_id']
            if pid != -1 and pid in item_map:
                item_map[pid].addChild(item)
            else:
                self.addTopLevelItem(item)
        
        self.expandAll()
        self.blockSignals(False)

    def _on_current_item_changed(self, current, previous):
        if current:
            self.element_selected.emit(current.data(0, QtCore.Qt.UserRole))
        else:
            self.element_selected.emit(None)

    def select_element(self, element_id):
        self.blockSignals(True)
        if element_id is None:
            self.clearSelection()
        else:
            # Simple linear search (fast enough for <1000 items)
            it = QtWidgets.QTreeWidgetItemIterator(self)
            found = False
            while it.value():
                item = it.value()
                if item.data(0, QtCore.Qt.UserRole) == element_id:
                    self.setCurrentItem(item)
                    self.scrollToItem(item)
                    found = True
                    break
                it += 1
            if not found:
                self.clearSelection()
        self.blockSignals(False)