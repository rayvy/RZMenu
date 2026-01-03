# RZMenu/qt_editor/widgets/lib/inputs.py
from PySide6 import QtWidgets, QtCore, QtGui
from .theme import get_current_theme
from ...utils.image_cache import ImageCache

class RZImageComboBox(QtWidgets.QComboBox):
    """
    ComboBox for image selection with drag-and-drop support.
    """
    value_changed = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.apply_theme()
        self.currentIndexChanged.connect(self._on_index_changed)

    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"""
            QComboBox {{
                background-color: {theme.get('bg_input', '#252930')};
                border: 1px solid {theme.get('border_input', '#4A505A')};
                border-radius: 3px;
                padding: 3px;
                color: {theme.get('text_main', '#E0E2E4')};
            }}
            QComboBox:focus {{ border: 1px solid {theme.get('accent', '#5298D4')}; }}
            QComboBox::drop-down {{ border-left: 1px solid {theme.get('border_input', '#4A505A')}; }}
        """)

    def update_items(self, images_list):
        """Populate the combo box with images: [{'id': 1, 'name': 'Name'}]"""
        self.blockSignals(True)
        current_id = self.currentData()
        self.clear()
        
        # Add a default "None" option
        self.addItem("None", -1)
        
        cache = ImageCache.instance()
        for img in images_list:
            img_id = img['id']
            name = img['name']
            pixmap = cache.get_pixmap(img_id)
            icon = QtGui.QIcon(pixmap) if pixmap else QtGui.QIcon()
            self.addItem(icon, name, img_id)
            
        # Try to restore selection
        if current_id is not None:
            self.set_value(current_id)
            
        self.blockSignals(False)

    def set_value(self, image_id):
        """Find item with this ID and select it."""
        index = self.findData(image_id)
        if index != -1:
            self.setCurrentIndex(index)
        else:
            self.setCurrentIndex(0) # Default to None

    def _on_index_changed(self, index):
        image_id = self.itemData(index)
        if image_id is not None:
            self.value_changed.emit(image_id)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-rzmenu-image-id"):
            event.acceptProposedAction()

    def dropEvent(self, event):
        data = event.mimeData().data("application/x-rzmenu-image-id")
        try:
            image_id = int(data.data().decode('utf-8'))
            self.set_value(image_id)
            event.acceptProposedAction()
        except (ValueError, TypeError):
            pass

