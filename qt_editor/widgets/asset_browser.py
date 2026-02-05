# RZMenu/qt_editor/widgets/asset_browser.py
import os
import shutil  # Нужно для копирования файлов
from PySide6 import QtCore, QtWidgets, QtGui
from .panel_base import RZEditorPanel
from .. import core
from ..core import read, blender_bridge
from ..utils.image_cache import ImageCache
from ..core.signals import SIGNALS

# --- ПОМОЩНИК ДЛЯ ПУТЕЙ ---
def get_base_templates_dir():
    """Возвращает путь к папке base_templates внутри аддона."""
    # Путь: qt_editor/widgets/asset_browser.py -> ... -> RZMenu/base_templates
    current_dir = os.path.dirname(os.path.abspath(__file__))
    addon_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir))) # Выходим из widgets -> qt_editor -> RZMenu
    # На всякий случай более надежный способ через __file__ если структура стандартная:
    # RZMenu/qt_editor/widgets/asset_browser.py -> 3 уровня вверх
    
    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "base_templates")
    
    if not os.path.exists(base_dir):
        try:
            os.makedirs(base_dir)
        except Exception as e:
            print(f"RZM Error: Could not create base_templates dir: {e}")
    return base_dir

class RZAssetListWidget(QtWidgets.QListWidget):
    """
    Handles asset list display with List/Grid toggle and external Drag & Drop support.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 1. Базовые настройки D&D
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDrop)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.set_view_mode_grid()

    def set_view_mode_list(self):
        """Переключение в режим Списка"""
        self.setViewMode(QtWidgets.QListWidget.ListMode)
        self.setIconSize(QtCore.QSize(32, 32))
        self.setSpacing(2)
        self.setResizeMode(QtWidgets.QListWidget.Adjust)
        self.setMovement(QtWidgets.QListView.Static)

    def set_view_mode_grid(self):
        """Переключение в режим Плитки (Grid)"""
        self.setViewMode(QtWidgets.QListWidget.IconMode)
        self.setIconSize(QtCore.QSize(64, 64))
        self.setGridSize(QtCore.QSize(80, 100))
        self.setResizeMode(QtWidgets.QListWidget.Adjust)
        self.setSpacing(5)
        # Используем Snap, чтобы работало перемещение и дроп
        self.setMovement(QtWidgets.QListView.Snap)

    def contextMenuEvent(self, event):
        """Контекстное меню для переключения вида"""
        menu = QtWidgets.QMenu(self)
        
        action_grid = menu.addAction("View: Grid (Tiles)")
        action_list = menu.addAction("View: List")
        
        if self.viewMode() == QtWidgets.QListWidget.IconMode:
            action_grid.setCheckable(True); action_grid.setChecked(True)
        else:
            action_list.setCheckable(True); action_list.setChecked(True)
            
        action = menu.exec(event.globalPos())
        if action == action_grid: self.set_view_mode_grid()
        elif action == action_list: self.set_view_mode_list()

    # --- DRAG & DROP LOGIC (Сисетма -> Браузер -> Вьюпорт) ---

    def mimeData(self, items):
        """Упаковка данных при перетаскивании ИЗ браузера ВО вьюпорт."""
        if not items: return None
        item = items[0]
        
        asset_type = item.data(QtCore.Qt.UserRole + 1) # "TEMPLATE" или "IMAGE"
        asset_data = item.data(QtCore.Qt.UserRole)     # Path или ID
        
        mime = QtCore.QMimeData()
        
        if asset_type == "TEMPLATE":
            # Передаем путь к файлу .rzmt
            mime.setData("application/x-rzmenu-template", QtCore.QByteArray(str(asset_data).encode('utf-8')))
        else:
            # Передаем ID картинки
            mime.setData("application/x-rzmenu-image-id", QtCore.QByteArray(str(asset_data).encode('utf-8')))
            
        return mime

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
        # Принимаем файлы из системы или внутренние типы
        if (event.mimeData().hasUrls() or 
            event.mimeData().hasFormat("application/x-rzmenu-image-id") or
            event.mimeData().hasFormat("application/x-rzmenu-template")):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if (event.mimeData().hasUrls() or 
            event.mimeData().hasFormat("application/x-rzmenu-image-id") or
            event.mimeData().hasFormat("application/x-rzmenu-template")):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        """
        Обработка падения объекта В Ассет Браузер.
        Цель: Сохранить (копировать) файл или импортировать картинку.
        """
        # 1. Файлы из системы (Внешний D&D)
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            files_processed = False
            
            base_templates_dir = get_base_templates_dir()
            
            for url in urls:
                path = url.toLocalFile()
                if not path: continue
                
                ext = os.path.splitext(path)[1].lower()
                filename = os.path.basename(path)
                
                # А) Если кинули ШАБЛОН -> Копируем в base_templates
                if ext == '.rzmt':
                    target_path = os.path.join(base_templates_dir, filename)
                    try:
                        shutil.copy2(path, target_path)
                        print(f"[AssetBrowser] Saved template to library: {filename}")
                        files_processed = True
                    except Exception as e:
                        print(f"[AssetBrowser] Failed to copy template: {e}")

                # Б) Если кинули КАРТИНКУ -> Импортируем в Blend (как раньше)
                elif ext in ['.png', '.jpg', '.jpeg', '.tga', '.bmp']:
                    core.import_image_from_path(path)
                    files_processed = True
            
            if files_processed:
                # Обновляем интерфейс (сигнал заставит панель перерисоваться)
                SIGNALS.structure_changed.emit()
                
            event.acceptProposedAction()
            
        # 2. Внутреннее перетаскивание (сортировка или игнор)
        # Мы игнорируем, чтобы не создавать копии, но можно разрешить перемещение
        elif (event.mimeData().hasFormat("application/x-rzmenu-image-id") or 
              event.mimeData().hasFormat("application/x-rzmenu-template")):
            event.ignore()
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

        # --- TOOLBAR ---
        toolbar = QtWidgets.QHBoxLayout()
        
        # 1. Кнопки действий
        self.btn_import = QtWidgets.QPushButton("Import")
        self.btn_import.clicked.connect(blender_bridge.import_asset_from_dialog)
        toolbar.addWidget(self.btn_import)
        
        self.btn_reload = QtWidgets.QPushButton("↺")
        self.btn_reload.setToolTip("Reload Base Icons & Templates")
        self.btn_reload.setFixedWidth(30)
        self.btn_reload.clicked.connect(self.on_reload_clicked)
        toolbar.addWidget(self.btn_reload)
        
        toolbar.addStretch()

        # 2. Фильтр (All / Images / Templates)
        toolbar.addWidget(QtWidgets.QLabel("Type:"))
        self.combo_filter = QtWidgets.QComboBox()
        self.combo_filter.addItems(["All", "Images", "Templates"])
        self.combo_filter.currentTextChanged.connect(self.rebuild_view)
        toolbar.addWidget(self.combo_filter)

        # 3. Сортировка
        toolbar.addWidget(QtWidgets.QLabel("Sort:"))
        self.combo_sort = QtWidgets.QComboBox()
        self.combo_sort.addItems(["ID (New-Old)", "ID (Old-New)", "A-Z", "Z-A"])
        self.combo_sort.currentTextChanged.connect(self.rebuild_view)
        toolbar.addWidget(self.combo_sort)
        
        layout.addLayout(toolbar)

        # --- LIST WIDGET ---
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
        # Auto-load check
        images = read.get_available_images()
        if not images:
            # Это может вызвать рекурсию если не аккуратно, но reload эмиттит сигнал
            # blender_bridge.reload_base_icons() 
            # Лучше просто обновить вью, так как reload уже мог пройти
            pass
        self.rebuild_view()

    def on_reload_clicked(self):
        """Ручная перезагрузка"""
        blender_bridge.reload_base_icons()
        self.rebuild_view()

    def rebuild_view(self, *args):
        """Главная функция построения списка"""
        self.list_widget.clear()
        
        filter_mode = self.combo_filter.currentText() # All, Images, Templates
        
        items_to_show = []

        # 1. СБОР ДАННЫХ
        # A. Images
        if filter_mode in ["All", "Images"]:
            all_images = read.get_available_images()
            # Фильтр по source_type (если нужно, можно добавить в комбобокс, но пока берем все)
            for img in all_images:
                items_to_show.append({
                    "type": "IMAGE",
                    "id": img['id'],
                    "name": img['name'],
                    "sort_key_id": img['id'],
                    "sort_key_name": img['name']
                })

        # B. Templates
        if filter_mode in ["All", "Templates"]:
            # Сканируем только base_templates как ты просил
            base_dir = get_base_templates_dir()
            if os.path.exists(base_dir):
                for f in os.listdir(base_dir):
                    if f.endswith(".rzmt"):
                        name = os.path.splitext(f)[0]
                        path = os.path.join(base_dir, f)
                        items_to_show.append({
                            "type": "TEMPLATE",
                            "id": 999999, # Фейковый ID для сортировки (чтобы были сверху или снизу)
                            "name": name,
                            "filepath": path,
                            "sort_key_id": 999999,
                            "sort_key_name": name
                        })

        # 2. СОРТИРОВКА
        sort_mode = self.combo_sort.currentText()
        
        if sort_mode == "ID (New-Old)":
            items_to_show.sort(key=lambda x: x['sort_key_id'], reverse=True)
        elif sort_mode == "ID (Old-New)":
            items_to_show.sort(key=lambda x: x['sort_key_id'])
        elif sort_mode == "A-Z":
            items_to_show.sort(key=lambda x: x['sort_key_name'].lower())
        elif sort_mode == "Z-A":
            items_to_show.sort(key=lambda x: x['sort_key_name'].lower(), reverse=True)

        # 3. ЗАПОЛНЕНИЕ ВИДЖЕТА
        cache = ImageCache.instance()
        file_icon = self.style().standardIcon(QtWidgets.QStyle.SP_FileIcon)

        for item_data in items_to_show:
            list_item = QtWidgets.QListWidgetItem(item_data['name'])
            
            if item_data['type'] == "IMAGE":
                list_item.setData(QtCore.Qt.UserRole, item_data['id'])
                list_item.setData(QtCore.Qt.UserRole + 1, "IMAGE")
                list_item.setToolTip(f"ID: {item_data['id']} (Image)")
                
                pix = cache.get_pixmap(item_data['id'])
                if pix: list_item.setIcon(QtGui.QIcon(pix))
                
            elif item_data['type'] == "TEMPLATE":
                list_item.setData(QtCore.Qt.UserRole, item_data['filepath'])
                list_item.setData(QtCore.Qt.UserRole + 1, "TEMPLATE")
                list_item.setToolTip(f"{item_data['filepath']} (Template)")
                list_item.setIcon(file_icon) # Можно потом заменить на кастомную иконку .rzmt
            
            self.list_widget.addItem(list_item)
            
        if not items_to_show:
            empty = QtWidgets.QListWidgetItem("No items found")
            empty.setFlags(QtCore.Qt.NoItemFlags)
            self.list_widget.addItem(empty)