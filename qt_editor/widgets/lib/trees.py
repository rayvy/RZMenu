# RZMenu/qt_editor/widgets/lib/trees.py
from PySide6 import QtWidgets, QtCore
from .theme import get_current_theme


class RZBaseTreeWidget(QtWidgets.QTreeWidget):
    """
    Base tree widget with theming support and common functionality.
    Provides drag & drop, selection, and theme-aware styling.
    """

    # Signals for column clicks (to be overridden in subclasses)
    item_column_clicked = QtCore.Signal(QtWidgets.QTreeWidgetItem, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)

        self.itemClicked.connect(self._on_item_clicked)

        # Apply theme
        self.apply_theme()

    def apply_theme(self):
        """Apply theme colors to the tree."""
        theme = get_current_theme()

        # Set stylesheet for the tree
        self.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {theme.get('bg_input', '#252930')};
                color: {theme.get('text_main', '#E0E2E4')};
                border: 1px solid {theme.get('border_main', '#3A404A')};
            }}

            QTreeWidget::item {{
                color: {theme.get('text_main', '#E0E2E4')};
                padding: 2px;
            }}

            QTreeWidget::item:selected {{
                background-color: {theme.get('selection', '#4A6E91')};
                color: {theme.get('text_bright', '#FFFFFF')};
            }}

            QTreeWidget::item:hover {{
                background-color: {theme.get('bg_panel', '#2C313A')};
            }}
        """)

    def _on_item_clicked(self, item, column):
        """Handle item clicks, emit signal for column-specific handling."""
        self.item_column_clicked.emit(item, column)


class RZDraggableTreeWidget(RZBaseTreeWidget):
    """
    Enhanced tree widget with drag & drop reordering support.
    Emits signals when items are reordered.
    """

    # Signal emitted when items are reordered: (moved_item_id, new_parent_id)
    items_reordered = QtCore.Signal(int, object)

    def __init__(self, parent=None):
        super().__init__(parent)

    def dropEvent(self, event):
        """Handle drop events for reordering."""
        source_items = self.selectedItems()
        if not source_items:
            return

        # Standard Qt drop handling
        super().dropEvent(event)

        # Calculate new positions
        first_item = source_items[0]
        moved_id = first_item.data(0, QtCore.Qt.UserRole)

        parent_item = first_item.parent()
        new_parent_id = parent_item.data(0, QtCore.Qt.UserRole) if parent_item else None

        self.items_reordered.emit(moved_id, new_parent_id)

    def get_expanded_item_ids(self):
        """Get IDs of currently expanded items."""
        expanded_ids = set()
        it = QtWidgets.QTreeWidgetItemIterator(self)
        while it.value():
            item = it.value()
            if item.isExpanded():
                item_id = item.data(0, QtCore.Qt.UserRole)
                if item_id is not None:
                    expanded_ids.add(item_id)
            it += 1
        return expanded_ids

    def set_expanded_items(self, expanded_ids):
        """Set which items should be expanded."""
        it = QtWidgets.QTreeWidgetItemIterator(self)
        while it.value():
            item = it.value()
            item_id = item.data(0, QtCore.Qt.UserRole)
            if item_id in expanded_ids:
                item.setExpanded(True)
            it += 1
