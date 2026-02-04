# RZMenu/qt_editor/widgets/asset_browser.py
from PySide6 import QtCore, QtWidgets, QtGui
from .panel_base import RZEditorPanel
from .. import core  # <--- ДОБАВЛЕНО: нужно для вызова core.import_image_from_path
from ..core import read, blender_bridge
from ..utils.image_cache import ImageCache
from ..core.signals import SIGNALS

class RZAssetListWidget(QtWidgets.QListWidget):
    """
    Handles asset list display with List/Grid toggle and external Drag & Drop support.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 1. Базовые настройки D&D (Это должно быть всегда)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDrop)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        
        # 2. Настраиваем режим по умолчанию (Плитка), но БЕЗ Static
        self.set_view_mode_grid()

    def set_view_mode_list(self):
        """Переключение в режим Списка"""
        self.setViewMode(QtWidgets.QListWidget.ListMode)
        self.setIconSize(QtCore.QSize(32, 32))
        self.setSpacing(2)
        self.setResizeMode(QtWidgets.QListWidget.Adjust)
        # В режиме списка Static работает нормально
        self.setMovement(QtWidgets.QListView.Static)

    def set_view_mode_grid(self):
        """Переключение в режим Плитки (Grid)"""
        self.setViewMode(QtWidgets.QListWidget.IconMode)
        self.setIconSize(QtCore.QSize(64, 64))
        self.setGridSize(QtCore.QSize(80, 100))
        self.setResizeMode(QtWidgets.QListWidget.Adjust)
        self.setSpacing(5)
        # ИСПРАВЛЕНИЕ: Используем Snap вместо Static. 
        # Это позволяет принимать Drops, но элементы будут "прилипать" к сетке.
        self.setMovement(QtWidgets.QListView.Snap)

    def contextMenuEvent(self, event):
        """Контекстное меню для переключения вида"""
        menu = QtWidgets.QMenu(self)
        
        # Создаем действия
        action_grid = menu.addAction("View: Grid (Tiles)")
        action_list = menu.addAction("View: List")
        
        # Ставим галочку напротив текущего режима
        if self.viewMode() == QtWidgets.QListWidget.IconMode:
            action_grid.setCheckable(True)
            action_grid.setChecked(True)
        else:
            action_list.setCheckable(True)
            action_list.setChecked(True)
            
        # Обработка выбора
        action = menu.exec(event.globalPos())
        if action == action_grid:
            self.set_view_mode_grid()
        elif action == action_list:
            self.set_view_mode_list()

    # --- DRAG & DROP LOGIC ---

    def mimeData(self, items):
        if not items: return None
        item = items[0]
        image_id = item.data(QtCore.Qt.UserRole)
        mime_data = QtCore.QMimeData()
        mime_data.setData("application/x-rzmenu-image-id", QtCore.QByteArray(str(image_id).encode('utf-8')))
        return mime_data

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item: return
        mime = self.mimeData([item])
        if not mime: return
        drag = QtGui.QDrag(self)
        drag.setMimeData(mime)
        pixmap = item.icon().pixmap(self.iconSize())
        if not pixmap.isNull():
            drag.setPixmap(pixmap)
            drag.setHotSpot(pixmap.rect().center())
        drag.exec(supportedActions)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasFormat("application/x-rzmenu-image-id"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasFormat("application/x-rzmenu-image-id"):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        # 1. Файлы из системы
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                if path:
                    core.import_image_from_path(path)
            event.acceptProposedAction()
            
        # 2. Внутреннее перетаскивание (игнорируем перемещение для порядка, но принимаем событие)
        elif event.mimeData().hasFormat("application/x-rzmenu-image-id"):
            event.ignore() # Игнорируем drop "сам в себя", чтобы не дублировать иконки
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