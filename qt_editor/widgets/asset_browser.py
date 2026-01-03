# RZMenu/qt_editor/widgets/asset_browser.py
from PySide6 import QtCore, QtWidgets, QtGui
from .panel_base import RZEditorPanel
from ..core import read
from ..utils.image_cache import ImageCache
from ..core.signals import SIGNALS

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

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setViewMode(QtWidgets.QListWidget.IconMode)
        self.list_widget.setIconSize(QtCore.QSize(64, 64))
        self.list_widget.setGridSize(QtCore.QSize(80, 100))
        self.list_widget.setResizeMode(QtWidgets.QListWidget.Adjust)
        self.list_widget.setSpacing(5)
        self.list_widget.setMovement(QtWidgets.QListView.Static)
        self.list_widget.setDragEnabled(True)
        
        # Override startDrag logic via events or subclassing? 
        # For simplicity, we can use the default but ensure MIME data is set.
        self.list_widget.startDrag = self._start_drag_override
        
        layout.addWidget(self.list_widget)

    def _start_drag_override(self, supported_actions):
        item = self.list_widget.currentItem()
        if not item:
            return

        image_id = item.data(QtCore.Qt.UserRole)
        
        drag = QtGui.QDrag(self.list_widget)
        mime_data = QtCore.QMimeData()
        # Data: The Integer ID of the image converted to bytes/string.
        mime_data.setData("application/x-rzmenu-image-id", QtCore.QByteArray(str(image_id).encode()))
        
        drag.setMimeData(mime_data)
        
        # Use item icon as drag pixmap
        icon = item.icon()
        if not icon.isNull():
            drag.setPixmap(icon.pixmap(64, 64))
            
        drag.exec_(supported_actions)

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
            else:
                # Use a default placeholder if not in cache
                # Since we are in the UI thread, we might not want to wait for Blender
                # But typically ImageCache would have been filled by the bridge.
                # For now, just a placeholder icon or empty.
                pass

            self.list_widget.addItem(item)
