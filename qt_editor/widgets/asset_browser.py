# RZMenu/qt_editor/widgets/asset_browser.py
from PySide6 import QtCore, QtWidgets, QtGui
from .panel_base import RZEditorPanel
from ..core import read
from ..utils.image_cache import ImageCache
from ..core.signals import SIGNALS

class RZAssetListWidget(QtWidgets.QListWidget):
    """
    Subclass for handled Asset List Drag & Drop.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QtWidgets.QListWidget.IconMode)
        self.setIconSize(QtCore.QSize(64, 64))
        self.setGridSize(QtCore.QSize(80, 100))
        self.setResizeMode(QtWidgets.QListWidget.Adjust)
        self.setSpacing(5)
        self.setMovement(QtWidgets.QListView.Static)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)

    def mimeData(self, items):
        """Format mime data for internal dragging."""
        if not items:
            return None
        
        item = items[0]
        image_id = item.data(QtCore.Qt.UserRole)
        
        mime_data = QtCore.QMimeData()
        mime_data.setData("application/x-rzmenu-image-id", QtCore.QByteArray(str(image_id).encode('utf-8')))
        return mime_data

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                print(f"Importing: {path}")
                # Trigger import logic via core
                from .. import core
                if hasattr(core, 'import_image_from_path'):
                    core.import_image_from_path(path)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class RZAssetBrowserPanel(RZEditorPanel):
    PANEL_ID = "ASSETS"
    PANEL_NAME = "Assets"
    PANEL_ICON = "image"

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.list_widget = RZAssetListWidget()
        layout.addWidget(self.list_widget)

    def _connect_signals(self):
        SIGNALS.structure_changed.connect(self.refresh_data)

    def _disconnect_signals(self):
        try:
            SIGNALS.structure_changed.disconnect(self.refresh_data)
        except (RuntimeError, TypeError):
            pass

    def refresh_data(self):
        """Fetch and display current images from core."""
        images = read.get_available_images()
        self.list_widget.clear()

        cache = ImageCache.instance()

        for img_data in images:
            img_id = img_data['id']
            name = img_data['name']

            item = QtWidgets.QListWidgetItem(name)
            item.setData(QtCore.Qt.UserRole, img_id)

            pixmap = cache.get_pixmap(img_id)
            if pixmap:
                item.setIcon(QtGui.QIcon(pixmap))
            
            self.list_widget.addItem(item)
