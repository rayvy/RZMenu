# RZMenu/qt_editor/widgets/asset_browser.py
import os
import shutil  # Нужно для копирования файлов
from PySide6 import QtCore, QtWidgets, QtGui
from .panel_base import RZEditorPanel
from .. import core
from ..core import read, blender_bridge, signals
from ..utils.image_cache import ImageCache
from ..core.signals import SIGNALS
import json

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

class RZAssetDetailsPanel(QtWidgets.QFrame):
    """Панель инспектора для выбранного ассета."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QtWidgets.QFrame.StyledPanel | QtWidgets.QFrame.Sunken)
        self.asset_data = None
        self.setup_ui()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Title/Header
        self.lbl_title = QtWidgets.QLabel("<b>Asset Details</b>")
        self.lbl_title.setStyleSheet("font-size: 14px; color: #55aaff;")
        layout.addWidget(self.lbl_title)

        # --- PREVIEW AREA ---
        self.preview_label = QtWidgets.QLabel()
        self.preview_label.setFixedSize(160, 160)
        self.preview_label.setAlignment(QtCore.Qt.AlignCenter)
        self.preview_label.setStyleSheet("border: 1px solid #444; background: #222;")
        layout.addWidget(self.preview_label, 0, QtCore.Qt.AlignCenter)
        
        # Timer for animation preview
        self.anim_timer = QtCore.QTimer()
        self.anim_timer.timeout.connect(self.update_anim_preview)
        self.curr_frame_idx = 0
        
        self.q_movie = None # For GIF support

        # Form Layout for properties
        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight)
        
        self.txt_name = QtWidgets.QLineEdit()
        self.txt_name.editingFinished.connect(self.on_prop_changed)
        form.addRow("Name:", self.txt_name)
        
        self.lbl_id = QtWidgets.QLabel("-")
        form.addRow("ID:", self.lbl_id)
        
        self.lbl_type = QtWidgets.QLabel("-")
        form.addRow("Type:", self.lbl_type)
        
        self.lbl_path = QtWidgets.QLabel("-")
        self.lbl_path.setWordWrap(True)
        self.lbl_path.setMaximumWidth(250)
        form.addRow("Source Path:", self.lbl_path)
        
        layout.addLayout(form)

        # --- ANIMATION GROUP ---
        self.anim_group = QtWidgets.QGroupBox("Animation Optimization")
        anim_vbox = QtWidgets.QVBoxLayout(self.anim_group)
        
        anim_form = QtWidgets.QFormLayout()
        
        self.combo_preset = QtWidgets.QComboBox()
        self.combo_preset.addItems(["ECONOMY", "ECONOMY_PLUS", "ADAPTIVE", "ADAPTIVE_PLUS", "EXTREME"])
        self.combo_preset.currentTextChanged.connect(self.on_prop_changed)
        anim_form.addRow("Quality Preset:", self.combo_preset)
        
        # Trim
        trim_h = QtWidgets.QHBoxLayout()
        self.spin_start = QtWidgets.QSpinBox()
        self.spin_start.setRange(0, 9999)
        self.spin_start.valueChanged.connect(self.on_prop_changed)
        self.spin_end = QtWidgets.QSpinBox()
        self.spin_end.setRange(0, 9999)
        self.spin_end.valueChanged.connect(self.on_prop_changed)
        trim_h.addWidget(QtWidgets.QLabel("Start:"))
        trim_h.addWidget(self.spin_start)
        trim_h.addWidget(QtWidgets.QLabel("End:"))
        trim_h.addWidget(self.spin_end)
        anim_form.addRow("Frame Range:", trim_h)

        self.lbl_stats = QtWidgets.QLabel("Frames: - | Duration: -")
        self.lbl_stats.setStyleSheet("color: #888;")
        anim_form.addRow("Current Stats:", self.lbl_stats)
        
        self.btn_view_json = QtWidgets.QPushButton("View UV JSON")
        self.btn_view_json.clicked.connect(self.on_view_json)
        anim_form.addRow("Debug:", self.btn_view_json)
        
        anim_vbox.addLayout(anim_form)
        layout.addWidget(self.anim_group)

        layout.addStretch()

        # --- BUTTONS ---
        btn_h = QtWidgets.QHBoxLayout()
        
        self.btn_build_atlas = QtWidgets.QPushButton("Build Atlas")
        self.btn_build_atlas.setToolTip("Process animation and pack into atlas to see results")
        self.btn_build_atlas.clicked.connect(self.on_build_atlas)
        self.btn_build_atlas.setStyleSheet("background-color: #2b5b2b;")
        btn_h.addWidget(self.btn_build_atlas)

        self.btn_delete = QtWidgets.QPushButton("Delete")
        self.btn_delete.clicked.connect(self.on_delete_clicked)
        self.btn_delete.setStyleSheet("background-color: #5b2b2b;")
        btn_h.addWidget(self.btn_delete)
        
        layout.addLayout(btn_h)

        self.is_updating = False

    def set_asset(self, data):
        self.is_updating = True
        self.asset_data = data
        self.anim_timer.stop()
        if self.q_movie: self.q_movie.stop()
        self.curr_frame_idx = 0
        
        self.txt_name.setText(data.get('name', ''))
        self.lbl_id.setText(str(data.get('id', 'N/A')))
        self.lbl_type.setText(data.get('source_type', 'TEMPLATE'))
        self.lbl_path.setText(data.get('path', ''))
        
        # Show initial preview
        path = data.get('path', '')
        if path.lower().endswith('.gif'):
            self.q_movie = QtGui.QMovie(path)
            self.preview_label.setMovie(self.q_movie)
            self.q_movie.setScaledSize(QtCore.QSize(150, 150))
            self.q_movie.start()
        elif data.get('id'):
            pix = ImageCache.instance().get_pixmap(data['id'])
            if pix:
                self.preview_label.setPixmap(pix.scaled(150, 150, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            else:
                self.preview_label.setText("No Preview")
        else:
            self.preview_label.setText("No Preview")

        is_anim = data.get('source_type') == 'ANIMATED'
        self.anim_group.setVisible(is_anim)
        self.btn_build_atlas.setVisible(is_anim)
        
        if is_anim:
            self.combo_preset.setCurrentText(data.get('anim_preset', 'ADAPTIVE'))
            self.spin_start.setValue(data.get('anim_start', 0))
            self.spin_end.setValue(data.get('anim_end', 0))
            
            unique = data.get('anim_frame_count', 0)
            total_dur = data.get('anim_total_dur', 0)
            self.lbl_stats.setText(f"Unique Frames: {unique} | Total: {total_dur:.2f}s")
            
            # Start preview timer if baked
            if unique > 0:
                self.anim_timer.start(100) # 10 FPS preview

        self.is_updating = False

    def update_anim_preview(self):
        """Циклический показ запеченных кадров (если они есть в блендере)."""
        if not self.asset_data: return
        
        unique = self.asset_data.get('anim_frame_count', 0)
        if unique <= 0: return
        
        self.curr_frame_idx = (self.curr_frame_idx + 1) % unique
        
        # Пытаемся достать кадр из кэша
        pix = ImageCache.instance().get_anim_frame(self.asset_data['name'], self.curr_frame_idx)
        if pix:
            self.preview_label.setPixmap(pix.scaled(150, 150, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        else:
            # Если хоть раз не удалось достать кадр (не запечен), останавливаем
            self.anim_timer.stop()

    def on_prop_changed(self, *args):
        if self.is_updating or not self.asset_data: return
        
        # Отправляем изменения в Blender
        asset_id = self.asset_data.get('id')
        if not asset_id and self.asset_data.get('type') == 'TEMPLATE':
            asset_id = self.asset_data.get('path')
        
        is_anim = self.asset_data.get('source_type') == 'ANIMATED'
        
        # Общий Name
        if self.txt_name.text() != self.asset_data.get('name'):
            blender_bridge.update_asset_property(asset_id, 'name', self.txt_name.text())
        
        if is_anim:
            blender_bridge.update_asset_property(asset_id, 'anim_preset', self.combo_preset.currentText())
            blender_bridge.update_asset_property(asset_id, 'anim_start', self.spin_start.value())
            blender_bridge.update_asset_property(asset_id, 'anim_end', self.spin_end.value())

    def on_build_atlas(self):
        """Вызывает пересборку атласа для предпросмотра эффекта Optimization."""
        if blender_bridge.trigger_atlas_update():
            # После обновления атласа, перечитываем данные (чтобы обновились Stats)
            self.on_prop_changed() # Force sync before reread
            SIGNALS.structure_changed.emit()

    def on_view_json(self):
        """Показывает JSON с координатами кадров."""
        if not self.asset_data: return
        
        # Мы не храним JSON в qt_dict для легкости, так что берем его из Blender
        import bpy
        img = next((i for i in bpy.context.scene.rzm.images if i.id == self.asset_data.get('id')), None)
        if img:
            QtWidgets.QMessageBox.information(self, "UV JSON", img.anim_frame_coords)

    def on_delete_clicked(self):
        msg = QtWidgets.QMessageBox.question(
            self, "Delete Asset", 
            f"Are you sure you want to delete '{self.txt_name.text()}'?\nThis will remove it from the library and cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if msg == QtWidgets.QMessageBox.Yes:
            asset_id = self.asset_data.get('id')
            asset_type = "IMAGE" if self.asset_data.get('source_type') else "TEMPLATE"
            if not asset_id and asset_type == "TEMPLATE":
                asset_id = self.asset_data.get('path')
                
            blender_bridge.delete_asset(asset_id, asset_type)
            self.setVisible(False)

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
        print(f"[AssetBrowser] dragEnter: hasUrls={event.mimeData().hasUrls()}, formats={event.mimeData().formats()}")
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
        print(f"[AssetBrowser] dropEvent started")
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
                print(f"[AssetBrowser] dropEvent: Processing '{filename}' (Ext: {ext})")
                
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
                elif ext in ['.png', '.jpg', '.jpeg', '.dds', '.tga', '.bmp', '.gif', '.mp4', '.webm', '.avi']:
                    print(f"[AssetBrowser] Calling core.import_image_from_path for {path}")
                    from .. import core
                    core.import_image_from_path(path)
                    files_processed = True
                else:
                    print(f"[AssetBrowser] Unsupported file type: {ext}")
            
            if files_processed:
                # Обновляем интерфейс (сигнал заставит панель перерисоваться)
                print("[AssetBrowser] Files processed, emitting structure_changed")
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

        # --- SPLITTER ---
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        
        # --- LIST WIDGET ---
        self.list_widget = RZAssetListWidget()
        self.list_widget.itemSelectionChanged.connect(self.on_selection_changed)
        self.splitter.addWidget(self.list_widget)
        
        # --- DETAILS PANEL ---
        self.details_panel = RZAssetDetailsPanel()
        self.details_panel.setVisible(False)
        self.splitter.addWidget(self.details_panel)
        
        layout.addWidget(self.splitter)

    def on_selection_changed(self):
        items = self.list_widget.selectedItems()
        if not items:
            self.details_panel.setVisible(False)
            return

        item = items[0]
        asset_id = item.data(QtCore.Qt.UserRole)
        asset_type = item.data(QtCore.Qt.UserRole + 1)
        
        # Ищем полные данные в результатах read.get_available_images()
        # Для простоты, мы можем заново запросить список или передать данные при наполнении
        all_imgs = read.get_available_images()
        asset_data = None
        
        if asset_type == "IMAGE":
            asset_data = next((img for img in all_imgs if img['id'] == asset_id), None)
        elif asset_type == "TEMPLATE":
            asset_data = {"type": "TEMPLATE", "path": asset_id, "name": item.text()}

        if asset_data:
            self.details_panel.set_asset(asset_data)
            self.details_panel.setVisible(True)
        else:
            self.details_panel.setVisible(False)

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