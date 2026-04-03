# RZMenu/qt_editor/widgets/asset_browser.py
import os
import shutil  # Нужно для копирования файлов
from PySide6 import QtCore, QtWidgets, QtGui
from .panel_base import RZEditorPanel
from .. import core
from ..core import read, blender_bridge, signals
from ..utils.image_cache import ImageCache
from ..utils.icons import IconManager
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

class RZDensityTimeline(QtWidgets.QWidget):
    """Визуализация плотности уникальных кадров на таймлайне."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(12)
        self.sequence_data = [] # List of {'duration': float, 'is_unique': bool}
        self.total_duration = 0.0

    def set_data(self, sequence):
        self.sequence_data = sequence
        self.total_duration = sum(s.get('duration', 0) for s in sequence)
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Background
        rect = self.rect()
        painter.fillRect(rect, QtGui.QColor(40, 40, 40))
        
        if not self.sequence_data or self.total_duration <= 0:
            return

        # Draw markers
        curr_time = 0.0
        w = rect.width()
        
        # Draw unique blocks
        painter.setPen(QtCore.Qt.NoPen)
        for item in self.sequence_data:
            x = (curr_time / self.total_duration) * w
            block_w = (item.get('duration', 0.1) / self.total_duration) * w
            
            if item.get('is_unique'):
                # Синий маркер для начала нового уникального блока
                painter.setBrush(QtGui.QColor(80, 160, 255, 200)) # Яркий синий
                painter.drawRect(QtCore.QRectF(x, 0, max(2.5, block_w * 0.1), rect.height()))
            else:
                # Тусклый маркер для повторов (чтобы видеть 'ритм' видео)
                painter.setBrush(QtGui.QColor(100, 100, 100, 80)) # Серый прозрачный
                painter.drawRect(QtCore.QRectF(x, 0, 1, rect.height()))

            curr_time += item.get('duration', 0)

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
        self.preview_label.setStyleSheet("border: 1px solid #444; background: #000;")
        layout.addWidget(self.preview_label, 0, QtCore.Qt.AlignCenter)

        # --- PLAYBACK CONTROLS ---
        self.playback_container = QtWidgets.QWidget()
        self.playback_layout = QtWidgets.QHBoxLayout(self.playback_container)
        self.playback_layout.setContentsMargins(0, 0, 0, 0)
        self.playback_layout.setSpacing(4)
        
        self.btn_play = QtWidgets.QPushButton()
        self.btn_play.setIcon(IconManager.get_instance().get_icon("play"))
        self.btn_play.setFixedWidth(24)
        self.btn_play.setCheckable(True)
        self.btn_play.clicked.connect(self.on_play_clicked)
        self.playback_layout.addWidget(self.btn_play)
        
        self.slider_preview = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider_preview.setFixedHeight(12)
        self.slider_preview.sliderMoved.connect(self.on_slider_moved)
        self.playback_layout.addWidget(self.slider_preview)
        
        layout.addWidget(self.playback_container)
        
        # Timer for animation preview
        self.anim_timer = QtCore.QTimer()
        self.anim_timer.timeout.connect(self.update_anim_preview)
        self.curr_frame_idx = 0
        self.total_frames = 0
        
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
        
        # --- VECTOR SETTINGS (SVG) ---
        self.vector_group = QtWidgets.QGroupBox("Vector Settings (SVG)")
        vector_layout = QtWidgets.QFormLayout(self.vector_group)
        self.cb_preserve_color = QtWidgets.QCheckBox("Preserve Original Color")
        self.cb_preserve_color.stateChanged.connect(self.on_prop_changed)
        vector_layout.addRow(self.cb_preserve_color)
        
        layout.addWidget(self.vector_group)

        # --- ANIMATION OPTIMIZATION ---
        self.anim_group = QtWidgets.QGroupBox("Animation Optimization")
        anim_vbox = QtWidgets.QVBoxLayout(self.anim_group)
        
        anim_form = QtWidgets.QFormLayout()
        
        self.combo_preset = QtWidgets.QComboBox()
        self.combo_preset.addItems(["ECONOMY", "ADAPTIVE_LIGHT", "ADAPTIVE", "ADAPTIVE_HEAVY"])
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

        # Max Frames Limit
        self.spin_max_frames = QtWidgets.QSpinBox()
        self.spin_max_frames.setRange(1, 4096)
        self.spin_max_frames.setToolTip("Limits the number of frames read from the source file. Increase if your video is cut short.")
        self.spin_max_frames.valueChanged.connect(self.on_prop_changed)
        anim_form.addRow("Read Limit:", self.spin_max_frames)

        self.lbl_stats = QtWidgets.QLabel("Frames: - | Duration: -")
        self.lbl_stats.setStyleSheet("color: #888;")
        anim_form.addRow("Stats:", self.lbl_stats)
        
        # --- DENSITY TIMELINE ---
        self.timeline = RZDensityTimeline()
        anim_form.addRow("Density:", self.timeline)

        self.btn_view_json = QtWidgets.QPushButton("View UV JSON")
        self.btn_view_json.clicked.connect(self.on_view_json)
        anim_form.addRow("Debug:", self.btn_view_json)
        
        anim_vbox.addLayout(anim_form)
        layout.addWidget(self.anim_group)

        layout.addStretch()

        btn_h = QtWidgets.QHBoxLayout()
        
        self.btn_delete = QtWidgets.QPushButton()
        self.btn_delete.setIcon(IconManager.get_instance().get_icon("trash"))
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
            self.q_movie.frameChanged.connect(self.on_movie_frame_changed)
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

        static_exts = ('.png', '.jpg', '.jpeg', '.dds', '.tga', '.bmp')
        is_static_ext = path.lower().endswith(static_exts)
        is_vector = data.get('source_type') == 'VECTOR' or path.lower().endswith('.svg')
        is_anim = (data.get('source_type') == 'ANIMATED' or path.lower().endswith('.gif')) and not is_static_ext and not is_vector
        
        self.vector_group.setVisible(is_vector)
        self.anim_group.setVisible(is_anim)
        self.playback_container.setVisible(is_anim)
        self.playback_container.setEnabled(is_anim)
        
        if is_vector:
            import bpy
            rzm = bpy.context.scene.rzm
            img = next((i for i in rzm.images if i.id == data.get('id')), None)
            if img:
                self.cb_preserve_color.setChecked(img.svg_preserve_color)

        if is_anim:
            from ...core import animated_loader
            info = animated_loader.get_frame_info(path)
            self.total_frames = info['frame_count']
            self.slider_preview.setRange(0, max(0, self.total_frames - 1))
            self.slider_preview.setValue(0)
            
            # Set timer interval based on FPS
            interval = int(1000 / max(1, info['fps']))
            self.anim_timer.setInterval(interval)

            self.combo_preset.setCurrentText(data.get('anim_preset', 'ADAPTIVE'))
            self.spin_start.setValue(data.get('anim_start', 0))
            self.spin_end.setValue(data.get('anim_end', 0))
            self.spin_max_frames.setValue(data.get('anim_max_frames', 256))
            
            unique = data.get('anim_frame_count', 0)
            total_dur = data.get('anim_total_dur', 0)
            src_fps = info.get('fps', 24.0)
            self.lbl_stats.setText(f"Src: {src_fps:.1f} FPS | Unique: {unique} | Total: {total_dur:.2f}s")
            
            # --- UPDATE TIMELINE ---
            sequence = []
            if data.get('id'):
                import bpy
                img = next((i for i in bpy.context.scene.rzm.images if i.id == data['id']), None)
                if img:
                    for s in img.anim_sequence:
                        sequence.append({'duration': s.duration, 'is_unique': s.is_unique})
            self.timeline.set_data(sequence)

        self.is_updating = False

    def on_play_clicked(self, checked):
        icon_mgr = IconManager.get_instance()
        if checked:
            self.btn_play.setIcon(icon_mgr.get_icon("pause"))
            if self.q_movie: self.q_movie.setPaused(False)
            else: self.anim_timer.start()
        else:
            self.btn_play.setIcon(icon_mgr.get_icon("play"))
            if self.q_movie: self.q_movie.setPaused(True)
            else: self.anim_timer.stop()

    def on_movie_frame_changed(self, frame_no):
        """Called when QMovie (GIF) advance to a new frame."""
        if not self.is_updating:
            self.is_updating = True
            self.slider_preview.setValue(frame_no)
            self.is_updating = False

    def on_slider_moved(self, pos):
        # При скраббинге останавливаем авто-воспроизведение
        self.btn_play.setChecked(False)
        self.btn_play.setText("▶")
        self.anim_timer.stop()
        
        self.curr_frame_idx = pos
        self.show_frame(pos)

    def show_frame(self, idx):
        if not self.asset_data or not self.asset_data.get('path'):
            return
            
        from ...core import animated_loader
        import numpy as np
        
        pixels = animated_loader.get_frame_at(self.asset_data['path'], idx)
        if pixels is not None:
            # pixels: (H, W, 4) float32 [0..1]
            height, width = pixels.shape[:2]
            # Convert to uint8 RGBA
            uint8_pixels = (pixels * 255).astype(np.uint8)
            
            # QImage expects data as (bytes, width, height, format)
            qimg = QtGui.QImage(uint8_pixels.data, width, height, width * 4, QtGui.QImage.Format_RGBA8888)
            pix = QtGui.QPixmap.fromImage(qimg)
            self.preview_label.setPixmap(pix.scaled(150, 150, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            
            # Update slider without recursive trigger
            self.is_updating = True
            self.slider_preview.setValue(idx)
            self.is_updating = False

    def update_anim_preview(self):
        """Looping playback logic."""
        if self.total_frames <= 1:
            return
            
        self.curr_frame_idx = (self.curr_frame_idx + 1) % self.total_frames
        self.show_frame(self.curr_frame_idx)

    def on_prop_changed(self, *args):
        if self.is_updating or not self.asset_data: return
        
        asset_id = self.asset_data.get('id')
        if not asset_id: return
        
        is_vector = self.vector_group.isVisible()
        is_anim = self.anim_group.isVisible()
        
        # Общий Name
        if self.txt_name.text() != self.asset_data.get('name'):
            blender_bridge.update_asset_property(asset_id, 'name', self.txt_name.text())
            
        if is_vector:
            blender_bridge.update_asset_property(asset_id, 'svg_preserve_color', self.cb_preserve_color.isChecked())
        
        if is_anim:
            blender_bridge.update_asset_property(asset_id, 'anim_preset', self.combo_preset.currentText())
            blender_bridge.update_asset_property(asset_id, 'anim_start', self.spin_start.value())
            blender_bridge.update_asset_property(asset_id, 'anim_end', self.spin_end.value())
            blender_bridge.update_asset_property(asset_id, 'anim_speed', self.spin_speed.value())

    def on_build_atlas(self):
        """Вызывает пересборку атласа для предпросмотра эффекта Optimization."""
        if blender_bridge.trigger_atlas_update():
            # Заставляем основную панель обновиться, чтобы подтянуть новые статы
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
                elif ext in ['.png', '.jpg', '.jpeg', '.dds', '.tga', '.bmp', '.gif', '.mp4', '.webm', '.avi', '.svg']:
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

        # Selection state
        self._last_selected_id = None
        self._last_selected_type = None
        self._is_rebuilding = False

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

        self.btn_build_atlas = QtWidgets.QPushButton("Build Atlas")
        self.btn_build_atlas.setStyleSheet("background-color: #2b5b2b; color: white; font-weight: bold;")
        self.btn_build_atlas.clicked.connect(self.on_build_atlas)
        toolbar.addWidget(self.btn_build_atlas)
        
        toolbar.addStretch()

        # 2. Фильтр по Типу (All / Images / Templates)
        toolbar.addWidget(QtWidgets.QLabel("Ref:"))
        self.combo_filter = QtWidgets.QComboBox()
        self.combo_filter.addItems(["All", "Images", "Templates"])
        self.combo_filter.currentTextChanged.connect(self.rebuild_view)
        toolbar.addWidget(self.combo_filter)

        # 2b. Фильтр по Источнику
        toolbar.addWidget(QtWidgets.QLabel("Src:"))
        self.combo_source = QtWidgets.QComboBox()
        self.combo_source.addItems(["All", "Base", "Custom", "Captured", "Vector", "Anim"])
        self.combo_source.currentTextChanged.connect(self.rebuild_view)
        toolbar.addWidget(self.combo_source)

        # 2c. Фильтр по Расширению
        toolbar.addWidget(QtWidgets.QLabel("Ext:"))
        self.combo_ext = QtWidgets.QComboBox()
        self.combo_ext.addItems(["All", ".png", ".svg", ".mp4", ".gif", ".rzmt"])
        self.combo_ext.currentTextChanged.connect(self.rebuild_view)
        toolbar.addWidget(self.combo_ext)

        # 3. Сортировка
        toolbar.addWidget(QtWidgets.QLabel("Sort:"))
        self.combo_sort = QtWidgets.QComboBox()
        self.combo_sort.addItems(["ID (New-Old)", "ID (Old-New)", "A-Z", "Z-A", "Type"])
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

    def draw_type_badge(self, pixmap, ext):
        if not ext: return pixmap
        ext_clean = ext.upper().replace('.', '')
        if ext_clean in ['PNG', 'JPG', 'JPEG']: return pixmap  # Skip common
        
        # We need a copy to not modify cache
        pix = pixmap.copy()
        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        colors = {
            'SVG': '#EF7D00', # Orange
            'MP4': '#00A2E8', # Blue
            'GIF': '#D80073', # Pink
            'RZMT': '#60A917' # Green
        }
        col_str = colors.get(ext_clean, '#647687') # Default grey-blue
        
        font = QtGui.QFont("Arial", 7, QtGui.QFont.Bold)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        tw = metrics.horizontalAdvance(ext_clean)
        th = metrics.height()
        
        # Position: bottom right
        badge_rect = QtCore.QRect(pix.width() - tw - 6, pix.height() - th - 2, tw + 4, th)
        
        painter.setBrush(QtGui.QColor(col_str))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(badge_rect, 2, 2)
        
        painter.setPen(QtCore.Qt.white)
        painter.drawText(badge_rect, QtCore.Qt.AlignCenter, ext_clean)
        painter.end()
        return pix

    def draw_source_badge(self, pixmap, source_type):
        if not source_type or source_type == 'CUSTOM': return pixmap
        
        pix = pixmap.copy()
        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        colors = {
            'VECTOR': '#CC6600', # Darker Orange
            'BASE': '#007ACC',   # Darker Blue
            'CAPTURED': '#4B8B11', # Darker Green
            'ANIMATED': '#B0005E'  # Darker Pink
        }
        col_str = colors.get(source_type, '#647687')
        
        font = QtGui.QFont("Arial", 6, QtGui.QFont.Bold)
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        tw = metrics.horizontalAdvance(source_type)
        th = metrics.height()
        
        # Position: top right
        badge_rect = QtCore.QRect(pix.width() - tw - 6, 2, tw + 4, th)
        
        painter.setBrush(QtGui.QColor(col_str))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(badge_rect, 2, 2)
        
        painter.setPen(QtCore.Qt.white)
        painter.drawText(badge_rect, QtCore.Qt.AlignCenter, source_type)
        painter.end()
        return pix

    def on_selection_changed(self):
        if self._is_rebuilding: return
        
        items = self.list_widget.selectedItems()
        if not items:
            self._last_selected_id = None
            self._last_selected_type = None
            self.details_panel.setVisible(False)
            return

        item = items[0]
        asset_id = item.data(QtCore.Qt.UserRole)
        asset_type = item.data(QtCore.Qt.UserRole + 1)
        
        self._last_selected_id = asset_id
        self._last_selected_type = asset_type

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

    def on_build_atlas(self):
        """Вызывается из верхнего тулбара."""
        if blender_bridge.trigger_atlas_update():
            SIGNALS.structure_changed.emit()

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
        self._is_rebuilding = True
        
        # Save scroll pos
        v_scroll = self.list_widget.verticalScrollBar()
        old_scroll = v_scroll.value()

        self.list_widget.clear()
        
        filter_mode = self.combo_filter.currentText() # All, Images, Templates
        src_mode = self.combo_source.currentText().upper() # ALL, BASE, CUSTOM, CAPTURED, VECTOR, ANIM
        ext_filter = self.combo_ext.currentText().lower() # .png, .svg, etc.
        
        items_to_show = []

        # 1. СБОР ДАННЫХ
        # A. Images
        if filter_mode in ["All", "Images"]:
            all_images = read.get_available_images()
            for img in all_images:
                # Filter Source
                if src_mode != "ALL":
                    img_src = img['source_type']
                    if src_mode == "ANIM" and img_src != "ANIMATED": continue
                    elif src_mode != "ANIM" and img_src != src_mode: continue
                
                # Filter Extension
                path = img.get('path', '')
                ext = os.path.splitext(path)[1].lower() if path else ""
                if ext_filter != "all" and ext != ext_filter:
                    if not (ext_filter == ".png" and not ext): # Default to .png if no ext
                        continue

                items_to_show.append({
                    "type": "IMAGE",
                    "id": img['id'],
                    "name": img['name'],
                    "ext": ext,
                    "source_type": img['source_type'],
                    "sort_key_id": img['id'],
                    "sort_key_name": img['name']
                })

        # B. Templates
        if filter_mode in ["All", "Templates"]:
            if src_mode in ["ALL", "BASE", "CUSTOM"]: # Templates count as base icons folder usually
                # Filter Extension
                if ext_filter in ["all", ".rzmt"]:
                    base_dir = get_base_templates_dir()
                    if os.path.exists(base_dir):
                        for f in os.listdir(base_dir):
                            if f.endswith(".rzmt"):
                                name = os.path.splitext(f)[0]
                                path = os.path.join(base_dir, f)
                                items_to_show.append({
                                    "type": "TEMPLATE",
                                    "id": 999999,
                                    "name": name,
                                    "ext": ".rzmt",
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
        elif sort_mode == "Type":
            items_to_show.sort(key=lambda x: (x['type'], x['sort_key_name'].lower()))

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
                if pix:
                    pix = self.draw_type_badge(pix, item_data['ext'])
                    pix = self.draw_source_badge(pix, item_data.get('source_type', ''))
                    list_item.setIcon(QtGui.QIcon(pix))
                
            elif item_data['type'] == "TEMPLATE":
                list_item.setData(QtCore.Qt.UserRole, item_data['filepath'])
                list_item.setData(QtCore.Qt.UserRole + 1, "TEMPLATE")
                list_item.setToolTip(f"{item_data['filepath']} (Template)")
                list_item.setIcon(file_icon) # Можно потом заменить на кастомную иконку .rzmt
            
            self.list_widget.addItem(list_item)
            
            # Restore selection
            if self._last_selected_id is not None:
                is_match = False
                if item_data['type'] == self._last_selected_type:
                    if item_data['type'] == "IMAGE" and item_data['id'] == self._last_selected_id:
                        is_match = True
                    elif item_data['type'] == "TEMPLATE" and item_data['filepath'] == self._last_selected_id:
                        is_match = True
                
                if is_match:
                    list_item.setSelected(True)
                    self.list_widget.setCurrentItem(list_item)

        # Restore scroll
        QtCore.QTimer.singleShot(50, lambda: v_scroll.setValue(old_scroll))
            
        self._is_rebuilding = False

        if not items_to_show:
            empty = QtWidgets.QListWidgetItem("No items found")
            empty.setFlags(QtCore.Qt.NoItemFlags)
            self.list_widget.addItem(empty)