# RZMenu/qt_editor/widgets/asset_browser.py
from PySide6 import QtCore, QtWidgets, QtGui
from .panel_base import RZEditorPanel
from ..core import read, blender_bridge
from ..utils.image_cache import ImageCache
from ..core.signals import SIGNALS

class RZAssetListWidget(QtWidgets.QListWidget):
    """
    Handles asset list display and custom internal MIME data for drag & drop.
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
        # Note: We disable AcceptDrops here because we use an Import button now
        self.setAcceptDrops(False) 

    def mimeData(self, items):
        """Format mime data for internal dragging so Inspector can recognize it."""
        if not items:
            return None
        
        item = items[0]
        image_id = item.data(QtCore.Qt.UserRole)
        
        mime_data = QtCore.QMimeData()
        # Encode as bytes for the mime data
        mime_data.setData("application/x-rzmenu-image-id", QtCore.QByteArray(str(image_id).encode('utf-8')))
        return mime_data


class RZAssetBrowserPanel(RZEditorPanel):
    PANEL_ID = "ASSETS"
    PANEL_NAME = "Assets"
    PANEL_ICON = "image"

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Toolbar
        toolbar = QtWidgets.QHBoxLayout()
        
        self.btn_import = QtWidgets.QPushButton("Import")
        self.btn_import.clicked.connect(blender_bridge.import_image_from_dialog)
        toolbar.addWidget(self.btn_import)
        
        self.btn_reload = QtWidgets.QPushButton("↺")
        self.btn_reload.setToolTip("Reload Base Icons & Refresh List")
        self.btn_reload.setFixedWidth(30)
        self.btn_reload.clicked.connect(self.on_reload_clicked)
        toolbar.addWidget(self.btn_reload)
        
        toolbar.addStretch()

        toolbar.addWidget(QtWidgets.QLabel("Filter:"))
        self.combo_filter = QtWidgets.QComboBox()
        self.combo_filter.addItems(["All", "Custom", "Base", "Captured"])
        self.combo_filter.currentTextChanged.connect(self.rebuild_view)
        toolbar.addWidget(self.combo_filter)

        toolbar.addWidget(QtWidgets.QLabel("Sort:"))
        self.combo_sort = QtWidgets.QComboBox()
        self.combo_sort.addItems(["ID (New-Old)", "ID (Old-New)", "A-Z", "Z-A"])
        self.combo_sort.currentTextChanged.connect(self.rebuild_view)
        toolbar.addWidget(self.combo_sort)
        
        layout.addLayout(toolbar)

        # Asset List
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
        """Initial refresh entry point."""
        # Auto-load check: if no images, try to load base icons once
        images = read.get_available_images()
        if not images:
            print("AssetBrowser: No images found, auto-reloading base icons...")
            blender_bridge.reload_base_icons()
            return # reload_base_icons will emit structure_changed, triggering this again
            
        self.rebuild_view()

    def on_reload_clicked(self):
        """Manually trigger base icon reload from Blender."""
        blender_bridge.reload_base_icons()
        self.rebuild_view()

    def rebuild_view(self):
        """Fetches images, applies filters/sorting, and populates the list."""
        all_images = read.get_available_images()
        
        # 1. Filter
        filter_text = self.combo_filter.currentText().upper()
        if filter_text == "ALL":
            filtered = all_images
        else:
            filtered = [img for img in all_images if img.get('source_type') == filter_text]

        # 2. Sort
        sort_mode = self.combo_sort.currentText()
        if sort_mode == "ID (New-Old)":
            filtered.sort(key=lambda x: x['id'], reverse=True)
        elif sort_mode == "ID (Old-New)":
            filtered.sort(key=lambda x: x['id'])
        elif sort_mode == "A-Z":
            filtered.sort(key=lambda x: x['name'].lower())
        elif sort_mode == "Z-A":
            filtered.sort(key=lambda x: x['name'].lower(), reverse=True)

        # 3. Populate
        self.list_widget.clear()
        cache = ImageCache.instance()

        for img_data in filtered:
            img_id = img_data['id']
            name = img_data['name']

            item = QtWidgets.QListWidgetItem(name)
            item.setData(QtCore.Qt.UserRole, img_id)

            pixmap = cache.get_pixmap(img_id)
            if pixmap:
                item.setIcon(QtGui.QIcon(pixmap))
            
            self.list_widget.addItem(item)
