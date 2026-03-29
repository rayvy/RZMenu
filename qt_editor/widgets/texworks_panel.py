# RZMenu/qt_editor/widgets/texworks_panel.py
from PySide6 import QtWidgets, QtCore, QtGui
import bpy
from functools import partial

from .panel_base import RZEditorPanel
from .lib.widgets import RZPushButton, RZLabel, RZLineEdit, RZComboBox, RZSpinBox, RZDoubleSpinBox, RZCheckBox, RZGroupBox, RZScrollArea
from .lib.theme import get_current_theme
from ..core.signals import SIGNALS
from ..context import RZContextManager
import os
from ..lib import image_utils
from ..utils.icons import IconManager

# --- UTILS & CORE WIDGETS ---

class RZTabRow(QtWidgets.QWidget):
    """Horizontal selection bar for items (Blocks, Comps, Slots)."""
    clicked = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)
        self.buttons = []
        self.active_idx = -1

    def sync_items(self, names, active_idx):
        while self.layout.count():
            it = self.layout.takeAt(0)
            if it.widget():
                it.widget().hide()
                it.widget().setParent(None)
                it.widget().deleteLater()
        self.buttons.clear()
        
        t = get_current_theme()
        accent = t.get('accent', '#5298D4')
        
        for i, name in enumerate(names):
            name = name if name else f"Item {i}"
            btn = QtWidgets.QPushButton(name, self)
            btn.setCheckable(True)
            btn.setChecked(i == active_idx)
            btn.setMinimumHeight(24)
            
            # Styling
            is_active = (i == active_idx)
            style = f"""
                QPushButton {{ 
                    background: {accent if is_active else t.get('bg_header', '#2C313A')};
                    color: {'white' if is_active else t.get('text_dim', '#888')};
                    border: 1px solid {t.get('border', '#3E4451')};
                    border-radius: 4px;
                    padding: 0 8px;
                    font-weight: {'bold' if is_active else 'normal'};
                }}
                QPushButton:hover {{ background: {accent if is_active else t.get('border', '#3E4451')}; }}
            """
            btn.setStyleSheet(style)
            btn.clicked.connect(partial(self.clicked.emit, i))
            self.layout.addWidget(btn)
            self.buttons.append(btn)
        self.layout.addStretch()

class RZTexWorksAnchorBar(QtWidgets.QWidget):
    clicked = QtCore.Signal(str)
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.layout = QtWidgets.QHBoxLayout(self); self.layout.setContentsMargins(10, 0, 10, 0); self.layout.setSpacing(15)
        self.buttons = {}
        for label, tab_id in items:
            btn = QtWidgets.QPushButton(label); btn.setObjectName("AnchorButton"); btn.setFlat(True); btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, n=tab_id: self.clicked.emit(n)); self.layout.addWidget(btn); self.buttons[tab_id] = btn
        self.layout.addStretch()
        self.underline = QtWidgets.QWidget(self); self.underline.setFixedHeight(2); self.underline.hide()
        self._anim = QtCore.QPropertyAnimation(self.underline, b"geometry"); self._anim.setDuration(300); self._anim.setEasingCurve(QtCore.QEasingCurve.OutQuint)
        self.active_tab = None

    def set_active(self, tab_id):
        if self.active_tab == tab_id: return
        self.active_tab = tab_id
        btn = self.buttons.get(tab_id)
        if not btn: return
        self.underline.show()
        t = get_current_theme()
        self.underline.setStyleSheet(f"background-color: {t.get('accent', '#5298D4')}; border-radius: 1px;")
        rect = btn.geometry(); rect.setY(self.height() - 3); rect.setHeight(2)
        self._anim.stop(); self._anim.setEndValue(rect); self._anim.start()
        for name, b in self.buttons.items():
            is_active = (name == tab_id); col = t.get('text_bright', '#FFF') if is_active else t.get('text_dim', '#888')
            b.setStyleSheet(f"color: {col}; font-weight: {'bold' if is_active else 'normal'}; border: none; background: transparent;")

class ComboBoxFix(RZComboBox):
    """ComboBox with a sane maximum height."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.view().setMinimumWidth(150)
        self.view().setStyleSheet("QListView { max-height: 300px; }")

class AtlasPreviewWidget(QtWidgets.QWidget):
    def __init__(self, size=384, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size); self._size = size
        self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(0, 0, 0, 0)
        self.lbl = RZLabel(); self.lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl.setStyleSheet("background: #000; border: 1px solid #333; border-radius: 4px;")
        self.layout.addWidget(self.lbl)

    def update_block(self, block):
        if not block: return
        data = image_utils.collect_block_preview_data(block)
        image_utils.AsyncImageLoader.get_instance().load_atlas_async(data["layers"], data["res"], self._size, self.lbl.setPixmap)

    def update_with_layers(self, layers, res):
        image_utils.AsyncImageLoader.get_instance().load_atlas_async(layers, res, self._size, self.lbl.setPixmap)

class ResourcePreviewWidget(QtWidgets.QWidget):
    """Small thumbnail of a registered resource."""
    fileDropped = QtCore.Signal(str)

    def __init__(self, size=64, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.lbl = RZLabel()
        self.lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl.setStyleSheet("background: #333; border: 1px solid #444; border-radius: 4px;")
        self.layout.addWidget(self.lbl)
        self.setAcceptDrops(True)
        self._current_request_path = ""
        self._current_resource_name = ""
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self._current_resource_name:
            drag = QtGui.QDrag(self)
            mime = QtCore.QMimeData()
            mime.setText(self._current_resource_name)
            drag.setMimeData(mime)
            pix = self.lbl.pixmap()
            if pix:
                drag.setPixmap(pix.scaled(48, 48, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            drag.exec_(QtCore.Qt.CopyAction)
        
    def update_resource(self, resource_name):
        """Standard update via resource name (looks up in Blender)."""
        self.update_resource_by_name(resource_name)

    def update_resource_by_name(self, name):
        """Looks up resource path by name and triggers async load."""
        self._current_resource_name = name
        if not name:
            self.lbl.setPixmap(image_utils.get_placeholder_pixmap("EMPTY", self.width()))
            return
            
        rzm = bpy.context.scene.rzm
        res = next((r for r in rzm.tw_resources if r.name == name), None)
        
        if res and res.type == 'VIRTUAL':
            # Try to find a block that outputs to this resource
            block = next((b for b in rzm.tw_blocks if b.resource_name == name), None)
            if block:
                data = image_utils.collect_block_preview_data(block)
                pix = image_utils.get_total_block_preview(data["layers"], data["res"], size=self.width())
                self.lbl.setPixmap(pix)
                return
            else:
                pix = image_utils.get_placeholder_pixmap("VIRTUAL", self.width(), format_id=res.format)
                self.lbl.setPixmap(pix)
                return

        path = image_utils.get_resource_path(name)
        if path:
            self.update_from_path(path)
        else:
            self.lbl.setPixmap(image_utils.get_placeholder_pixmap("EMPTY", self.width()))

    def update_from_path(self, path):
        """Asynchronously updates preview from a raw path string."""
        if not path:
            self.lbl.setPixmap(image_utils.get_placeholder_pixmap("EMPTY", self.width()))
            return
            
        self._current_request_path = path
        # Check memory cache only. NO resolve_path here (it hits disk).
        # We use a placeholder and let the worker handle resolution.
        self.lbl.setPixmap(image_utils.get_placeholder_pixmap("LOADING", self.width()))
            
        image_utils.AsyncImageLoader.get_instance().load_async(
            path, self.width(), self._on_thumbnail_ready
        )

    def _on_thumbnail_ready(self, data):
        # Only update if this is still the path we want
        # Note: data might contain 'path' if we added it to ThumbnailWorker
        # For now, we trust the callback order or add a check
        if data.get("pixmap"):
            self.lbl.setPixmap(data["pixmap"])

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragEnterEvent(event)

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self.fileDropped.emit(path)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

class ResourcePathLineEdit(RZLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragEnterEvent(event)
        
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            mod_base = image_utils.get_mod_base_path()
            if mod_base and path.startswith(mod_base):
                rel_path = os.path.relpath(path, mod_base)
                if rel_path.startswith(f"Textures{os.sep}"):
                    rel_path = os.path.relpath(path, os.path.join(mod_base, "Textures"))
                path = rel_path.replace(os.sep, '/')
            self.setText(path)
            self.editingFinished.emit()
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

class RZResourceLineEdit(RZLineEdit):
    """LineEdit that supports drag-drop and autocomplete of resources."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setPlaceholderText("Resource Name or DragnDrop...")
        
        self.completer = QtWidgets.QCompleter(self)
        self.completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.completer.setFilterMode(QtCore.Qt.MatchContains)
        self.setCompleter(self.completer)
        self._update_completer()

    def _update_completer(self):
        # We need all resource names from rzm
        names = []
        try:
            rzm = bpy.context.scene.rzm
            names = [res.name for res in rzm.tw_resources]
        except: pass
        
        model = QtCore.QStringListModel(names)
        self.completer.setModel(model)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        txt = event.mimeData().text()
        # If it's a full path, let's see if it's already in registry or find its basename if possible
        # Actually, let's just use the basename of the file as an attempt if it's a path
        if os.path.isabs(txt):
            name = os.path.splitext(os.path.basename(txt))[0]
            # Check if this name exists in our resources
            rzm = bpy.context.scene.rzm
            res = next((r for r in rzm.tw_resources if r.name == name or r.path == txt), None)
            if res:
                self.setText(res.name)
            else:
                self.setText(name)
        else:
            self.setText(txt)
            
        self.editingFinished.emit()
        event.acceptProposedAction()

    def focusInEvent(self, event):
        self._update_completer()
        super().focusInEvent(event)

class TexturePreviewItem(QtWidgets.QWidget):
    def __init__(self, filepath, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.setFixedHeight(100)
        l = QtWidgets.QHBoxLayout(self); l.setContentsMargins(5, 5, 5, 5); l.setSpacing(10)
        
        self.lbl_preview = RZLabel()
        self.lbl_preview.setFixedSize(90, 90)
        self.lbl_preview.setStyleSheet("border: 1px solid #333; background: #000; border-radius: 4px;")
        l.addWidget(self.lbl_preview)
        
        inf_l = QtWidgets.QVBoxLayout(); l.addLayout(inf_l)
        name = os.path.basename(filepath)
        fmt = image_utils.get_dds_format(filepath)
        
        self.lbl_name = RZLabel(f"<b>{name}</b>"); self.lbl_name.setStyleSheet("font-size: 13px; color: white;")
        self.lbl_fmt = RZLabel(f"Format: {fmt} | Color: Unknown"); self.lbl_fmt.setStyleSheet("color: #888; font-size: 11px;")
        lbl_path = RZLabel(filepath); lbl_path.setStyleSheet("font-size: 10px; color: #555;")
        
        inf_l.addWidget(self.lbl_name); inf_l.addWidget(self.lbl_fmt); inf_l.addWidget(lbl_path); inf_l.addStretch()
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def set_preview_data(self, data):
        if data and data.get("pixmap"): 
            self.lbl_preview.setPixmap(data["pixmap"])
            self.lbl_preview.setAlignment(QtCore.Qt.AlignCenter)
        else:
            self.lbl_preview.setText("E")
        if data and data.get("colorspace"):
            current_fmt = self.lbl_fmt.text().split("|")[0].strip()
            self.lbl_fmt.setText(f"{current_fmt} | Color: {data['colorspace']}")

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.drag_start_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & QtCore.Qt.LeftButton): return
        if (event.position().toPoint() - self.drag_start_position).manhattanLength() < QtWidgets.QApplication.startDragDistance(): return
        
        drag = QtGui.QDrag(self)
        mime_data = QtCore.QMimeData()
        mime_data.setUrls([QtCore.QUrl.fromLocalFile(self.filepath)])
        drag.setMimeData(mime_data)
        
        pixmap = self.lbl_preview.pixmap()
        if pixmap: drag.setPixmap(pixmap.scaled(64, 64, QtCore.Qt.KeepAspectRatio))
        drag.exec_(QtCore.Qt.CopyAction)

class ScanWorker(QtCore.QThread):
    finished = QtCore.Signal(list)
    def __init__(self, path, subfolder, recursive=False):
        super().__init__()
        self.path = path; self.subfolder = subfolder; self.recursive = recursive
    def run(self):
        files = image_utils.scan_textures(self.path, self.subfolder, self.recursive)
        self.finished.emit(files)

# --- TABS: REGISTRY ---

class RZImageRegistryWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 5, 0, 0)
        self._current_cat_idx = 0
        
        tools = QtWidgets.QHBoxLayout()
        self.tabs = RZTabRow(); self.tabs.setFixedHeight(28)
        self.tabs.sync_items(["Textures", "TexWorks"], 0)
        self.tabs.clicked.connect(self._on_category_changed)
        tools.addWidget(self.tabs, 1)
        
        self.btn_refresh = RZPushButton("🔄 Refresh")
        self.btn_refresh.clicked.connect(self.refresh)
        tools.addWidget(self.btn_refresh)
        self.layout.addLayout(tools)
        
        self.scroll = RZScrollArea(); self.layout.addWidget(self.scroll, 1)
        self.container = QtWidgets.QWidget()
        self.c_layout = QtWidgets.QVBoxLayout(self.container)
        self.c_layout.setContentsMargins(0, 0, 0, 0); self.c_layout.setSpacing(2); self.c_layout.addStretch()
        
        self.scroll.setWidget(self.container); self.scroll.setWidgetResizable(True)
        self.pending_files = []; self._load_timer = QtCore.QTimer(); self._load_timer.timeout.connect(self._load_next_batch)
        
        # Initial scan
        QtCore.QTimer.singleShot(100, self.refresh)

    def _on_category_changed(self, idx):
        self._current_cat_idx = idx
        self.tabs.sync_items(["Textures", "TexWorks"], idx)
        self.refresh()

    def refresh(self):
        cat = ["Textures", "TexWorks"][getattr(self, "_current_cat_idx", 0)]
        self.start_scan(cat, True)

    def start_scan(self, subfolder, recursive):
        path = image_utils.get_mod_base_path()
        if not path: return
        self.btn_refresh.setEnabled(False)
        
        while self.c_layout.count() > 1:
            it = self.c_layout.takeAt(0); it.widget().deleteLater() if it.widget() else None
            
        self.worker = ScanWorker(path, subfolder, recursive)
        self.worker.finished.connect(self.on_scan_finished)
        self.worker.start()

    def on_scan_finished(self, files):
        self.btn_refresh.setEnabled(True)
        self.pending_files = files
        self._load_timer.start(30)

    def _load_next_batch(self):
        if not self.pending_files: self._load_timer.stop(); return
        
        for _ in range(6): # batch size
            if not self.pending_files: break
            f = self.pending_files.pop(0)
            item = TexturePreviewItem(f, self)
            self.c_layout.insertWidget(self.c_layout.count() - 1, item)
            
            image_utils.AsyncImageLoader.get_instance().load_async(f, 90, item.set_preview_data)

# --- TABS: RESOURCES ---

class TexWorksResourceItem(QtWidgets.QWidget):
    def __init__(self, index, data, parent_list):
        super().__init__()
        self.index = index; self.parent_list = parent_list
        self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(0, 2, 0, 4); self.layout.setSpacing(2)
        
        t = get_current_theme()
        self._show_details = False

        # Header Row
        row = QtWidgets.QHBoxLayout(); self.layout.addLayout(row)
        row.setSpacing(6)
        
        self.pre = ResourcePreviewWidget(42, self)
        self.pre.fileDropped.connect(self._on_file_dropped)
        row.addWidget(self.pre)
        
        im = IconManager.get_instance()
        self.btn_fav = RZPushButton(""); self.btn_fav.setFixedSize(24, 24); row.addWidget(self.btn_fav)
        self.btn_fav.setIcon(im.get_icon("star", QtWidgets.QStyle.StandardPixmap.SP_DialogYesButton))
        self.btn_fav.clicked.connect(self._toggle_fav)
        
        self.edit_name = RZLineEdit(); self.edit_name.setPlaceholderText("Name"); self.edit_name.setText(data.name); row.addWidget(self.edit_name, 1)
        self.edit_name.editingFinished.connect(self._on_changed)
        
        self.cb_type = ComboBoxFix(); self.cb_type.addItems(["EMPTY", "ON_DISK", "VIRTUAL"]); self.cb_type.setFixedWidth(85); row.addWidget(self.cb_type)
        self.cb_type.setCurrentText(data.type); self.cb_type.currentTextChanged.connect(self._on_changed)
        
        self.edit_tag = RZLineEdit(); self.edit_tag.setPlaceholderText("Tag"); self.edit_tag.setFixedWidth(70); row.addWidget(self.edit_tag)
        self.edit_tag.setText(data.qt_tag); self.edit_tag.editingFinished.connect(self._on_changed)

        # Action Buttons
        self.btn_del = RZPushButton(""); self.btn_del.setFixedSize(24, 24); row.addWidget(self.btn_del)
        self.btn_del.setIcon(im.get_icon("circle_x", QtWidgets.QStyle.StandardPixmap.SP_DialogCancelButton))
        self.btn_del.clicked.connect(lambda: self.parent_list.remove_item(self.index))

        # Details Area
        self.w_details = QtWidgets.QWidget(); self.l_details = QtWidgets.QFormLayout(self.w_details)
        self.l_details.setContentsMargins(30, 0, 10, 4); self.l_details.setSpacing(2); self.layout.addWidget(self.w_details)
        
        path_lay = QtWidgets.QHBoxLayout()
        self.edit_path = ResourcePathLineEdit()
        path_lay.addWidget(self.edit_path)
        self.l_details.addRow("Path:", path_lay)
        self.edit_path.editingFinished.connect(self._on_changed)
        self.edit_path.textChanged.connect(self._on_path_typing)
        
        self.sp_res = QtWidgets.QWidget(); lr = QtWidgets.QHBoxLayout(self.sp_res); lr.setContentsMargins(0,0,0,0)
        self.sp_x = RZSpinBox(); self.sp_y = RZSpinBox(); [s.setRange(1, 16384) for s in [self.sp_x, self.sp_y]]
        lr.addWidget(self.sp_x); lr.addWidget(RZLabel("x")); lr.addWidget(self.sp_y); self.l_details.addRow("Resolution:", self.sp_res)
        [s.valueChanged.connect(self._on_changed) for s in [self.sp_x, self.sp_y]]
        
        self.cb_fmt = ComboBoxFix(); self.cb_fmt.addItems(['DXGI_FORMAT_R8G8B8A8_UNORM_SRGB', 'DXGI_FORMAT_R8G8B8A8_UNORM', 'DXGI_FORMAT_BC7_UNORM'])
        self.cb_fmt.currentTextChanged.connect(self._on_changed); self.l_details.addRow("Format:", self.cb_fmt)

        self.update_data(data)

    def _toggle_fav(self):
        bpy.ops.rzm.update_tw_item(collection_name="resources", index=self.index, prop_name="qt_favorite", value_str=str(not self.btn_fav.property("active")))
        SIGNALS.structure_changed.emit()

    def _on_changed(self, *args):
        if self.parent_list._block: return
        props = {"name": self.edit_name.text(), "type": self.cb_type.currentText(), "path": self.edit_path.text(), "resolution[0]": str(self.sp_x.value()), "resolution[1]": str(self.sp_y.value()), "format": self.cb_fmt.currentText(), "qt_tag": self.edit_tag.text()}
        for k, v in props.items(): bpy.ops.rzm.update_tw_item(collection_name="resources", index=self.index, prop_name=k, value_str=v)

    def _on_path_typing(self):
        """Immediate preview update on typing (fixes lag)."""
        self.pre.update_from_path(self.edit_path.text())

    def _on_file_dropped(self, f):
        mod_base = image_utils.get_mod_base_path()
        path = f
        if mod_base and path.startswith(mod_base):
            rel_path = os.path.relpath(path, mod_base)
            if rel_path.startswith(f"Textures{os.sep}"):
                rel_path = os.path.relpath(path, os.path.join(mod_base, "Textures"))
            path = rel_path.replace(os.sep, '/')
        self.edit_path.setText(path)
        self._on_changed()

    def update_data(self, data):
        self.blockSignals(True)
        self.edit_name.setText(data.name)
        self.cb_type.setCurrentText(data.type)
        self.edit_path.setText(data.path)
        self.pre.update_resource(data.name)
        self.sp_x.setValue(data.resolution[0])
        self.sp_y.setValue(data.resolution[1])
        self.cb_fmt.setCurrentText(data.format)
        self.edit_tag.setText(data.qt_tag)
        self.blockSignals(False)
        
        # UI State
        self.btn_fav.setProperty("active", data.qt_favorite)
        self.btn_fav.setStyleSheet(f"color: {'#FFD700' if data.qt_favorite else '#888'};")
        
        self.edit_path.setVisible(data.type == 'ON_DISK')
        self.sp_res.setVisible(data.type == 'VIRTUAL')
        self.cb_fmt.setVisible(data.type == 'VIRTUAL')
        self.w_details.setVisible(self.parent_list.show_details and data.type != 'EMPTY')
        self.pre.setVisible(self.parent_list.show_previews)


class TexWorksResourcesTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self._block = False; self.show_details = False; self.show_previews = True
        self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(5, 5, 5, 5)
        
        # Tools row
        tools = QtWidgets.QHBoxLayout(); self.layout.addLayout(tools)
        btn_add = RZPushButton("+ Add Resource"); btn_add.clicked.connect(lambda: bpy.ops.rzm.add_tw_resource())
        tools.addWidget(btn_add)
        btn_clear = RZPushButton("Clear"); btn_clear.clicked.connect(lambda: bpy.ops.rzm.clear_tw_resources())
        tools.addWidget(btn_clear)
        self.chk_details = RZCheckBox("Show Details"); self.chk_details.toggled.connect(self._toggle_details); tools.addWidget(self.chk_details)
        self.chk_preview = RZCheckBox("Show Preview"); self.chk_preview.setChecked(True); self.chk_preview.toggled.connect(self._toggle_previews); tools.addWidget(self.chk_preview)
        
        self.scroll = RZScrollArea(); self.layout.addWidget(self.scroll)
        self.scroll_content = QtWidgets.QWidget(); self.scroll.setWidget(self.scroll_content); self.scroll.setWidgetResizable(True)
        self.list_layout = QtWidgets.QVBoxLayout(self.scroll_content); self.list_layout.setSpacing(4); self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.addStretch()

    def _toggle_details(self, val): self.show_details = val; self.update_ui()
    def _toggle_previews(self, val): self.show_previews = val; self.update_ui()
    
    def update_ui(self):
        self._block = True
        rzm = bpy.context.scene.rzm
        
        # Ensure we have a _widgets list
        if not hasattr(self, "_widgets"):
            self._widgets = []
            
        # 1. Ajust widget count
        count = len(rzm.tw_resources)
        while len(self._widgets) > count:
            w = self._widgets.pop()
            self.list_layout.removeWidget(w)
            w.hide(); w.setParent(None); w.deleteLater()
            
        while len(self._widgets) < count:
            new_idx = len(self._widgets)
            # Create placeholder data for now, will be updated below
            w = TexWorksResourceItem(new_idx, rzm.tw_resources[new_idx], self)
            self.list_layout.insertWidget(self.list_layout.count() - 1, w)
            self._widgets.append(w)
            
        # 2. Update existing widgets
        for i, res in enumerate(rzm.tw_resources):
            w = self._widgets[i]
            w.index = i
            w.update_data(res)
            
        self._block = False

    def remove_item(self, idx): bpy.ops.rzm.remove_tw_resource(index=idx); self.update_ui()

# --- TABS: OVERRIDES ---

class TexWorksOverrideItem(QtWidgets.QWidget):
    def __init__(self, index, data, parent_list):
        super().__init__()
        self.index = index; self.parent_list = parent_list
        row = QtWidgets.QHBoxLayout(self); row.setContentsMargins(5, 2, 5, 2); row.setSpacing(6)
        
        self.pre = ResourcePreviewWidget(42, self)
        row.addWidget(self.pre)
        
        im = IconManager.get_instance()
        self.btn_fav = RZPushButton("")
        self.btn_fav.setFixedSize(24, 24); row.addWidget(self.btn_fav)
        self.btn_fav.setIcon(im.get_icon("star", QtWidgets.QStyle.StandardPixmap.SP_DialogYesButton))
        self.btn_fav.clicked.connect(self._toggle_fav)
        
        self.edit_name = RZLineEdit(); self.edit_name.setPlaceholderText("Name"); self.edit_name.setText(data.name); row.addWidget(self.edit_name, 1)
        self.edit_name.editingFinished.connect(self._on_changed)
        
        self.edit_hash = RZLineEdit(); self.edit_hash.setPlaceholderText("Hash"); self.edit_hash.setText(data.hash); self.edit_hash.setFixedWidth(85); row.addWidget(self.edit_hash)
        self.edit_hash.editingFinished.connect(self._on_changed)
        
        self.edit_res = RZResourceLineEdit(); self.edit_res.setPlaceholderText("Resource Name"); self.edit_res.setText(data.resource_name); self.edit_res.setFixedWidth(120); row.addWidget(self.edit_res)
        self.edit_res.editingFinished.connect(self._on_changed)
        self.edit_res.textChanged.connect(self._on_res_typing)
        
        self.btn_del = RZPushButton(""); self.btn_del.setFixedSize(24, 24); row.addWidget(self.btn_del)
        self.btn_del.setIcon(im.get_icon("circle_x", QtWidgets.QStyle.StandardPixmap.SP_DialogCancelButton))
        self.btn_del.clicked.connect(lambda: self.parent_list.remove_item(self.index))
        
        self.update_data(data)

    def update_data(self, data):
        self.btn_fav.setProperty("active", data.qt_favorite)
        self.btn_fav.setStyleSheet(f"color: {'#FFD700' if data.qt_favorite else '#888'};")
        self.pre.setVisible(self.parent_list.show_previews)
        self.pre.update_resource_by_name(data.resource_name)

    def _on_res_typing(self):
        self.pre.update_resource_by_name(self.edit_res.text())

    def _toggle_fav(self):
        bpy.ops.rzm.update_tw_item(collection_name="overrides", index=self.index, prop_name="qt_favorite", value_str=str(not self.btn_fav.property("active")))
        SIGNALS.structure_changed.emit()

    def _on_changed(self):
        props = {"name": self.edit_name.text(), "hash": self.edit_hash.text(), "resource_name": self.edit_res.text()}
        for k, v in props.items(): bpy.ops.rzm.update_tw_item(collection_name="overrides", index=self.index, prop_name=k, value_str=v)

class TexWorksOverridesTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.show_previews = True
        self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(5, 5, 5, 5)
        tools = QtWidgets.QHBoxLayout(); self.layout.addLayout(tools)
        btn_add = RZPushButton("+ Add Override"); btn_add.clicked.connect(lambda: bpy.ops.rzm.add_tw_override())
        tools.addWidget(btn_add)
        btn_auto = RZPushButton("Auto-Import")
        btn_auto.clicked.connect(self._on_auto_import_clicked)
        tools.addWidget(btn_auto)

        self.chk_preview = RZCheckBox("Show Preview"); self.chk_preview.setChecked(True); self.chk_preview.toggled.connect(self._toggle_previews); tools.addWidget(self.chk_preview)
        
        self.scroll = RZScrollArea(); self.layout.addWidget(self.scroll)
        self.scroll_content = QtWidgets.QWidget(); self.scroll.setWidget(self.scroll_content); self.scroll.setWidgetResizable(True)
        self.list_layout = QtWidgets.QVBoxLayout(self.scroll_content); self.list_layout.setSpacing(4); self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.addStretch()

    def _toggle_previews(self, val): self.show_previews = val; self.update_ui()

    def _on_auto_import_clicked(self):
        # Use native Qt dialog to avoid switching to Blender window
        root = image_utils.get_mod_base_path()
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Dump Folder", root)
        if path:
            # We call the operator with the directory property explicitly
            # This triggers the new context-aware logic in operators/texworks_ops.py
            bpy.ops.rzm.tw_res_over_fill(directory=path)
            # Re-sync local UI
            self.update_ui()
            # Also notify other widgets
            SIGNALS.structure_changed.emit()


    def update_ui(self):
        rzm = bpy.context.scene.rzm
        if not hasattr(self, "_widgets"):
            self._widgets = []
            
        count = len(rzm.tw_overrides)
        while len(self._widgets) > count:
            w = self._widgets.pop()
            self.list_layout.removeWidget(w)
            w.hide(); w.setParent(None); w.deleteLater()
            
        while len(self._widgets) < count:
            new_idx = len(self._widgets)
            w = TexWorksOverrideItem(new_idx, rzm.tw_overrides[new_idx], self)
            self.list_layout.insertWidget(self.list_layout.count() - 1, w)
            self._widgets.append(w)
            
        for i, over in enumerate(rzm.tw_overrides):
            w = self._widgets[i]
            w.index = i
            w.update_data(over)

    def remove_item(self, idx): bpy.ops.rzm.remove_tw_override(index=idx); self.update_ui()

# --- TABS: MATERIALS ---

class TexWorksMaterialsTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self._block = False
        self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(0, 5, 0, 0)
        
        tools = QtWidgets.QHBoxLayout(); self.layout.addLayout(tools)
        btn_add = RZPushButton("+ Add MaterialSlot"); btn_add.clicked.connect(lambda: bpy.ops.rzm.add_tw_material())
        tools.addWidget(btn_add)

        self.scroll = RZScrollArea(); self.layout.addWidget(self.scroll)
        self.scroll_content = QtWidgets.QWidget(); self.scroll.setWidget(self.scroll_content); self.scroll.setWidgetResizable(True)
        self.list_layout = QtWidgets.QVBoxLayout(self.scroll_content); self.list_layout.setSpacing(2); self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.addStretch()

    def update_ui(self):
        self._block = True
        while self.list_layout.count() > 1: # Keep stretch
            it = self.list_layout.takeAt(0)
            if it.widget(): it.widget().deleteLater()
        
        rzm = bpy.context.scene.rzm
        for i, mat_item in enumerate(rzm.tw_materials):
            row = QtWidgets.QHBoxLayout(); w = QtWidgets.QWidget(); w.setLayout(row); w.setFixedHeight(28)
            row.setContentsMargins(5, 0, 5, 0)
            
            lbl = RZLabel(f"M{i}:"); row.addWidget(lbl)
            
            btn_mat = RZPushButton(mat_item.material.name if mat_item.material else "None")
            btn_mat.setCursor(QtCore.Qt.PointingHandCursor)
            btn_mat.setFixedHeight(24)
            btn_mat.clicked.connect(partial(self._select_material, i))
            row.addWidget(btn_mat, 1)
            
            btn_del = RZPushButton("✕"); btn_del.setFixedWidth(24); btn_del.setFixedHeight(24); row.addWidget(btn_del)
            btn_del.clicked.connect(partial(self._remove_material, i))
            
            self.list_layout.insertWidget(self.list_layout.count() - 1, w)
        self._block = False

    def _select_material(self, idx):
        bpy.ops.rzm.tw_select_material('INVOKE_DEFAULT', index=idx)

    def _remove_material(self, idx):
        bpy.ops.rzm.remove_tw_material(index=idx)
        # trigger_refresh handled by operator



# --- TABS: MAIN (SELECTION BASED) ---

class TexWorksDetailView(QtWidgets.QWidget):
    """Refined detail view for active item."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(5, 5, 5, 5); self.layout.setSpacing(8)
        self.layout.addStretch()
        t = get_current_theme()
        # Ensure it has a background to avoid "ghosting"
        self.setStyleSheet(f"background-color: {t.get('bg_dark', '#1E2127')};")

    def add_section(self, title, icon=None):
        box = RZGroupBox(title, self)
        box.setStyleSheet("QGroupBox { border: 1px solid #3E4451; border-radius: 4px; margin-top: 10px; padding-top: 10px; font-weight: bold; color: #BBB; } QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; }")
        l = QtWidgets.QVBoxLayout(box); l.setContentsMargins(8, 15, 8, 8); l.setSpacing(4)
        self.layout.insertWidget(self.layout.count() - 1, box)
        return l



class TexWorksMainTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Level 1: Blocks
        row_b = QtWidgets.QHBoxLayout(); row_b.setContentsMargins(5, 2, 5, 2); self.layout.addLayout(row_b)
        row_b.addWidget(RZLabel("Blocks:")); self.tab_blocks = RZTabRow(); self.tab_blocks.setFixedHeight(30); row_b.addWidget(self.tab_blocks, 1)
        btn_add_b = RZPushButton("+"); btn_add_b.setFixedWidth(24); btn_add_b.setFixedHeight(24); btn_add_b.clicked.connect(lambda: bpy.ops.rzm.add_tw_block()); row_b.addWidget(btn_add_b)
        
        # Level 2: Components (Visible only if block selected)
        self.w_comps = QtWidgets.QWidget(); self.w_comps.setFixedHeight(34)
        self.l_comps = QtWidgets.QHBoxLayout(self.w_comps); self.l_comps.setContentsMargins(5, 2, 5, 2)
        self.l_comps.addWidget(RZLabel("Comps:")); self.tab_comps = RZTabRow(); self.tab_comps.setFixedHeight(30); self.l_comps.addWidget(self.tab_comps, 1)
        btn_add_c = RZPushButton("+"); btn_add_c.setFixedWidth(24); btn_add_c.setFixedHeight(24); btn_add_c.clicked.connect(self._add_comp); self.l_comps.addWidget(btn_add_c)
        self.layout.addWidget(self.w_comps)

        # Level 3: Slots
        self.w_slots = QtWidgets.QWidget(); self.w_slots.setFixedHeight(34)
        self.l_slots = QtWidgets.QHBoxLayout(self.w_slots); self.l_slots.setContentsMargins(5, 2, 5, 2)
        self.l_slots.addWidget(RZLabel("Slots:")); self.tab_slots = RZTabRow(); self.tab_slots.setFixedHeight(30); self.l_slots.addWidget(self.tab_slots, 1)
        btn_add_s = RZPushButton("+"); btn_add_s.setFixedWidth(24); btn_add_s.setFixedHeight(24); btn_add_s.clicked.connect(self._add_slot); self.l_slots.addWidget(btn_add_s)
        self.layout.addWidget(self.w_slots)

        self.scroll = RZScrollArea(); self.layout.addWidget(self.scroll, 1)
        self.details = TexWorksDetailView(); self.scroll.setWidget(self.details); self.scroll.setWidgetResizable(True)
        
        # SIDE-BY-SIDE PREVIEWS at the bottom
        self.p_wrap = QtWidgets.QWidget(); self.layout.addWidget(self.p_wrap)
        self.p_layout = QtWidgets.QHBoxLayout(self.p_wrap); self.p_layout.setContentsMargins(5, 5, 5, 5); self.p_layout.setSpacing(10)
        
        self.blk_box = RZGroupBox("Atlas (Block Output)", self); l1 = QtWidgets.QVBoxLayout(self.blk_box)
        self.blk_pre = AtlasPreviewWidget(size=250, parent=self); l1.addWidget(self.blk_pre); self.p_layout.addWidget(self.blk_box)
        
        self.cmp_box = RZGroupBox("Selected Component Preview", self); l2 = QtWidgets.QVBoxLayout(self.cmp_box)
        self.cmp_pre = AtlasPreviewWidget(size=250, parent=self); l2.addWidget(self.cmp_pre); self.p_layout.addWidget(self.cmp_box)
        
        # Tab signals
        self.tab_blocks.clicked.connect(lambda i: self._set_active("block", i))
        self.tab_comps.clicked.connect(lambda i: self._set_active("comp", i))
        self.tab_slots.clicked.connect(lambda i: self._set_active("slot", i))

    def _set_active(self, type, idx):
        rzm = bpy.context.scene.rzm
        if type == "block": bpy.ops.rzm.set_active_block(index=idx)
        elif type == "comp": bpy.ops.rzm.set_active_component(block_index=rzm.active_tw_block_index, index=idx)
        elif type == "slot": bpy.ops.rzm.set_active_slot(block_index=rzm.active_tw_block_index, comp_index=rzm.tw_blocks[rzm.active_tw_block_index].active_component_index, index=idx)
        self.update_ui()

    def _add_comp(self): idx = bpy.context.scene.rzm.active_tw_block_index; bpy.ops.rzm.add_tw_component(block_index=idx); self.update_ui()
    def _add_slot(self): rzm = bpy.context.scene.rzm; b = rzm.active_tw_block_index; c = rzm.tw_blocks[b].active_component_index; bpy.ops.rzm.add_tw_slot(block_index=b, comp_index=c); self.update_ui()

    def update_ui(self):
        rzm = bpy.context.scene.rzm
        self.tab_blocks.sync_items([b.name for b in rzm.tw_blocks], rzm.active_tw_block_index)
        
        # Clean details (except stretch)
        while self.details.layout.count() > 1:
            it = self.details.layout.takeAt(0)
            if not it: continue
            
            w = it.widget()
            if w:
                w.hide(); w.setParent(None); w.deleteLater()
            
            lay = it.layout()
            if lay:
                while lay.count():
                    sit = lay.takeAt(0)
                    if sit and sit.widget():
                        sw = sit.widget()
                        sw.hide(); sw.setParent(None); sw.deleteLater()
                lay.deleteLater()
        
        b_idx = rzm.active_tw_block_index
        self.w_comps.setVisible(b_idx >= 0 and len(rzm.tw_blocks) > 0)
        if 0 <= b_idx < len(rzm.tw_blocks):
            block = rzm.tw_blocks[b_idx]
            self.tab_comps.sync_items([c.name for c in block.components], block.active_component_index)
            
            c_idx = block.active_component_index
            self.w_slots.setVisible(c_idx >= 0 and len(block.components) > 0)
            
            if 0 <= c_idx < len(block.components):
                comp = block.components[c_idx]
                self.tab_slots.sync_items([s.name for s in comp.slots], comp.active_slot_index)
                
                self._update_comp_preview(comp)
                
                s_idx = comp.active_slot_index
                if 0 <= s_idx < len(comp.slots):
                    self._draw_slot_details(comp.slots[s_idx], b_idx, c_idx, s_idx)
                else:
                    self._draw_comp_details(comp, b_idx, c_idx)
            else:
                self._draw_block_details(block, b_idx)
                self.cmp_pre.hide()
            
            self._update_block_preview(block)
        else:
            self.blk_pre.hide()
            self.cmp_pre.hide()

    def _update_block_preview(self, block):
        blk_data = image_utils.collect_block_preview_data(block)
        self.blk_pre.update_with_layers(blk_data["layers"], blk_data["res"])
        self.blk_pre.show()

    def _update_comp_preview(self, comp):
        # Build local layer list for just this component
        comp_path = image_utils.get_resource_path(comp.base_resource_name)
        layers = [{"rect": [0, 0, comp.rect[2], comp.rect[3]], "path": comp_path, "opacity": 0.8}]
        for slot in comp.slots:
            if not slot.active: continue
            slot_path = "" # TexWorksSlot has no resource_name
            layers.append({"rect": list(slot.rect), "path": slot_path, "is_decal": True, "opacity": 0.9, "parent_comp_rect": list(comp.rect)})
        
        cw, ch = comp.rect[2], comp.rect[3]
        if cw <= 0: cw = 1024
        if ch <= 0: ch = 1024
        
        local_layers = []
        for lyr in layers:
            rect = lyr["rect"]
            if lyr.get("is_decal"):
                ox, oy = comp.rect[0], comp.rect[1]
                local_rect = [rect[0]-ox, rect[1]-oy, rect[2], rect[3]]
                local_layers.append({"rect": local_rect, "path": lyr["path"], "is_decal": True, "opacity": 0.9})
            else:
                local_layers.append(lyr)

        self.cmp_pre.update_with_layers(local_layers, (cw, ch))
        # Find a place in details if we want it embedded, or just show it persistent
        # Actually, let's keep it embedded by adding it ONCE
        if not self.cmp_pre.parent():
             self.layout.insertWidget(self.layout.indexOf(self.scroll), self.cmp_pre)
        self.cmp_pre.show()

    def _draw_block_details(self, block, b_idx):
        # Already have block preview drawn globally in update_ui
        l = self.details.add_section("Block Settings")
        
        row = QtWidgets.QHBoxLayout(); l.addLayout(row)
        row.addWidget(RZLabel("Name:"))
        e_name = RZLineEdit(); e_name.setText(block.name); row.addWidget(e_name, 1)
        e_name.editingFinished.connect(lambda: self._item_changed("blocks", b_idx, "name", -1, -1, e_name.text()))
        
        row = QtWidgets.QHBoxLayout(); l.addLayout(row)
        row.addWidget(RZLabel("Output Atlas:"))
        e_res = RZResourceLineEdit(); e_res.setText(block.resource_name); row.addWidget(e_res, 1)
        e_res.editingFinished.connect(lambda: self._item_changed("blocks", b_idx, "resource_name", -1, -1, e_res.text()))

        l_sh = self.details.add_section("Shader Config")
        row = QtWidgets.QHBoxLayout(); l_sh.addLayout(row)
        cb_sh = ComboBoxFix(); cb_sh.addItems(["STANDARD", "SKIN", "CLOTH", "METAL"]); cb_sh.setCurrentText(block.shader_type)
        cb_sh.currentTextChanged.connect(lambda v: self._item_changed("blocks", b_idx, "shader_type", -1, -1, v))
        row.addWidget(RZLabel("Type:")); row.addWidget(cb_sh)

        l_back = self.details.add_section("Backdrop")
        chk_back = RZCheckBox("Enable Backdrop"); chk_back.setChecked(block.backdrop_enabled); l_back.addWidget(chk_back)
        chk_back.toggled.connect(lambda v: self._item_changed("blocks", b_idx, "backdrop_enabled", -1, -1, str(v)))
        
        if block.backdrop_enabled:
            row_b = QtWidgets.QHBoxLayout(); l_back.addLayout(row_b)
            row_b.addWidget(RZLabel("Resource:"))
            e_b_res = RZResourceLineEdit(); e_b_res.setText(block.backdrop_resource_name); row_b.addWidget(e_b_res, 1)
            e_b_res.editingFinished.connect(lambda: self._item_changed("blocks", b_idx, "backdrop_resource_name", -1, -1, e_b_res.text()))
            
            row_rect = QtWidgets.QHBoxLayout(); l_back.addLayout(row_rect)
            row_rect.addWidget(RZLabel("Rect:"))
            for i in range(4):
                sp = RZSpinBox(); sp.setRange(0, 16384); sp.setValue(block.backdrop_rect[i])
                sp.valueChanged.connect(partial(self._item_changed, "blocks", b_idx, f"backdrop_rect[{i}]", -1, -1))
                row_rect.addWidget(sp)
        
    def _draw_comp_details(self, comp, b_idx, c_idx):
        l = self.details.add_section("Component: " + comp.name)
        
        row = QtWidgets.QHBoxLayout(); l.addLayout(row)
        row.addWidget(RZLabel("Base Res:"))
        e_base = RZResourceLineEdit(); e_base.setText(comp.base_resource_name); row.addWidget(e_base, 1)
        e_base.editingFinished.connect(lambda: self._item_changed("components", c_idx, "base_resource_name", b_idx, -1, e_base.text()))
        
        # Atlas Rect
        row = QtWidgets.QHBoxLayout(); l.addLayout(row)
        row.addWidget(RZLabel("Atlas Rect:"))
        for i in range(4):
            sp = RZSpinBox(); sp.setRange(0, 16384); sp.setValue(comp.rect[i])
            sp.valueChanged.connect(partial(self._item_changed, "components", c_idx, f"rect[{i}]", b_idx, -1))
            row.addWidget(sp)
            
        # TexMorph
        row_m = QtWidgets.QHBoxLayout(); l.addLayout(row_m)
        chk_m = RZCheckBox("TexMorph"); chk_m.setChecked(comp.tex_morph_enabled); row_m.addWidget(chk_m)
        chk_m.toggled.connect(lambda v: self._item_changed("components", c_idx, "tex_morph_enabled", b_idx, -1, str(v)))
        if comp.tex_morph_enabled:
            e_m_res = RZResourceLineEdit(); e_m_res.setText(comp.tex_morph_resource_name); row_m.addWidget(e_m_res, 1)
            e_m_res.editingFinished.connect(lambda: self._item_changed("components", c_idx, "tex_morph_resource_name", b_idx, -1, e_m_res.text()))

        # Masking & HSV
        l_fx = self.details.add_section("Effects & Masking")
        row = QtWidgets.QHBoxLayout(); l_fx.addLayout(row)
        chk_mask = RZCheckBox("Mask"); chk_mask.setChecked(comp.mask_enabled); row.addWidget(chk_mask)
        chk_mask.toggled.connect(lambda v: self._item_changed("components", c_idx, "mask_enabled", b_idx, -1, str(v)))
        
        chk_hsv = RZCheckBox("HSV"); chk_hsv.setChecked(comp.hsv_enabled); row.addWidget(chk_hsv)
        chk_hsv.toggled.connect(lambda v: self._item_changed("components", c_idx, "hsv_enabled", b_idx, -1, str(v)))
        
        e_hsv_l = RZLineEdit(); e_hsv_l.setPlaceholderText("($) Link"); e_hsv_l.setText(comp.hsv_link); row.addWidget(e_hsv_l)
        e_hsv_l.editingFinished.connect(lambda: self._item_changed("components", c_idx, "hsv_link", b_idx, -1, e_hsv_l.text()))

        btn_mask = RZPushButton("Easy Mask"); btn_mask.clicked.connect(lambda: bpy.ops.rzm.tw_create_easy_mask(block_idx=b_idx, comp_idx=c_idx, slot_idx=-1))
        l_fx.addWidget(btn_mask)

    def _draw_slot_details(self, slot, b_idx, c_idx, s_idx):
        l = self.details.add_section("Slot: " + slot.name)
        
        chk_active = RZCheckBox("Active"); chk_active.setChecked(slot.active)
        chk_active.toggled.connect(lambda v: self._item_changed("slots", s_idx, "active", b_idx, c_idx, str(v)))
        l.addWidget(chk_active)

        # Pass 0 Row
        row_p0 = self.details.add_section("Transform Core (Pass 0)")
        row = QtWidgets.QHBoxLayout(); row_p0.addLayout(row)
        row.addWidget(RZLabel("Rect:"))
        for i in range(4):
            sp = RZSpinBox(); sp.setRange(0, 16384); sp.setValue(slot.rect[i])
            sp.valueChanged.connect(lambda v, i=i: self._item_changed("slots", s_idx, f"rect[{i}]", b_idx, c_idx, str(v)))
            row.addWidget(sp)
        
        row2 = QtWidgets.QHBoxLayout(); row_p0.addLayout(row2)
        sp_rot = RZSpinBox(); sp_rot.setRange(0, 360); sp_rot.setValue(slot.rotation); row2.addWidget(RZLabel("Rot:"))
        sp_rot.valueChanged.connect(lambda v: self._item_changed("slots", s_idx, "rotation", b_idx, c_idx, str(v)))
        row2.addWidget(sp_rot)
        chk_mir = RZCheckBox("M"); chk_mir.setChecked(slot.mirror); row2.addWidget(chk_mir)
        chk_mir.toggled.connect(lambda v: self._item_changed("slots", s_idx, "mirror", b_idx, c_idx, str(v)))
        chk_flp = RZCheckBox("F"); chk_flp.setChecked(slot.flip); row2.addWidget(chk_flp)
        chk_flp.toggled.connect(lambda v: self._item_changed("slots", s_idx, "flip", b_idx, c_idx, str(v)))

        # Multi-pass
        l_mp = self.details.add_section("Multi-Pass Settings")
        cb_mode = ComboBoxFix(); cb_mode.addItems(["NONE", "DECAL", "MASK_ONLY"]); cb_mode.setCurrentText(slot.multi_pass_mode)
        cb_mode.currentTextChanged.connect(lambda v: self._item_changed("slots", s_idx, "multi_pass_mode", b_idx, c_idx, v))
        l_mp.addWidget(cb_mode)
        
        if slot.multi_pass_mode != 'NONE':
            mp_row = QtWidgets.QHBoxLayout(); l_mp.addLayout(mp_row)
            mp_row.addWidget(RZLabel("Pass 1 Rect:"))
            for i in range(4):
                sp = RZSpinBox(); sp.setRange(0, 16384); sp.setValue(slot.multi_pass_rect[i])
                sp.valueChanged.connect(lambda v, i=i: self._item_changed("slots", s_idx, f"multi_pass_rect[{i}]", b_idx, c_idx, str(v)))
                mp_row.addWidget(sp)

        # Warping 3x3
        l_warp = self.details.add_section("Warping / Lattice (3x3)")
        chk_w0 = RZCheckBox("Pass 0 Warp"); chk_w0.setChecked(slot.warp_p0_enabled); l_warp.addWidget(chk_w0)
        chk_w0.toggled.connect(lambda v: self._item_changed("slots", s_idx, "warp_p0_enabled", b_idx, c_idx, str(v)))
        
        if slot.warp_p0_enabled:
            grid0 = QtWidgets.QGridLayout(); l_warp.addLayout(grid0)
            for i in range(9):
                row, col = divmod(i, 3)
                spx = RZDoubleSpinBox(); spx.setRange(-2.0, 2.0); spx.setValue(slot.warp_p0_grid[i*2]); spx.setFixedWidth(50)
                spy = RZDoubleSpinBox(); spy.setRange(-2.0, 2.0); spy.setValue(slot.warp_p0_grid[i*2+1]); spy.setFixedWidth(50)
                spx.valueChanged.connect(lambda v, i=i: self._item_changed("slots", s_idx, f"warp_p0_grid[{i*2}]", b_idx, c_idx, str(v)))
                spy.valueChanged.connect(lambda v, i=i: self._item_changed("slots", s_idx, f"warp_p0_grid[{i*2+1}]", b_idx, c_idx, str(v)))
                grid0.addWidget(spx, row, col*2); grid0.addWidget(spy, row, col*2+1)

        # UV Calculator
        l_calc = self.details.add_section("UV Calculator")
        row_c = QtWidgets.QHBoxLayout(); l_calc.addLayout(row_c)
        row_c.addWidget(RZLabel("Padding:")); sp_pad = RZSpinBox(); sp_pad.setValue(slot.calc_padding); row_c.addWidget(sp_pad)
        sp_pad.valueChanged.connect(lambda v: self._item_changed("slots", s_idx, "calc_padding", b_idx, c_idx, str(v)))
        
        btn_c0 = RZPushButton("Calc P0")
        btn_c0.clicked.connect(lambda: bpy.ops.rzm.calc_slot_config(block_index=b_idx, comp_index=c_idx, slot_index=s_idx, target_pass=0))
        btn_c1 = RZPushButton("Calc P1")
        btn_c1.clicked.connect(lambda: bpy.ops.rzm.calc_slot_config(block_index=b_idx, comp_index=c_idx, slot_index=s_idx, target_pass=1))
        l_calc.addWidget(btn_c0); l_calc.addWidget(btn_c1)

    def _item_changed(self, coll, idx, prop, b, c, val):
        bpy.ops.rzm.update_tw_item(collection_name=coll, index=idx, prop_name=prop, value_str=str(val), block_index=b, comp_index=c)


# --- MANAGER ---

class TexWorksManager(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(0, 0, 0, 0); self.layout.setSpacing(0)
        self.tabs_info = [("Main", "tab_main"), ("Resources", "tab_res"), ("Overrides", "tab_over"), ("Materials", "tab_mat"), ("Registry", "tab_reg")]
        self.anchor_bar = RZTexWorksAnchorBar(self.tabs_info); self.anchor_bar.clicked.connect(self._on_tab_clicked); self.layout.addWidget(self.anchor_bar)
        self.stack = QtWidgets.QStackedWidget(); self.layout.addWidget(self.stack)
        self.tab_widgets = {"tab_main": TexWorksMainTab(), "tab_res": TexWorksResourcesTab(), "tab_over": TexWorksOverridesTab(), "tab_mat": TexWorksMaterialsTab(), "tab_reg": RZImageRegistryWidget()}
        for tab_id in ["tab_main", "tab_res", "tab_over", "tab_mat", "tab_reg"]: self.stack.addWidget(self.tab_widgets[tab_id])
        self.anchor_bar.set_active("tab_main"); self.stack.setCurrentWidget(self.tab_widgets["tab_main"])
        
        # Debounce timer for updates
        self._refresh_timer = QtCore.QTimer(); self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._do_refresh)
        SIGNALS.structure_changed.connect(self.refresh_current)

    def _on_tab_clicked(self, tab_id): self.anchor_bar.set_active(tab_id); self.stack.setCurrentWidget(self.tab_widgets[tab_id]); self.refresh_current()
    
    def refresh_current(self):
        self._refresh_timer.start(100) # 100ms debounce
        
    def _do_refresh(self):
        w = self.stack.currentWidget()
        if hasattr(w, 'update_ui'): w.update_ui()
        
    def on_activate(self): self._do_refresh()

class RZMTexWorksPanel(RZEditorPanel):
    PANEL_ID = "TEXWORKS"; PANEL_NAME = "TexWorks"; PANEL_ICON = "image"
    def __init__(self, parent=None):
        super().__init__(parent); self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(0, 0, 0, 0); self.manager = TexWorksManager(); self.layout.addWidget(self.manager)
    def on_activate(self): self.manager.on_activate()
    def update_theme_styles(self): pass
    def enterEvent(self, event): RZContextManager.get_instance().update_input(self.cursor().pos(), (0,0), "TEXWORKS"); super().enterEvent(event)