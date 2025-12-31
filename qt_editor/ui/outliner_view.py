# RZMenu/qt_editor/ui/outliner_view.py
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Signal
from typing import List, Set

from ..backend.dtos import RZElement

class OutlinerView(QtWidgets.QTreeWidget):
    """
    A view to display a hierarchical list of RZElement DTOs.
    It is a "dumb" component that only displays data and emits user interactions.
    """
    # Emits a set of selected element IDs
    selection_changed = Signal(set) 
    # Emits the ID of an element whose visibility icon was clicked
    visibility_toggled = Signal(int)
    # Emits the ID of an element whose lock icon was clicked
    lock_toggled = Signal(int)
    # Emits when an element is dragged to a new parent or reordered
    element_reparented = Signal(int, int) # child_id, new_parent_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._block_signals = False
        
        # --- Setup UI ---
        self.setHeaderLabels(["Name", "V", "L"])
        self.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.header().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(1, 25)
        self.setColumnWidth(2, 25)
        
        # --- Setup Drag & Drop ---
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)

        # --- Connect Signals ---
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.itemClicked.connect(self._on_item_clicked)

    def update_tree(self, root_elements: List[RZElement]):
        """Rebuilds the entire tree from a list of root RZElement DTOs."""
        self._block_signals = True
        
        # Save expanded state
        expanded_ids = {
            self.topLevelItem(i).data(0, QtCore.Qt.ItemDataRole.UserRole)
            for i in range(self.topLevelItemCount()) if self.topLevelItem(i).isExpanded()
        }

        self.clear()

        for root_dto in root_elements:
            self._add_tree_item(root_dto, None, expanded_ids)
            
        self._block_signals = False

    def _add_tree_item(self, dto: RZElement, parent_widget: QtWidgets.QTreeWidgetItem | None, expanded_ids: Set[int]):
        """Recursively adds a DTO and its children to the tree."""
        item = QtWidgets.QTreeWidgetItem()
        item.setText(0, dto.name)
        item.setData(0, QtCore.Qt.ItemDataRole.UserRole, dto.id)
        
        # Visibility Icon (Column 1)
        item.setText(1, "👁️" if not dto.is_hidden else "❌")
        item.setTextAlignment(1, QtCore.Qt.AlignmentFlag.AlignCenter)
        
        # Lock Icon (Column 2)
        item.setText(2, "🔒" if dto.is_locked else "✔️")
        item.setTextAlignment(2, QtCore.Qt.AlignmentFlag.AlignCenter)
        
        if parent_widget is None:
            self.addTopLevelItem(item)
        else:
            parent_widget.addChild(item)

        if dto.id in expanded_ids or parent_widget is None:
            item.setExpanded(True)
            
        for child_dto in dto.children:
            self._add_tree_item(child_dto, item, expanded_ids)

    def set_selection_from_ids(self, ids: Set[int]):
        """Updates the selection in the tree based on a set of IDs."""
        self._block_signals = True
        self.clearSelection()
        if not ids:
            self._block_signals = False
            return
            
        it = QtWidgets.QTreeWidgetItemIterator(self)
        while it.value():
            item = it.value()
            if item.data(0, QtCore.Qt.ItemDataRole.UserRole) in ids:
                item.setSelected(True)
            it += 1
        self._block_signals = False

    def _on_selection_changed(self):
        """Emits the IDs of the currently selected items."""
        if self._block_signals:
            return
        selected_ids = {item.data(0, QtCore.Qt.ItemDataRole.UserRole) for item in self.selectedItems()}
        self.selection_changed.emit(selected_ids)

    def _on_item_clicked(self, item: QtWidgets.QTreeWidgetItem, column: int):
        """Handles clicks on the visibility and lock icons."""
        item_id = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if item_id is None:
            return
            
        if column == 1:
            self.visibility_toggled.emit(item_id)
        elif column == 2:
            self.lock_toggled.emit(item_id)
            
    def dropEvent(self, event: QtGui.QDropEvent):
        """Handles when an item is dropped to reparent it."""
        # Find the item being moved
        source_item = self.selectedItems()[0] if self.selectedItems() else None
        if not source_item:
            return

        child_id = source_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        
        # Let Qt handle the move first to find the new parent
        super().dropEvent(event)
        
        # After the move, find the new parent
        new_parent_item = source_item.parent()
        new_parent_id = new_parent_item.data(0, QtCore.Qt.ItemDataRole.UserRole) if new_parent_item else -1
        
        self.element_reparented.emit(child_id, new_parent_id)
        event.accept()
