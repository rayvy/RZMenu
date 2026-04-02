# RZMenu/qt_editor/widgets/texworks_panel.py
from PySide6 import QtWidgets, QtCore, QtGui
import bpy
from functools import partial

from .panel_base import RZEditorPanel
from .lib.widgets import RZPushButton, RZLabel, RZLineEdit, RZComboBox, RZSpinBox, RZDoubleSpinBox, RZCheckBox, RZGroupBox, RZScrollArea, RZColorButton
from .lib.theme import get_current_theme
from ..core.signals import SIGNALS
from ..context import RZContextManager
import os
from ..lib import image_utils
from ..utils.icons import IconManager
from ..core import blender_bridge

# --- UTILS & CORE WIDGETS ---
TEXWORKS_WIP = True # Toggler for experimental mesh-dependent features

class RZTabRow(QtWidgets.QScrollArea):
    """Horizontal selection bar for items (Blocks, Comps, Slots)."""
    clicked = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setMinimumHeight(30)
        
        self.container = QtWidgets.QWidget()
        self.setWidget(self.container)
        self.container_layout = QtWidgets.QHBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(4)
        self.buttons = []
        self.active_idx = -1

    def wheelEvent(self, event):
        if event.angleDelta().y() != 0:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - event.angleDelta().y())
        else:
            super().wheelEvent(event)

    def clear(self):
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item:
                w = item.widget()
                if w:
                    w.hide()
                    w.setParent(None)
                    w.deleteLater()
        self.buttons.clear()
        self.active_idx = -1

    def sync_items(self, names, active_idx):
        self.clear()
        
        t = get_current_theme()
        accent = t.get('accent', '#5298D4')
        
        for i, name in enumerate(names):
            name = name if name else f"Item {i}"
            btn = QtWidgets.QPushButton(name, self)
            btn.setCheckable(True)
            btn.setChecked(i == active_idx)
            btn.setMinimumHeight(26)
            
            # Styling
            is_active = (i == active_idx)
            style = f"""
                QPushButton {{ 
                    background: {accent if is_active else 'transparent'};
                    color: {'white' if is_active else t.get('text_dim', '#888')};
                    border: 1px solid {accent if is_active else t.get('border', '#3E4451')};
                    border-radius: 13px;
                    padding: 0 12px;
                    font-size: 11px;
                    font-weight: {'bold' if is_active else 'normal'};
                }}
                QPushButton:hover {{ 
                    background: {accent + '44' if not is_active else accent}; 
                    border: 1px solid {accent};
                }}
            """
            btn.setStyleSheet(style)
            btn.clicked.connect(lambda _, ix=i: self.clicked.emit(ix))
            self.container_layout.addWidget(btn)
            self.buttons.append(btn)
        self.container_layout.addStretch()

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
        self.setFixedSize(size, size)
        self._size = size
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.lbl = RZLabel(); self.lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl.setStyleSheet("background: #000; border: 1px solid #333; border-radius: 4px;")
        self.layout.addWidget(self.lbl)

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
        self.update_resource_by_name(resource_name)

    def update_resource_by_name(self, name):
        self._current_resource_name = name
        if not name:
            self.lbl.setPixmap(image_utils.get_placeholder_pixmap("EMPTY", self.width()))
            return
            
        rzm = bpy.context.scene.rzm
        res = next((r for r in rzm.tw_resources if r.name == name), None)
        
        if res and res.type == 'VIRTUAL':
            block = next((b for b in rzm.tw_blocks if b.resource_name == name), None)
            if block:
                data = image_utils.collect_block_preview_data(block)
                self.lbl.setPixmap(image_utils.get_placeholder_pixmap("LOADING", self.width()))
                image_utils.AsyncImageLoader.get_instance().load_atlas_async(data["layers"], data["res"], self.width(), self.lbl.setPixmap)
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
        if not path:
            self.lbl.setPixmap(image_utils.get_placeholder_pixmap("EMPTY", self.width()))
            return
        self._current_request_path = path
        self.lbl.setPixmap(image_utils.get_placeholder_pixmap("LOADING", self.width()))
        image_utils.AsyncImageLoader.get_instance().load_async(path, self.width(), self._on_thumbnail_ready)

    def _on_thumbnail_ready(self, data):
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
        else: super().dropEvent(event)

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
        else: super().dropEvent(event)

class RZResourceLineEdit(RZLineEdit):
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
        names = []
        try:
            rzm = bpy.context.scene.rzm
            names = [res.name for res in rzm.tw_resources]
        except: pass
        model = QtCore.QStringListModel(names)
        self.completer.setModel(model)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText(): event.acceptProposedAction()

    def dropEvent(self, event):
        txt = event.mimeData().text()
        if os.path.isabs(txt):
            name = os.path.splitext(os.path.basename(txt))[0]
            rzm = bpy.context.scene.rzm
            res = next((r for r in rzm.tw_resources if r.name == name or r.path == txt), None)
            if res: self.setText(res.name)
            else: self.setText(name)
        else: self.setText(txt)
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
        self.lbl_preview = RZLabel(); self.lbl_preview.setFixedSize(90, 90)
        self.lbl_preview.setStyleSheet("border: 1px solid #333; background: #000; border-radius: 4px;")
        l.addWidget(self.lbl_preview)
        inf_l = QtWidgets.QVBoxLayout(); l.addLayout(inf_l)
        name = os.path.basename(filepath); fmt = image_utils.get_dds_format(filepath)
        self.lbl_name = RZLabel(f"<b>{name}</b>"); self.lbl_name.setStyleSheet("font-size: 13px; color: white;")
        self.lbl_fmt = RZLabel(f"Format: {fmt} | Color: Unknown"); self.lbl_fmt.setStyleSheet("color: #888; font-size: 11px;")
        lbl_path = RZLabel(filepath); lbl_path.setStyleSheet("font-size: 10px; color: #555;")
        inf_l.addWidget(self.lbl_name); inf_l.addWidget(self.lbl_fmt); inf_l.addWidget(lbl_path); inf_l.addStretch()
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def set_preview_data(self, data):
        if data and data.get("pixmap"): 
            self.lbl_preview.setPixmap(data["pixmap"])
            self.lbl_preview.setAlignment(QtCore.Qt.AlignCenter)
        else: self.lbl_preview.setText("E")
        if data and data.get("colorspace"):
            current_fmt = self.lbl_fmt.text().split("|")[0].strip()
            self.lbl_fmt.setText(f"{current_fmt} | Color: {data['colorspace']}")

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton: self.drag_start_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & QtCore.Qt.LeftButton): return
        if (event.position().toPoint() - self.drag_start_position).manhattanLength() < QtWidgets.QApplication.startDragDistance(): return
        drag = QtGui.QDrag(self); mime_data = QtCore.QMimeData(); mime_data.setUrls([QtCore.QUrl.fromLocalFile(self.filepath)]); drag.setMimeData(mime_data)
        pixmap = self.lbl_preview.pixmap()
        if pixmap: drag.setPixmap(pixmap.scaled(64, 64, QtCore.Qt.KeepAspectRatio))
        drag.exec_(QtCore.Qt.CopyAction)

class ScanWorker(QtCore.QThread):
    finished = QtCore.Signal(list)
    def __init__(self, path, subfolder, recursive=False):
        super().__init__(); self.path = path; self.subfolder = subfolder; self.recursive = recursive
    def run(self):
        files = image_utils.scan_textures(self.path, self.subfolder, self.recursive)
        self.finished.emit(files)

class RZImageRegistryWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(0, 5, 0, 0); self._current_cat_idx = 0
        tools = QtWidgets.QHBoxLayout(); self.tabs = RZTabRow(); self.tabs.setFixedHeight(28); self.tabs.sync_items(["Textures", "TexWorks"], 0)
        self.tabs.clicked.connect(self._on_category_changed); tools.addWidget(self.tabs, 1)
        self.btn_refresh = RZPushButton("🔄 Refresh"); self.btn_refresh.clicked.connect(self.refresh); tools.addWidget(self.btn_refresh); self.layout.addLayout(tools)
        self.scroll = RZScrollArea(); self.layout.addWidget(self.scroll, 1); self.container = QtWidgets.QWidget(); self.c_layout = QtWidgets.QVBoxLayout(self.container)
        self.c_layout.setContentsMargins(0, 0, 0, 0); self.c_layout.setSpacing(2); self.c_layout.addStretch()
        self.scroll.setWidget(self.container); self.scroll.setWidgetResizable(True); self.pending_files = []; self._load_timer = QtCore.QTimer()
        self._load_timer.timeout.connect(self._load_next_batch); QtCore.QTimer.singleShot(100, self.refresh)

    def _on_category_changed(self, idx): self._current_cat_idx = idx; self.tabs.sync_items(["Textures", "TexWorks"], idx); self.refresh()
    def refresh(self): cat = ["Textures", "TexWorks"][getattr(self, "_current_cat_idx", 0)]; self.start_scan(cat, True)
    def start_scan(self, subfolder, recursive):
        path = image_utils.get_mod_base_path()
        if not path: return
        self.btn_refresh.setEnabled(False)
        while self.c_layout.count() > 1: it = self.c_layout.takeAt(0); it.widget().deleteLater() if it.widget() else None
        self.worker = ScanWorker(path, subfolder, recursive); self.worker.finished.connect(self.on_scan_finished); self.worker.start()

    def on_scan_finished(self, files): self.btn_refresh.setEnabled(True); self.pending_files = files; self._load_timer.start(30)

    def _load_next_batch(self):
        if not self.pending_files: self._load_timer.stop(); return
        for _ in range(6): 
            if not self.pending_files: break
            f = self.pending_files.pop(0); item = TexturePreviewItem(f, self); self.c_layout.insertWidget(self.c_layout.count() - 1, item)
            image_utils.AsyncImageLoader.get_instance().load_async(f, 90, item.set_preview_data)

class TexWorksResourceItem(QtWidgets.QWidget):
    def __init__(self, index, data, parent_list):
        super().__init__()
        self.index = index
        self.parent_list = parent_list
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 2, 0, 4)
        self.layout.setSpacing(2)
        row = QtWidgets.QHBoxLayout()
        self.layout.addLayout(row)
        row.setSpacing(6)
        self.pre = ResourcePreviewWidget(42, self)
        self.pre.fileDropped.connect(self._on_file_dropped)
        row.addWidget(self.pre)
        im = IconManager.get_instance()
        self.btn_fav = RZPushButton("")
        self.btn_fav.setFixedSize(24, 24)
        self.btn_fav.setToolTip("Toggle Favorite")
        row.addWidget(self.btn_fav)
        self.btn_fav.setIcon(im.get_icon("star", QtWidgets.QStyle.StandardPixmap.SP_DialogYesButton))
        self.btn_fav.clicked.connect(self._toggle_fav)
        self.edit_name = RZLineEdit()
        self.edit_name.setPlaceholderText("Name")
        self.edit_name.setText(data.name)
        row.addWidget(self.edit_name, 1)
        self.edit_name.editingFinished.connect(self._on_changed)
        self.cb_type = ComboBoxFix()
        self.cb_type.addItems(["EMPTY", "ON_DISK", "VIRTUAL"])
        self.cb_type.setFixedWidth(85)
        row.addWidget(self.cb_type)
        self.cb_type.setCurrentText(data.type)
        self.cb_type.currentTextChanged.connect(self._on_changed)
        self.edit_tag = RZLineEdit()
        self.edit_tag.setPlaceholderText("Tag")
        self.edit_tag.setFixedWidth(70)
        row.addWidget(self.edit_tag)
        self.edit_tag.setText(data.qt_tag)
        self.edit_tag.editingFinished.connect(self._on_changed)
        self.btn_del = RZPushButton("")
        self.btn_del.setFixedSize(24, 24)
        self.btn_del.setToolTip("Remove Resource")
        row.addWidget(self.btn_del)
        self.btn_del.setIcon(im.get_icon("circle_x", QtWidgets.QStyle.StandardPixmap.SP_DialogCancelButton))
        self.btn_del.clicked.connect(lambda: self.parent_list.remove_item(self.index))
        self.w_details = QtWidgets.QWidget()
        self.l_details = QtWidgets.QFormLayout(self.w_details)
        self.l_details.setContentsMargins(30, 0, 10, 4)
        self.l_details.setSpacing(2)
        self.layout.addWidget(self.w_details)
        path_lay = QtWidgets.QHBoxLayout()
        self.edit_path = ResourcePathLineEdit()
        path_lay.addWidget(self.edit_path)
        self.l_details.addRow("Path:", path_lay)
        self.edit_path.editingFinished.connect(self._on_changed)
        self.edit_path.textChanged.connect(self._on_path_typing)
        self.sp_res = QtWidgets.QWidget()
        lr = QtWidgets.QHBoxLayout(self.sp_res)
        lr.setContentsMargins(0,0,0,0)
        self.sp_x = RZSpinBox()
        self.sp_y = RZSpinBox()
        for s in [self.sp_x, self.sp_y]:
            s.setRange(1, 16384)
        lr.addWidget(self.sp_x)
        lr.addWidget(RZLabel("x"))
        lr.addWidget(self.sp_y)
        self.l_details.addRow("Resolution:", self.sp_res)
        for s in [self.sp_x, self.sp_y]:
            s.editingFinished.connect(self._on_changed)
        self.cb_fmt = ComboBoxFix()
        self.cb_fmt.addItems(['DXGI_FORMAT_R8G8B8A8_UNORM_SRGB', 'DXGI_FORMAT_R8G8B8A8_UNORM', 'DXGI_FORMAT_BC7_UNORM'])
        self.cb_fmt.currentTextChanged.connect(self._on_changed)
        self.l_details.addRow("Format:", self.cb_fmt)
        self.update_data(data)

    def _toggle_fav(self):
        bpy.ops.rzm.update_tw_item(collection_name="resources", index=self.index, prop_name="qt_favorite", value_str=str(not self.btn_fav.property("active")))
        SIGNALS.structure_changed.emit()
    def _on_changed(self, *args):
        if self.parent_list._block:
            return
        props = {"name": self.edit_name.text(), "type": self.cb_type.currentText(), "path": self.edit_path.text(), "resolution[0]": str(self.sp_x.value()), "resolution[1]": str(self.sp_y.value()), "format": self.cb_fmt.currentText(), "qt_tag": self.edit_tag.text()}
        for k, v in props.items():
            bpy.ops.rzm.update_tw_item(collection_name="resources", index=self.index, prop_name=k, value_str=v)
    def _on_path_typing(self):
        self.pre.update_from_path(self.edit_path.text())
    def _on_file_dropped(self, f):
        mod_base = image_utils.get_mod_base_path(); path = f
        if mod_base and path.startswith(mod_base):
            rel_path = os.path.relpath(path, mod_base)
            if rel_path.startswith(f"Textures{os.sep}"): rel_path = os.path.relpath(path, os.path.join(mod_base, "Textures"))
            path = rel_path.replace(os.sep, '/')
        self.edit_path.setText(path); self._on_changed()

    def update_data(self, data):
        self.blockSignals(True)
        self.edit_name.set_text_silent(data.name)
        if self.cb_type.currentText() != data.type: self.cb_type.setCurrentText(data.type)
        self.edit_path.set_text_silent(data.path)
        self.pre.update_resource(data.name)
        self.sp_x.setValue(data.resolution[0])
        self.sp_y.setValue(data.resolution[1])
        if self.cb_fmt.currentText() != data.format: self.cb_fmt.setCurrentText(data.format)
        self.edit_tag.set_text_silent(data.qt_tag)
        self.blockSignals(False)
        self.btn_fav.setProperty("active", data.qt_favorite)
        self.btn_fav.setStyleSheet(f"color: {'#FFD700' if data.qt_favorite else '#888'};")
        self.edit_path.setVisible(data.type == 'ON_DISK')
        self.sp_res.setVisible(data.type == 'VIRTUAL')
        self.cb_fmt.setVisible(data.type == 'VIRTUAL')
        self.w_details.setVisible(self.parent_list.show_details and data.type != 'EMPTY')
        self.pre.setVisible(self.parent_list.show_previews)

class TexWorksResourcesTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._block = False
        self.show_details = False
        self.show_previews = True
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        tools = QtWidgets.QHBoxLayout()
        self.layout.addLayout(tools)
        btn_add = RZPushButton("+ Add Resource")
        btn_add.clicked.connect(lambda: bpy.ops.rzm.add_tw_resource())
        tools.addWidget(btn_add)
        btn_clear = RZPushButton("Clear")
        btn_clear.clicked.connect(lambda: bpy.ops.rzm.clear_tw_resources())
        tools.addWidget(btn_clear)
        self.chk_details = RZCheckBox("Show Details")
        self.chk_details.toggled.connect(self._toggle_details)
        tools.addWidget(self.chk_details)
        self.chk_preview = RZCheckBox("Show Preview")
        self.chk_preview.setChecked(True)
        self.chk_preview.toggled.connect(self._toggle_previews)
        tools.addWidget(self.chk_preview)
        self.scroll = RZScrollArea()
        self.layout.addWidget(self.scroll)
        self.scroll_content = QtWidgets.QWidget()
        self.scroll.setWidget(self.scroll_content)
        self.scroll.setWidgetResizable(True)
        self.list_layout = QtWidgets.QVBoxLayout(self.scroll_content)
        self.list_layout.setSpacing(4)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.addStretch()

    def _toggle_details(self, val):
        self.show_details = val
        self.update_ui()
    def _toggle_previews(self, val):
        self.show_previews = val
        self.update_ui()
    def update_ui(self):
        self._block = True; rzm = bpy.context.scene.rzm
        if not hasattr(self, "_widgets"): self._widgets = []
        count = len(rzm.tw_resources)
        while len(self._widgets) > count: w = self._widgets.pop(); self.list_layout.removeWidget(w); w.hide(); w.setParent(None); w.deleteLater()
        while len(self._widgets) < count:
            new_idx = len(self._widgets); w = TexWorksResourceItem(new_idx, rzm.tw_resources[new_idx], self)
            self.list_layout.insertWidget(self.list_layout.count() - 1, w); self._widgets.append(w)
        for i, res in enumerate(rzm.tw_resources): w = self._widgets[i]; w.index = i; w.update_data(res)
        self._block = False
    def remove_item(self, idx): bpy.ops.rzm.remove_tw_resource(index=idx); self.update_ui()

# --- TABS: OVERRIDES ---
class TexWorksOverrideItem(QtWidgets.QWidget):
    def __init__(self, index, data, parent_list):
        super().__init__(); self.index = index; self.parent_list = parent_list
        row = QtWidgets.QHBoxLayout(self); row.setContentsMargins(5, 2, 5, 2); row.setSpacing(6)
        self.pre = ResourcePreviewWidget(42, self); row.addWidget(self.pre); im = IconManager.get_instance();        self.btn_fav = RZPushButton("")
        self.btn_fav.setFixedSize(24, 24)
        self.btn_fav.setToolTip("Toggle Favorite")
        row.addWidget(self.btn_fav)
        self.btn_fav.setIcon(im.get_icon("star", QtWidgets.QStyle.StandardPixmap.SP_DialogYesButton))
        self.btn_fav.clicked.connect(self._toggle_fav)
        self.edit_name = RZLineEdit(); self.edit_name.setPlaceholderText("Name"); self.edit_name.setText(data.name); row.addWidget(self.edit_name, 1); self.edit_name.editingFinished.connect(self._on_changed)
        self.edit_hash = RZLineEdit(); self.edit_hash.setPlaceholderText("Hash"); self.edit_hash.setText(data.hash); self.edit_hash.setFixedWidth(85); row.addWidget(self.edit_hash); self.edit_hash.editingFinished.connect(self._on_changed)
        self.edit_res = RZResourceLineEdit(); self.edit_res.setPlaceholderText("Resource Name"); self.edit_res.setText(data.resource_name); self.edit_res.setFixedWidth(120); row.addWidget(self.edit_res)
        self.btn_del = RZPushButton("")
        self.btn_del.setFixedSize(24, 24)
        self.btn_del.setToolTip("Remove Override")
        row.addWidget(self.btn_del)
        self.btn_del.setIcon(im.get_icon("circle_x", QtWidgets.QStyle.StandardPixmap.SP_DialogCancelButton))
        self.btn_del.clicked.connect(lambda: self.parent_list.remove_item(self.index))
        self.update_data(data)

    def update_data(self, data): 
        self.btn_fav.setProperty("active", data.qt_favorite)
        self.btn_fav.setStyleSheet(f"color: {'#FFD700' if data.qt_favorite else '#888'};")
        self.pre.setVisible(self.parent_list.show_previews)
        self.pre.update_resource_by_name(data.resource_name)
        # Sync text fields silently
        self.edit_name.set_text_silent(data.name)
        self.edit_hash.set_text_silent(data.hash)
        self.edit_res.set_text_silent(data.resource_name)
    def _on_res_typing(self): self.pre.update_resource_by_name(self.edit_res.text())
    def _toggle_fav(self): bpy.ops.rzm.update_tw_item(collection_name="overrides", index=self.index, prop_name="qt_favorite", value_str=str(not self.btn_fav.property("active"))); SIGNALS.structure_changed.emit()
    def _on_changed(self):
        props = {"name": self.edit_name.text(), "hash": self.edit_hash.text(), "resource_name": self.edit_res.text()}
        for k, v in props.items(): bpy.ops.rzm.update_tw_item(collection_name="overrides", index=self.index, prop_name=k, value_str=v)

class TexWorksOverridesTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.show_previews = True; self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(5, 5, 5, 5); tools = QtWidgets.QHBoxLayout(); self.layout.addLayout(tools)
        btn_add = RZPushButton("+ Add Override"); btn_add.clicked.connect(lambda: bpy.ops.rzm.add_tw_override()); tools.addWidget(btn_add)
        btn_auto = RZPushButton("Auto-Import"); btn_auto.clicked.connect(self._on_auto_import_clicked); tools.addWidget(btn_auto)
        self.chk_preview = RZCheckBox("Show Preview"); self.chk_preview.setChecked(True); self.chk_preview.toggled.connect(self._toggle_previews); tools.addWidget(self.chk_preview)
        self.scroll = RZScrollArea(); self.layout.addWidget(self.scroll); self.scroll_content = QtWidgets.QWidget(); self.scroll.setWidget(self.scroll_content); self.scroll.setWidgetResizable(True)
        self.list_layout = QtWidgets.QVBoxLayout(self.scroll_content); self.list_layout.setSpacing(4); self.list_layout.setContentsMargins(0, 0, 0, 0); self.list_layout.addStretch()

    def _toggle_previews(self, val): self.show_previews = val; self.update_ui()
    def _on_auto_import_clicked(self):
        root = image_utils.get_mod_base_path(); path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Dump Folder", root)
        if path: bpy.ops.rzm.tw_res_over_fill(directory=path); self.update_ui(); SIGNALS.structure_changed.emit()

    def update_ui(self):
        rzm = bpy.context.scene.rzm
        if not hasattr(self, "_widgets"): self._widgets = []
        count = len(rzm.tw_overrides)
        while len(self._widgets) > count: w = self._widgets.pop(); self.list_layout.removeWidget(w); w.hide(); w.setParent(None); w.deleteLater()
        while len(self._widgets) < count:
            new_idx = len(self._widgets); w = TexWorksOverrideItem(new_idx, rzm.tw_overrides[new_idx], self)
            self.list_layout.insertWidget(self.list_layout.count() - 1, w); self._widgets.append(w)
        for i, over in enumerate(rzm.tw_overrides): w = self._widgets[i]; w.index = i; w.update_data(over)

    def remove_item(self, idx): bpy.ops.rzm.remove_tw_override(index=idx); self.update_ui()

# --- TABS: MATERIALS ---
class TexWorksMaterialsTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self._block = False; self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(0, 5, 0, 0); tools = QtWidgets.QHBoxLayout(); self.layout.addLayout(tools)
        btn_add = RZPushButton("+ Add MaterialSlot"); btn_add.clicked.connect(lambda: bpy.ops.rzm.add_tw_material()); tools.addWidget(btn_add)
        self.scroll = RZScrollArea(); self.layout.addWidget(self.scroll); self.scroll_content = QtWidgets.QWidget(); self.scroll.setWidget(self.scroll_content); self.scroll.setWidgetResizable(True)
        self.list_layout = QtWidgets.QVBoxLayout(self.scroll_content); self.list_layout.setSpacing(2); self.list_layout.setContentsMargins(0, 0, 0, 0); self.list_layout.addStretch()
        self._widgets = []

    def update_ui(self):
        self._block = True
        rzm = bpy.context.scene.rzm
        count = len(rzm.tw_materials)
        while len(self._widgets) > count:
            it = self._widgets.pop(); self.list_layout.removeWidget(it); it.hide(); it.setParent(None); it.deleteLater()
        
        while len(self._widgets) < count:
            row_w = QtWidgets.QWidget(); row_w.setFixedHeight(28); row = QtWidgets.QHBoxLayout(row_w); row.setContentsMargins(5, 0, 5, 0)
            lbl = RZLabel(""); row_w.lbl = lbl; row.addWidget(lbl)
            btn_mat = RZPushButton(""); btn_mat.setCursor(QtCore.Qt.PointingHandCursor); btn_mat.setFixedHeight(24); row_w.btn_mat = btn_mat; row.addWidget(btn_mat, 1)
            btn_del = RZPushButton("✕"); btn_del.setFixedWidth(24); btn_del.setFixedHeight(24); row.addWidget(btn_del); row_w.btn_del = btn_del
            self.list_layout.insertWidget(len(self._widgets), row_w); self._widgets.append(row_w)

        for i, mat_item in enumerate(rzm.tw_materials):
            w = self._widgets[i]
            w.lbl.setText(f"M{i}:")
            w.btn_mat.setText(mat_item.material.name if mat_item.material else "None")
            try: w.btn_mat.clicked.disconnect()
            except: pass
            w.btn_mat.clicked.connect(lambda _, idx=i: self._select_material(idx))
            try: w.btn_del.clicked.disconnect()
            except: pass
            w.btn_del.clicked.connect(lambda _, idx=i: self._remove_material(idx))
        
        self._block = False
    def _select_material(self, idx): bpy.ops.rzm.tw_select_material('INVOKE_DEFAULT', index=idx)
    def _remove_material(self, idx): bpy.ops.rzm.remove_tw_material(index=idx)

# --- TABS: MAIN (SELECTION BASED) ---
class TexWorksDetailView(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(5, 5, 5, 5); self.layout.setSpacing(8)
        t = get_current_theme(); self.setStyleSheet(f"background-color: {t.get('bg_dark', '#1E2127')};")
    def add_section(self, title, icon=None):
        box = RZGroupBox(title, self); box.setStyleSheet("QGroupBox { border: 1px solid #3E4451; border-radius: 4px; margin-top: 10px; padding-top: 10px; font-weight: bold; color: #BBB; } QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; }")
        l = QtWidgets.QVBoxLayout(box); l.setContentsMargins(8, 15, 8, 8); l.setSpacing(4); self.layout.addWidget(box); return l

class TexWorksMainTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(0, 0, 0, 0); im = IconManager.get_instance(); self.mode = "BLOCKS"; self.show_details = False
        row_b = QtWidgets.QHBoxLayout(); row_b.setContentsMargins(5, 2, 5, 2); self.layout.addLayout(row_b)
        row_b.addWidget(RZLabel("Blocks:")); self.tab_blocks = RZTabRow(); self.tab_blocks.setFixedHeight(30); row_b.addWidget(self.tab_blocks, 1)
        btn_ops_b = QtWidgets.QHBoxLayout(); btn_ops_b.setSpacing(4); row_b.addLayout(btn_ops_b)
        btn_add_b = RZPushButton("Add Block"); btn_add_b.setFixedHeight(24); btn_add_b.clicked.connect(lambda: bpy.ops.rzm.add_tw_block()); btn_ops_b.addWidget(btn_add_b)
        btn_dup_b = RZPushButton("Copy"); btn_dup_b.setFixedHeight(24); btn_dup_b.clicked.connect(lambda: bpy.ops.rzm.duplicate_tw_block()); btn_ops_b.addWidget(btn_dup_b)
        btn_rem_b = RZPushButton("Delete"); btn_rem_b.setFixedHeight(24); btn_rem_b.clicked.connect(lambda: bpy.ops.rzm.remove_tw_block()); btn_ops_b.addWidget(btn_rem_b)
        row_m = QtWidgets.QHBoxLayout(); row_m.setContentsMargins(5, 0, 5, 0); self.layout.addLayout(row_m); self.tab_modes = RZTabRow(); self.tab_modes.setFixedHeight(30); row_m.addWidget(self.tab_modes, 1)
        self.tab_modes.sync_items(["BLOCKS", "COMPONENTS", "SLOTS"], 0)
        self.tab_modes.clicked.connect(self._set_mode)
        self.chk_details = RZCheckBox("Show Details")
        self.chk_details.setChecked(self.show_details)
        self.chk_details.toggled.connect(self._toggle_details)
        row_m.addWidget(self.chk_details)
        
        self.scroll = RZScrollArea()
        self.layout.addWidget(self.scroll, 1)
        self.scroll_w = QtWidgets.QWidget()
        self.scroll_l = QtWidgets.QVBoxLayout(self.scroll_w)
        self.scroll_l.setContentsMargins(0, 0, 0, 0); self.scroll_l.setSpacing(0)
        self.scroll.setWidget(self.scroll_w); self.scroll.setWidgetResizable(True)
        
        self.details = TexWorksDetailView()
        self.scroll_l.addWidget(self.details)
        self.tab_blocks.clicked.connect(lambda i: self._set_active("block", i))
        self._last_state = (None, -1, -1, -1)
        self._widgets = {} # Storage for persistent widgets in details view

        # Bottom Previews were moved inside the tabs.


    def _set_mode(self, idx): self.mode = ["BLOCKS", "COMPONENTS", "SLOTS"][idx]; self.update_ui()
    def _toggle_details(self, state): self.show_details = state; self.update_ui()
    def _set_active(self, type, idx):
        rzm = bpy.context.scene.rzm
        if type == "block": rzm.active_tw_block_index = idx
        elif type == "comp": b = rzm.tw_blocks[rzm.active_tw_block_index]; b.active_component_index = idx
        elif type == "slot": b = rzm.tw_blocks[rzm.active_tw_block_index]; c = b.components[b.active_component_index]; c.active_slot_index = idx
        self.update_ui()
    def _add_comp(self): bpy.ops.rzm.add_tw_component(block_index=bpy.context.scene.rzm.active_tw_block_index)
    def _rem_comp(self): rzm = bpy.context.scene.rzm; b = rzm.active_tw_block_index; c = rzm.tw_blocks[b].active_component_index; bpy.ops.rzm.remove_tw_component(block_index=b, index=c)
    def _add_slot(self): rzm = bpy.context.scene.rzm; b = rzm.active_tw_block_index; c = rzm.tw_blocks[b].active_component_index; bpy.ops.rzm.add_tw_slot(block_index=b, comp_index=c)
    def _rem_slot(self): rzm = bpy.context.scene.rzm; b = rzm.active_tw_block_index; c = rzm.tw_blocks[b].active_component_index; s = rzm.tw_blocks[b].components[c].active_slot_index; bpy.ops.rzm.remove_tw_slot(block_index=b, comp_index=c, index=s)
    def clear_layout(self, layout):
        if not layout: return
        while layout.count():
            it = layout.takeAt(0)
            if it.widget():
                w = it.widget()
                w.hide()
                w.setParent(None)
                w.deleteLater()
            elif it.layout():
                self.clear_layout(it.layout())
                it.layout().deleteLater()
        return True
    def update_ui(self):
        self._is_updating = True
        try:
            rzm = bpy.context.scene.rzm
            b_idx = rzm.active_tw_block_index
            block = rzm.tw_blocks[b_idx] if 0 <= b_idx < len(rzm.tw_blocks) else None
            
            if not block:
                self.clear_layout(self.details.layout)
                self._last_state = (None, b_idx, -1, -1, self.show_details)
                return
    
            c_idx = block.active_component_index if block else -1
            comp = block.components[c_idx] if (block and 0 <= c_idx < len(block.components)) else None
            s_idx = comp.active_slot_index if comp else -1
    
            self.tab_blocks.sync_items([b.name for b in rzm.tw_blocks], b_idx)
            self.tab_modes.sync_items(["BLOCKS", "COMPONENTS", "SLOTS"], ["BLOCKS", "COMPONENTS", "SLOTS"].index(self.mode))
            
            current_state = (self.mode, b_idx, c_idx, s_idx, self.show_details)
            state_changed = current_state != self._last_state
            self._last_state = current_state
    
            if state_changed:
                self._widgets.clear()
                self.clear_layout(self.details.layout)
                getattr(self, f"_draw_{self.mode.lower()}_mode")(block)
                self.details.layout.addStretch()
            else:
                getattr(self, f"_sync_{self.mode.lower()}_data")(block)
        finally:
            self._is_updating = False

    def _sync_widget(self, name, value):
        widget = self.details.findChild(QtWidgets.QWidget, name)
        if not widget: return
        if widget.hasFocus(): return
        
        widget.blockSignals(True)
        try:
            if hasattr(widget, "set_text_silent"): # RZLineEdit, RZFormulaInput
                widget.set_text_silent(str(value))
            elif isinstance(widget, (QtWidgets.QLineEdit, RZLineEdit)):
                if widget.text() != str(value): widget.setText(str(value))
            elif isinstance(widget, (QtWidgets.QSpinBox, RZSpinBox)):
                if widget.value() != int(value): widget.setValue(int(value))
            elif isinstance(widget, (QtWidgets.QDoubleSpinBox, RZDoubleSpinBox)):
                if abs(widget.value() - float(value)) > 0.0001: widget.setValue(float(value))
            elif isinstance(widget, QtWidgets.QComboBox):
                if widget.currentText() != str(value): widget.setCurrentText(str(value))
            elif isinstance(widget, (QtWidgets.QCheckBox, RZCheckBox)):
                checked = str(value).lower() in ["true", "1"]
                if widget.isChecked() != checked: widget.setChecked(checked)
        finally:
            widget.blockSignals(False)



    def _draw_blocks_mode(self, block):
        b_idx = bpy.context.scene.rzm.active_tw_block_index
        row_top = QtWidgets.QHBoxLayout(); self.details.layout.addLayout(row_top)
        self.blk_box = RZGroupBox("Atlas (Block Output)", self); l1 = QtWidgets.QVBoxLayout(self.blk_box)
        self.blk_pre = AtlasPreviewWidget(size=240, parent=self); l1.addWidget(self.blk_pre); row_top.addWidget(self.blk_box)
        l_core = QtWidgets.QVBoxLayout(); row_top.addLayout(l_core)
        row_n = QtWidgets.QHBoxLayout(); l_core.addLayout(row_n); row_n.addWidget(RZLabel("Name:"))
        e_name = RZLineEdit(); e_name.setObjectName("p_name"); self._widgets['name'] = e_name
        e_name.editingFinished.connect(lambda p=e_name: self._item_changed("blocks", b_idx, "name", -1, -1, p.text()))
        row_n.addWidget(e_name, 1)
        row_r = QtWidgets.QHBoxLayout(); l_core.addLayout(row_r); row_r.addWidget(RZLabel("Res Name:"))
        e_res = RZResourceLineEdit(); e_res.setObjectName("p_res"); self._widgets['res_name'] = e_res
        e_res.editingFinished.connect(lambda p=e_res: self._item_changed("blocks", b_idx, "resource_name", -1, -1, p.text()))
        row_r.addWidget(e_res, 1)
        self._widgets['info_lbl'] = RZLabel(); l_core.addWidget(self._widgets['info_lbl'])
        btn_exp = RZPushButton("Export Hierarchy"); btn_exp.clicked.connect(lambda: bpy.ops.rzm.tw_export_hierarchy(block_index=b_idx)); l_core.addWidget(btn_exp); l_core.addStretch()

        l_back = self.details.add_section("Backdrop"); row_back = QtWidgets.QHBoxLayout(); l_back.addLayout(row_back)
        self.back_pre = ResourcePreviewWidget(90, self); row_back.addWidget(self.back_pre)
        l_b_opts = QtWidgets.QVBoxLayout(); row_back.addLayout(l_b_opts)
        chk_b = RZCheckBox("Enable Backdrop"); chk_b.setObjectName("p_backdrop_enabled"); self._widgets['backdrop_en'] = chk_b
        chk_b.toggled.connect(lambda v: self._item_changed("blocks", b_idx, "backdrop_enabled", -1, -1, str(v))); l_b_opts.addWidget(chk_b)
        self._widgets['backdrop_res_row'] = QtWidgets.QWidget(); l_b_res = QtWidgets.QHBoxLayout(self._widgets['backdrop_res_row'])
        l_b_res.setContentsMargins(0,0,0,0); e_br = RZResourceLineEdit(); e_br.setObjectName("p_backdrop_res"); self._widgets['backdrop_res'] = e_br
        e_br.editingFinished.connect(lambda p=e_br: self._item_changed("blocks", b_idx, "backdrop_resource_name", -1, -1, p.text()))
        l_b_res.addWidget(RZLabel("Res:")); l_b_res.addWidget(e_br, 1); l_b_opts.addWidget(self._widgets['backdrop_res_row'])
        self._widgets['backdrop_rect_row'] = QtWidgets.QWidget(); l_b_rect = QtWidgets.QHBoxLayout(self._widgets['backdrop_rect_row'])
        l_b_rect.setContentsMargins(0,0,0,0)
        for i in range(4):
            sp = RZSpinBox(); sp.setObjectName(f"p_backdrop_rect_{i}"); self._widgets[f'back_rect_{i}'] = sp; sp.setRange(0, 16384)
            sp.editingFinished.connect(lambda p=sp, ix=i: self._item_changed("blocks", b_idx, f"backdrop_rect[{ix}]", -1, -1, p.value()))
            l_b_rect.addWidget(sp)
        l_b_opts.addWidget(self._widgets['backdrop_rect_row'])

        if self.show_details:
            l_sh = self.details.add_section("Shader & Atlas Config")
            row_t = QtWidgets.QHBoxLayout(); l_sh.addLayout(row_t)
            cb_sh = ComboBoxFix(); cb_sh.setObjectName("p_shader_type"); self._widgets['shader_type'] = cb_sh; cb_sh.addItems(["STANDARD", "SKIN", "CLOTH", "METAL"])
            cb_sh.currentTextChanged.connect(lambda v: self._item_changed("blocks", b_idx, "shader_type", -1, -1, v))
            row_t.addWidget(RZLabel("Shader Type:")); row_t.addWidget(cb_sh)
            l_sh.addWidget(RZLabel("Shader Config (Color x46):"))
            row_c = QtWidgets.QHBoxLayout(); l_sh.addLayout(row_c)
            for i in range(4):
                sp = RZDoubleSpinBox(); sp.setObjectName(f"p_shader_config_{i}"); self._widgets[f'sh_cfg_{i}'] = sp; sp.setRange(-1000, 1000)
                sp.editingFinished.connect(lambda p=sp, ix=i: self._item_changed("blocks", b_idx, f"shader_config[{ix}]", -1, -1, p.value()))
                row_c.addWidget(sp)
            l_sh.addWidget(RZLabel("Shader Overlay (Overlap x47):"))
            row_o = QtWidgets.QHBoxLayout(); l_sh.addLayout(row_o)
            for i in range(4):
                sp = RZDoubleSpinBox(); sp.setObjectName(f"p_shader_overlay_{i}"); self._widgets[f'sh_ovl_{i}'] = sp; sp.setRange(-1000, 1000)
                sp.editingFinished.connect(lambda p=sp, ix=i: self._item_changed("blocks", b_idx, f"shader_overlay[{ix}]", -1, -1, p.value()))
                row_o.addWidget(sp)
            row_sh = QtWidgets.QHBoxLayout(); l_sh.addLayout(row_sh)
            chk_sh = RZCheckBox("Shared Textures"); chk_sh.setObjectName("p_shared_textures"); self._widgets['use_shared'] = chk_sh
            chk_sh.toggled.connect(lambda v: self._item_changed("blocks", b_idx, "use_shared_textures", -1, -1, str(v))); row_sh.addWidget(chk_sh)
            e_sh_b = RZLineEdit(); e_sh_b.setObjectName("p_shared_block"); self._widgets['shared_blk'] = e_sh_b; e_sh_b.setPlaceholderText("Block Name")
            e_sh_b.editingFinished.connect(lambda: self._item_changed("blocks", b_idx, "shared_textures_block", -1, -1, e_sh_b.text()))
            row_sh.addWidget(e_sh_b, 1)
            row_uv = QtWidgets.QHBoxLayout(); l_sh.addLayout(row_uv)
            sp_uv = RZDoubleSpinBox(); sp_uv.setObjectName("p_uv_rescale"); self._widgets['uv_rescale'] = sp_uv; sp_uv.setRange(0.01, 10.0)
            sp_uv.editingFinished.connect(lambda p=sp_uv: self._item_changed("blocks", b_idx, "uv_rescale", -1, -1, str(p.value())))
            row_uv.addWidget(RZLabel("UV Rescale:")); row_uv.addWidget(sp_uv)
        self._sync_blocks_data(block)

    def _sync_blocks_data(self, block):
        w = self._widgets
        w['name'].set_text_silent(block.name)
        w['res_name'].set_text_silent(block.resource_name)
        res_info = next((r for r in bpy.context.scene.rzm.tw_resources if r.name == block.resource_name), None)
        info_txt = f"Format: {res_info.format} | {res_info.resolution[0]}x{res_info.resolution[1]}" if res_info else "Format: None | 0x0"
        w['info_lbl'].setText(info_txt)
        blk_data = image_utils.collect_block_preview_data(block)
        self.blk_pre.update_with_layers(blk_data["layers"], blk_data["res"])
        w['backdrop_en'].setChecked(block.backdrop_enabled)
        w['backdrop_res_row'].setVisible(block.backdrop_enabled)
        w['backdrop_rect_row'].setVisible(block.backdrop_enabled)
        if block.backdrop_enabled:
            w['backdrop_res'].set_text_silent(block.backdrop_resource_name)
            for i in range(4): w[f'back_rect_{i}'].setValue(block.backdrop_rect[i])
        self.back_pre.update_resource(block.backdrop_resource_name if block.backdrop_enabled else "")

        if self.show_details:
            w['shader_type'].setCurrentText(block.shader_type)
            for i in range(4): w[f'sh_cfg_{i}'].setValue(block.shader_config[i]); w[f'sh_ovl_{i}'].setValue(block.shader_overlay[i])
            w['use_shared'].setChecked(block.use_shared_textures)
            w['shared_blk'].set_text_silent(block.shared_textures_block)
            w['shared_blk'].setVisible(block.use_shared_textures)
            w['uv_rescale'].setValue(block.uv_rescale)

    def _toggle_cmp_slots(self, v):
        self.cmp_show_slots = v
        self.update_ui()

    def _draw_components_mode(self, block):
        b_idx = bpy.context.scene.rzm.active_tw_block_index
        row_sel = QtWidgets.QHBoxLayout(); self.details.layout.addLayout(row_sel)
        row_sel.addWidget(RZLabel("Components:")); self.tab_comps = RZTabRow(); row_sel.addWidget(self.tab_comps, 1)
        self.tab_comps.sync_items([c.name for c in block.components], block.active_component_index)
        self.tab_comps.clicked.connect(lambda i: self._set_active("comp", i))
        btn_add = RZPushButton("Add Comp"); btn_add.setFixedHeight(24); btn_add.clicked.connect(self._add_comp); row_sel.addWidget(btn_add)
        btn_rem = RZPushButton("Delete"); btn_rem.setFixedHeight(24); btn_rem.clicked.connect(self._rem_comp); row_sel.addWidget(btn_rem)
        if block.active_component_index < 0 or block.active_component_index >= len(block.components): return
        comp = block.components[block.active_component_index]; c_idx = block.active_component_index
        l_core = self.details.add_section(f"[{comp.name}] Settings")
        if self.show_details:
            chk_sh = RZCheckBox("Use Shared Config"); self._widgets['use_shared_cfg'] = chk_sh
            chk_sh.toggled.connect(lambda v: self._item_changed("components", c_idx, "use_shared_config", b_idx, -1, str(v))); l_core.addWidget(chk_sh)
            self._widgets['shared_cfg_row'] = QtWidgets.QWidget(); l_sh = QtWidgets.QHBoxLayout(self._widgets['shared_cfg_row'])
            l_sh.setContentsMargins(0,0,0,0); e_sh_b = RZLineEdit(); self._widgets['sh_cfg_blk'] = e_sh_b; e_sh_b.setPlaceholderText("Block")
            e_sh_b.editingFinished.connect(lambda p=e_sh_b: self._item_changed("components", c_idx, "shared_config_block", b_idx, -1, p.text())); l_sh.addWidget(e_sh_b)
            e_sh_c = RZLineEdit(); self._widgets['sh_cfg_comp'] = e_sh_c; e_sh_c.setPlaceholderText("Comp")
            e_sh_c.editingFinished.connect(lambda p=e_sh_c: self._item_changed("components", c_idx, "shared_config_component", b_idx, -1, p.text())); l_sh.addWidget(e_sh_c)
            l_core.addWidget(self._widgets['shared_cfg_row'])
        self._widgets['comp_core_section'] = QtWidgets.QWidget(); l_cc = QtWidgets.QVBoxLayout(self._widgets['comp_core_section']); l_cc.setContentsMargins(0,0,0,0); l_core.addWidget(self._widgets['comp_core_section'])
        r1 = QtWidgets.QHBoxLayout(); l_cc.addLayout(r1); e_name = RZLineEdit(); self._widgets['name'] = e_name; e_name.editingFinished.connect(lambda p=e_name: self._item_changed("components", c_idx, "name", b_idx, -1, p.text()))
        r1.addWidget(RZLabel("Name:")); r1.addWidget(e_name, 1)
        r2 = QtWidgets.QHBoxLayout(); l_cc.addLayout(r2); v_base = QtWidgets.QVBoxLayout(); r2.addLayout(v_base)
        self.cmp_pre = AtlasPreviewWidget(size=140, parent=self); v_base.addWidget(self.cmp_pre); chk_shw = RZCheckBox("Show Slots Layers")
        self._widgets['show_slots'] = chk_shw; chk_shw.toggled.connect(self._toggle_cmp_slots); v_base.addWidget(chk_shw)
        l_base_info = QtWidgets.QVBoxLayout(); r2.addLayout(l_base_info); row_b_res = QtWidgets.QHBoxLayout(); l_base_info.addLayout(row_b_res)
        e_base = RZResourceLineEdit(); self._widgets['base_res'] = e_base; e_base.editingFinished.connect(lambda p=e_base: self._item_changed("components", c_idx, "base_resource_name", b_idx, -1, p.text()))
        row_b_res.addWidget(RZLabel("Base Res:")); row_b_res.addWidget(e_base, 1); l_base_info.addWidget(RZLabel("Atlas Rect (X,Y,W,H):"))
        r_atl = QtWidgets.QHBoxLayout(); l_base_info.addLayout(r_atl)
        for i in range(4):
            sp = RZSpinBox(); self._widgets[f'rect_{i}'] = sp; sp.setRange(0, 16384)
            sp.editingFinished.connect(lambda p=sp, ix=i: self._item_changed("components", c_idx, f"rect[{ix}]", b_idx, -1, p.value())); r_atl.addWidget(sp)
        if self.show_details:
            l_base_info.addWidget(RZLabel("Base Rect (Source):")); r_src = QtWidgets.QHBoxLayout(); l_base_info.addLayout(r_src)
            for i in range(4):
                sp = RZSpinBox(); self._widgets[f'base_rect_{i}'] = sp; sp.setRange(0, 16384)
                sp.editingFinished.connect(lambda p=sp, ix=i: self._item_changed("components", c_idx, f"base_rect[{ix}]", b_idx, -1, p.value())); r_src.addWidget(sp)
        l_base_info.addStretch(); l_hsv = self.details.add_section("HSV Filter"); r_hsv = QtWidgets.QHBoxLayout(); l_hsv.addLayout(r_hsv)
        self.hsv_pre = ResourcePreviewWidget(90, self); r_hsv.addWidget(self.hsv_pre); v_hsv = QtWidgets.QVBoxLayout()
        r_hsv.addLayout(v_hsv)
        h_hsv_chks = QtWidgets.QHBoxLayout(); v_hsv.addLayout(h_hsv_chks)
        for h in ["hsv_enabled", "mask_enabled", "hsv_mask_enabled"]:
            chk = RZCheckBox(h.replace("_enabled", "").upper()); self._widgets[h] = chk
            chk.toggled.connect(lambda v, lh=h: self._item_changed("components", c_idx, lh, b_idx, -1, str(v))); h_hsv_chks.addWidget(chk)
        h_mask_preview = QtWidgets.QHBoxLayout(); v_hsv.addLayout(h_mask_preview)
        self.comp_mask_pre = ResourcePreviewWidget(48, self); h_mask_preview.addWidget(self.comp_mask_pre)
        e_m_lbl = RZLabel("Mask: mask.png (Auto)"); h_mask_preview.addWidget(e_m_lbl, 1)
        e_hlink = RZLineEdit(); self._widgets['hsv_link'] = e_hlink; e_hlink.setPlaceholderText("HSV Link")
        e_hlink.editingFinished.connect(lambda p=e_hlink: self._item_changed("components", c_idx, "hsv_link", b_idx, -1, p.text())); v_hsv.addWidget(e_hlink)
        l_morph = self.details.add_section("TexMorph"); r_morph = QtWidgets.QHBoxLayout(); l_morph.addLayout(r_morph)
        self.morph_pre = ResourcePreviewWidget(90, self); r_morph.addWidget(self.morph_pre); v_morph = QtWidgets.QVBoxLayout(); r_morph.addLayout(v_morph)
        chk_m = RZCheckBox("Enable TexMorph"); self._widgets['morph_en'] = chk_m
        chk_m.toggled.connect(lambda v: self._item_changed("components", c_idx, "tex_morph_enabled", b_idx, -1, str(v))); v_morph.addWidget(chk_m)
        e_m_res = RZResourceLineEdit(); self._widgets['morph_res'] = e_m_res; e_m_res.editingFinished.connect(lambda p=e_m_res: self._item_changed("components", c_idx, "tex_morph_resource_name", b_idx, -1, p.text()))
        v_morph.addWidget(e_m_res); e_mlink = RZLineEdit(); self._widgets['morph_lnk'] = e_mlink; e_mlink.setPlaceholderText("Morph Variable Link ($Var)")
        e_mlink.editingFinished.connect(lambda p=e_mlink: self._item_changed("components", c_idx, "tex_morph_link", b_idx, -1, p.text())); v_morph.addWidget(e_mlink)
        self._sync_components_data(block)

    def _sync_components_data(self, block):
        if block.active_component_index < 0: return
        comp = block.components[block.active_component_index]; w = self._widgets
        if self.show_details and 'use_shared_cfg' in w:
            w['use_shared_cfg'].setChecked(comp.use_shared_config)
            w['shared_cfg_row'].setVisible(comp.use_shared_config)
            if comp.use_shared_config:
                w['sh_cfg_blk'].set_text_silent(comp.shared_config_block)
                w['sh_cfg_comp'].set_text_silent(comp.shared_config_component)
                w['comp_core_section'].hide(); return
        w['comp_core_section'].show(); w['name'].set_text_silent(comp.name); w['base_res'].set_text_silent(comp.base_resource_name)
        w['show_slots'].setChecked(getattr(self, "cmp_show_slots", True))
        for i in range(4):
            w[f'rect_{i}'].setValue(comp.rect[i])
            if self.show_details and f'base_rect_{0}' in w: w[f'base_rect_{i}'].setValue(comp.base_rect[i])
        for h in ["hsv_enabled", "mask_enabled", "hsv_mask_enabled"]: w[h].setChecked(getattr(comp, h))
        w['hsv_link'].set_text_silent(comp.hsv_link); w['morph_en'].setChecked(comp.tex_morph_enabled)
        w['morph_res'].set_text_silent(comp.tex_morph_resource_name); w['morph_res'].setVisible(comp.tex_morph_enabled)
        w['morph_lnk'].set_text_silent(comp.tex_morph_link); w['morph_lnk'].setVisible(comp.tex_morph_enabled)
        p = image_utils.get_resource_path(comp.base_resource_name) or (image_utils.get_resource_path(block.backdrop_resource_name) if block.backdrop_resource_name else None)
        layers = [{"rect": [0, 0, comp.rect[2], comp.rect[3]], "path": p, "opacity": 1.0}]
        if getattr(self, "cmp_show_slots", True):
            for s in comp.slots:
                if s.active: layers.append({"rect": list(s.rect), "path": "", "is_decal": True, "opacity": 0.8})
        self.cmp_pre.update_with_layers(layers, (comp.rect[2] if comp.rect[2]>0 else 1024, comp.rect[3] if comp.rect[3]>0 else 1024))
        if p: self.hsv_pre.update_from_path(p)
        if comp.tex_morph_enabled: self.morph_pre.update_resource(comp.tex_morph_resource_name)
        
        # Update Component Mask Preview
        base_path = image_utils.get_mod_base_path()
        if comp.mask_enabled and base_path:
            mask_path = os.path.join(base_path, "TexWorks", block.name, comp.name, "mask.png")
            self.comp_mask_pre.update_from_path(mask_path)
        else:
            self.comp_mask_pre.update_resource("")


    def _add_layer(self):
        rzm = bpy.context.scene.rzm; b = rzm.active_tw_block_index; c = rzm.tw_blocks[b].active_component_index; s = rzm.tw_blocks[b].components[c].active_slot_index
        bpy.ops.rzm.add_tw_decal_layer(block_index=b, comp_index=c, slot_index=s)
    def _rem_layer(self, layer_idx):
        rzm = bpy.context.scene.rzm; b = rzm.active_tw_block_index; c = rzm.tw_blocks[b].active_component_index; s = rzm.tw_blocks[b].components[c].active_slot_index
        bpy.ops.rzm.remove_tw_decal_layer(block_index=b, comp_index=c, slot_index=s, index=layer_idx)
    def _move_layer(self, layer_idx, dir):
        rzm = bpy.context.scene.rzm; b = rzm.active_tw_block_index; c = rzm.tw_blocks[b].active_component_index; s = rzm.tw_blocks[b].components[c].active_slot_index
        bpy.ops.rzm.move_tw_item(collection_name="decal_layers", index=layer_idx, direction=dir, block_index=b, comp_index=c, slot_index=s)

    def _draw_slots_mode(self, block):
        if block.active_component_index < 0: return
        comp = block.components[block.active_component_index]; b_idx = bpy.context.scene.rzm.active_tw_block_index; c_idx = block.active_component_index
        row_sel = QtWidgets.QHBoxLayout(); self.details.layout.addLayout(row_sel)
        row_sel.addWidget(RZLabel("Slots:")); self.tab_slots = RZTabRow(); row_sel.addWidget(self.tab_slots, 1)
        self.tab_slots.sync_items([s.name for s in comp.slots], comp.active_slot_index)
        self.tab_slots.clicked.connect(lambda i: self._set_active("slot", i))
        btn_add = RZPushButton("Add Slot"); btn_add.setFixedHeight(24); btn_add.clicked.connect(self._add_slot); row_sel.addWidget(btn_add)
        btn_rem = RZPushButton("Delete"); btn_rem.setFixedHeight(24); btn_rem.clicked.connect(self._rem_slot); row_sel.addWidget(btn_rem)
        if comp.active_slot_index < 0 or comp.active_slot_index >= len(comp.slots): return
        slot = comp.slots[comp.active_slot_index]; s_idx = comp.active_slot_index
        l_core = self.details.add_section(f"[{slot.name}] Settings")
        r_top = QtWidgets.QHBoxLayout(); l_core.addLayout(r_top)
        self.slot_pre = AtlasPreviewWidget(size=140, parent=self); r_top.addWidget(self.slot_pre)
        l_info = QtWidgets.QVBoxLayout(); r_top.addLayout(l_info)
        chk_act = RZCheckBox("Active"); self._widgets['active'] = chk_act
        chk_act.toggled.connect(lambda v: self._item_changed("slots", s_idx, "active", b_idx, c_idx, str(v))); l_info.addWidget(chk_act)
        r1 = QtWidgets.QHBoxLayout(); l_info.addLayout(r1); e_name = RZLineEdit(); self._widgets['name'] = e_name; e_name.editingFinished.connect(lambda p=e_name: self._item_changed("slots", s_idx, "name", b_idx, c_idx, p.text()))
        r1.addWidget(RZLabel("Name:")); r1.addWidget(e_name, 1); l_info.addStretch()
        l_mp = self.details.add_section("Multi-Pass / Symmetries")
        r_mp = QtWidgets.QHBoxLayout(); l_mp.addLayout(r_mp)
        cb_mode = RZComboBox(); self._widgets['mp_mode'] = cb_mode; cb_mode.addItems(["NONE", "DUPLICATE", "INDIVIDUAL"])
        cb_mode.currentTextChanged.connect(lambda v: self._item_changed("slots", s_idx, "multi_pass_mode", b_idx, c_idx, v))
        r_mp.addWidget(RZLabel("Mode:")); r_mp.addWidget(cb_mode, 1)
        self._widgets['mp_details'] = QtWidgets.QWidget(); l_mpd = QtWidgets.QVBoxLayout(self._widgets['mp_details']); l_mpd.setContentsMargins(0,0,0,0); l_mp.addWidget(self._widgets['mp_details'])
        r_md = QtWidgets.QHBoxLayout(); l_mpd.addLayout(r_md); r_md.addWidget(RZLabel("Data:"))
        for i in range(4):
            sp = RZDoubleSpinBox(); self._widgets[f'mp_data_{i}'] = sp; sp.setRange(-10000.0, 10000.0)
            sp.editingFinished.connect(lambda p=sp, ix=i: self._item_changed("slots", s_idx, f"multi_pass_data[{ix}]", b_idx, c_idx, p.value()))
            r_md.addWidget(sp)
        btn_cp = RZColorButton(); self._widgets['mp_data_cp'] = btn_cp; btn_cp.setFixedSize(24, 24)
        btn_cp.colorChanged.connect(lambda c: self._item_changed("slots", s_idx, "multi_pass_data", b_idx, c_idx, f"{c[0]},{c[1]},{c[2]},{c[3]}"))
        r_md.addWidget(btn_cp)
        r_mr = QtWidgets.QHBoxLayout(); l_mpd.addLayout(r_mr); r_mr.addWidget(RZLabel("Rect:"))
        for i in range(4):
            sp = RZSpinBox(); self._widgets[f'mp_rect_{i}'] = sp; sp.setRange(0, 16384)
            sp.editingFinished.connect(lambda p=sp, ix=i: self._item_changed("slots", s_idx, f"multi_pass_rect[{ix}]", b_idx, c_idx, p.value())); r_mr.addWidget(sp)
        r_mops = QtWidgets.QHBoxLayout(); l_mpd.addLayout(r_mops)
        r_mops.addWidget(RZLabel("Rot:")); sp_mrot = RZSpinBox(); self._widgets['mp_rot'] = sp_mrot; sp_mrot.setRange(-360, 360)
        sp_mrot.editingFinished.connect(lambda p=sp_mrot: self._item_changed("slots", s_idx, "multi_pass_rotation", b_idx, c_idx, p.value())); r_mops.addWidget(sp_mrot)
        chk_mm = RZCheckBox("M"); self._widgets['mp_mirror'] = chk_mm; chk_mm.toggled.connect(lambda v: self._item_changed("slots", s_idx, "multi_pass_mirror", b_idx, c_idx, str(v))); r_mops.addWidget(chk_mm)
        chk_mf = RZCheckBox("F"); self._widgets['mp_flip'] = chk_mf; chk_mf.toggled.connect(lambda v: self._item_changed("slots", s_idx, "multi_pass_flip", b_idx, c_idx, str(v))); r_mops.addWidget(chk_mf)
        chk_d = RZCheckBox("Dummy"); self._widgets['mp_dummy'] = chk_d; chk_d.toggled.connect(lambda v: self._item_changed("slots", s_idx, "multi_pass_dummy", b_idx, c_idx, str(v))); r_mops.addWidget(chk_d)
        l_trans = self.details.add_section("Transform")
        r_rect = QtWidgets.QHBoxLayout(); l_trans.addLayout(r_rect); r_rect.addWidget(RZLabel("Rect:"))
        for i in range(4):
            sp = RZSpinBox(); self._widgets[f'rect_{i}'] = sp; sp.setRange(0, 16384)
            sp.editingFinished.connect(lambda p=sp, ix=i: self._item_changed("slots", s_idx, f"rect[{ix}]", b_idx, c_idx, p.value())); r_rect.addWidget(sp)
        r_ops = QtWidgets.QHBoxLayout(); l_trans.addLayout(r_ops)
        r_ops.addWidget(RZLabel("Rot:")); sp_rot = RZSpinBox(); self._widgets['rot'] = sp_rot; sp_rot.setRange(-360, 360)
        sp_rot.editingFinished.connect(lambda p=sp_rot: self._item_changed("slots", s_idx, "rotation", b_idx, c_idx, p.value())); r_ops.addWidget(sp_rot)
        chk_m = RZCheckBox("M"); self._widgets['mirror'] = chk_m; chk_m.toggled.connect(lambda v: self._item_changed("slots", s_idx, "mirror", b_idx, c_idx, str(v))); r_ops.addWidget(chk_m)
        chk_f = RZCheckBox("F"); self._widgets['flip'] = chk_f; chk_f.toggled.connect(lambda v: self._item_changed("slots", s_idx, "flip", b_idx, c_idx, str(v))); r_ops.addWidget(chk_f)
        l_layers = self.details.add_section("Decal Layers")
        r_l_top = QtWidgets.QHBoxLayout(); l_layers.addLayout(r_l_top); btn_add_l = RZPushButton("+ Layer"); btn_add_l.clicked.connect(self._add_layer); r_l_top.addWidget(btn_add_l); r_l_top.addStretch()
        self.lyr_row = RZTabRow(self); self.lyr_row.setFixedHeight(140); l_layers.addWidget(self.lyr_row)
        if self.show_details:
            l_warp = self.details.add_section("Warping / Lattice (3x3)")
            for pw in [0, 1]:
                en_prop = f"warp_p{pw}_enabled"; chk_w = RZCheckBox(f"Pass {pw} Warp"); self._widgets[en_prop] = chk_w
                chk_w.toggled.connect(lambda v, p=en_prop: self._item_changed("slots", s_idx, p, b_idx, c_idx, str(v))); l_warp.addWidget(chk_w)
                self._widgets[f'warp_grid_{pw}'] = QtWidgets.QWidget(); gl = QtWidgets.QGridLayout(self._widgets[f'warp_grid_{pw}']); l_warp.addWidget(self._widgets[f'warp_grid_{pw}'])
                for i in range(18):
                    sp = RZDoubleSpinBox(); self._widgets[f'warp_{pw}_{i}'] = sp; sp.setRange(-1.0, 2.0)
                    sp.editingFinished.connect(lambda p=sp, ix=i, pwx=pw: self._item_changed("slots", s_idx, f"warp_p{pwx}_grid[{ix}]", b_idx, c_idx, p.value()))
                    gl.addWidget(sp, i // 6, i % 6)
        l_fx = self.details.add_section("Effects & Masking")
        row_h = QtWidgets.QHBoxLayout(); l_fx.addLayout(row_h)
        for h in ["hsv_enabled", "hsv_only", "hsv_mask_enabled"]:
            chk = RZCheckBox(h.replace("hsv_", "").upper()); self._widgets[h] = chk
            chk.toggled.connect(lambda v, ch=h: self._item_changed("slots", s_idx, ch, b_idx, c_idx, str(v))); row_h.addWidget(chk)
        e_hl = RZLineEdit(); self._widgets['hsv_link'] = e_hl; e_hl.setPlaceholderText("HSV Link")
        e_hl.editingFinished.connect(lambda p=e_hl: self._item_changed("slots", s_idx, "hsv_link", b_idx, c_idx, p.text())); row_h.addWidget(e_hl, 1)
        row_m = QtWidgets.QHBoxLayout(); l_fx.addLayout(row_m); chk_m = RZCheckBox("MASK"); self._widgets['mask_en'] = chk_m
        chk_m.toggled.connect(lambda v: self._item_changed("slots", s_idx, "mask_enabled", b_idx, c_idx, str(v))); row_m.addWidget(chk_m)
        self.slot_mask_pre = ResourcePreviewWidget(48, self); row_m.addWidget(self.slot_mask_pre)
        e_ms = RZLabel("Source (Automatic Path)"); row_m.addWidget(e_ms, 1)
        for px in [0, 1]:
            chk = RZCheckBox(f"P{px}"); self._widgets[f'pass{px}_mask'] = chk
            chk.toggled.connect(lambda v, lpx=px: self._item_changed("slots", s_idx, f"pass{lpx}_use_mask", b_idx, c_idx, str(v))); row_m.addWidget(chk)
        self._sync_slots_data(block)

    def _sync_slots_data(self, block):
        if block.active_component_index < 0: return
        comp = block.components[block.active_component_index]
        if comp.active_slot_index < 0 or comp.active_slot_index >= len(comp.slots): return
        slot = comp.slots[comp.active_slot_index]; b_idx = bpy.context.scene.rzm.active_tw_block_index; c_idx = block.active_component_index; s_idx = comp.active_slot_index; w = self._widgets
        w['active'].setChecked(slot.active); w['name'].set_text_silent(slot.name); w['mp_mode'].setCurrentText(slot.multi_pass_mode)
        w['mp_details'].setVisible(slot.multi_pass_mode != 'NONE')
        if slot.multi_pass_mode != 'NONE':
            for i in range(4): w[f'mp_data_{i}'].setValue(slot.multi_pass_data[i])
            w['mp_data_cp'].set_color(slot.multi_pass_data)
            for i in range(4): w[f'mp_rect_{i}'].setValue(slot.multi_pass_rect[i])
            w['mp_rot'].setValue(slot.multi_pass_rotation); w['mp_mirror'].setChecked(slot.multi_pass_mirror); w['mp_flip'].setChecked(slot.multi_pass_flip); w['mp_dummy'].setChecked(slot.multi_pass_dummy)
        for i in range(4): w[f'rect_{i}'].setValue(slot.rect[i])
        w['rot'].setValue(slot.rotation); w['mirror'].setChecked(slot.mirror); w['flip'].setChecked(slot.flip)
        if self.show_details:
            for pw in [0, 1]:
                en = getattr(slot, f"warp_p{pw}_enabled"); w[f'warp_p{pw}_enabled'].setChecked(en)
                w[f'warp_grid_{pw}'].setVisible(en)
                if en:
                    grid = getattr(slot, f"warp_p{pw}_grid")
                    for i in range(18): w[f'warp_{pw}_{i}'].setValue(grid[i])
        for h in ["hsv_enabled", "hsv_only", "hsv_mask_enabled"]: w[h].setChecked(getattr(slot, h))
        w['hsv_link'].set_text_silent(slot.hsv_link); w['mask_en'].setChecked(slot.mask_enabled)
        # Update Slot Mask Preview
        base_path = image_utils.get_mod_base_path()
        if slot.mask_enabled and base_path:
            m_comp = comp.name.replace(" ", "")
            m_slot = slot.name.replace(" ", "")
            mask_name = f"{m_comp}{m_slot}.MASK.png"
            mask_path = os.path.join(base_path, "TexWorks", block.name, comp.name, slot.name, mask_name)
            self.slot_mask_pre.update_from_path(mask_path)
        else:
            self.slot_mask_pre.update_resource("")
        for px in [0, 1]: w[f'pass{px}_mask'].setChecked(getattr(slot, f"pass{px}_use_mask"))
        p = image_utils.get_resource_path(comp.base_resource_name) or (image_utils.get_resource_path(block.backdrop_resource_name) if block.backdrop_resource_name else None)
        layers = [{"rect": [0, 0, comp.rect[2], comp.rect[3]], "path": p, "opacity": 1.0}]
        if slot.active: layers.append({"rect": list(slot.rect), "path": "", "is_decal": True, "opacity": 1.0})
        self.slot_pre.update_with_layers(layers, (comp.rect[2] if comp.rect[2]>0 else 1024, comp.rect[3] if comp.rect[3]>0 else 1024))
        self.lyr_row.clear()
        import os
        for l_idx, lyr in enumerate(slot.decal_layers):
            layer_frame = QtWidgets.QFrame(); layer_frame.setStyleSheet("QFrame { background: #1a1e24; border: 1px solid #3E4451; border-radius: 4px; }")
            lv = QtWidgets.QVBoxLayout(layer_frame); lv.setContentsMargins(5,5,5,5); lv.setSpacing(4)
            lh = QtWidgets.QHBoxLayout(); lv.addLayout(lh)
            le_name = RZLineEdit(); le_name.set_text_silent(lyr.name); le_name.editingFinished.connect(lambda p=le_name, ix=l_idx: self._item_changed("decal_layers", ix, "name", b_idx, c_idx, p.text(), s_idx))
            lh.addWidget(le_name, 1)
            btn_up = RZPushButton("Up"); btn_up.setFixedSize(30,20); btn_up.clicked.connect(lambda _, ix=l_idx: self._move_layer(ix, "UP")); lh.addWidget(btn_up)
            btn_dn = RZPushButton("Dn"); btn_dn.setFixedSize(30,20); btn_dn.clicked.connect(lambda _, ix=l_idx: self._move_layer(ix, "DOWN")); lh.addWidget(btn_dn)
            btn_rm = RZPushButton("Del"); btn_rm.setFixedSize(30,20); btn_rm.clicked.connect(lambda _, ix=l_idx: self._rem_layer(ix)); lh.addWidget(btn_rm)
            
            # Decal Gallery for this layer
            gal = QtWidgets.QWidget(); gl = QtWidgets.QHBoxLayout(gal); gl.setContentsMargins(0,0,0,0); gl.setSpacing(5)
            scroll = RZScrollArea(); scroll.setFixedHeight(100); scroll.setWidget(gal); scroll.setWidgetResizable(True); scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded); lv.addWidget(scroll)
            
            for i in range(lyr.count):
                item_w = QtWidgets.QWidget(); iv = QtWidgets.QVBoxLayout(item_w); iv.setContentsMargins(0,0,0,0); iv.setSpacing(2)
                pre = ResourcePreviewWidget(64, self); iv.addWidget(pre)
                iv.addWidget(RZLabel(f"Decal {i}", self), alignment=QtCore.Qt.AlignCenter)
                # ModNameFolder\TexWorks\BlockName\ComponentName\SlotName\LayerName\0.png
                decal_path = os.path.join(base_path, "TexWorks", block.name, comp.name, slot.name, lyr.name, f"{i}.png")
                pre.update_from_path(decal_path)
                gl.addWidget(item_w)
            gl.addStretch()
            
            lc = QtWidgets.QHBoxLayout(); lv.addLayout(lc); lc.addWidget(RZLabel("Count:")); sp_c = RZSpinBox(); sp_c.setRange(1, 100); sp_c.setValue(lyr.count)
            sp_c.editingFinished.connect(lambda p=sp_c, ix=l_idx: self._item_changed("decal_layers", ix, "count", b_idx, c_idx, p.value(), s_idx)); lc.addWidget(sp_c, 1)
            self.lyr_row.container_layout.addWidget(layer_frame)
        self.lyr_row.container_layout.addStretch()

    def _item_changed(self, coll, idx, prop, b, c, val=None, s=-1):
        if getattr(self, "_is_updating", False): return
        if val is None:
            sender = self.sender()
            if hasattr(sender, "value"): val = sender.value()
            elif hasattr(sender, "isChecked"): val = sender.isChecked()
            elif hasattr(sender, "currentText"): val = sender.currentText()
            else: return

        kwargs = {
            'collection_name': coll,
            'index': idx,
            'prop_name': prop,
            'value_str': str(val),
            'block_index': b,
            'comp_index': c,
            'slot_index': s
        }
        bpy.ops.rzm.update_tw_item(**kwargs)
        blender_bridge.safe_undo_push(f"TW: Change {prop}")

class TexWorksManager(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(0, 0, 0, 0); self.layout.setSpacing(0); self.tabs_info = [("Main", "tab_main"), ("Resources", "tab_res"), ("Overrides", "tab_over"), ("Materials", "tab_mat"), ("Registry", "tab_reg")]
        self.anchor_bar = RZTexWorksAnchorBar(self.tabs_info); self.anchor_bar.clicked.connect(self._on_tab_clicked); self.layout.addWidget(self.anchor_bar); self.stack = QtWidgets.QStackedWidget(); self.layout.addWidget(self.stack)
        self.tab_widgets = {"tab_main": TexWorksMainTab(), "tab_res": TexWorksResourcesTab(), "tab_over": TexWorksOverridesTab(), "tab_mat": TexWorksMaterialsTab(), "tab_reg": RZImageRegistryWidget()}
        for t_id in ["tab_main", "tab_res", "tab_over", "tab_mat", "tab_reg"]: self.stack.addWidget(self.tab_widgets[t_id])
        self.anchor_bar.set_active("tab_main"); self.stack.setCurrentWidget(self.tab_widgets["tab_main"]); self._refresh_timer = QtCore.QTimer(); self._refresh_timer.setSingleShot(True); self._refresh_timer.timeout.connect(self._do_refresh); SIGNALS.structure_changed.connect(self.refresh_current)
    def _on_tab_clicked(self, t_id): self.anchor_bar.set_active(t_id); self.stack.setCurrentWidget(self.tab_widgets[t_id]); self.refresh_current()
    def refresh_current(self): self._refresh_timer.start(100)
    def _do_refresh(self): w = self.stack.currentWidget(); getattr(w, 'update_ui')() if hasattr(w, 'update_ui') else None
    def on_activate(self):
        self._do_refresh()
        # --- EXPERIMENTAL CACHING ---
        # Rayvich: Disabled due to Blender context crashes during tab switching.
        # bp = image_utils.get_mod_base_path()
        # if bp:
        #     image_utils.AsyncImageLoader.get_instance().precache_folder(bp)

class RZMTexWorksPanel(RZEditorPanel):
    PANEL_ID = "TEXWORKS"; PANEL_NAME = "TexWorks"; PANEL_ICON = "image"
    def __init__(self, parent=None): super().__init__(parent); self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(0, 0, 0, 0); self.manager = TexWorksManager(); self.layout.addWidget(self.manager)
    def on_activate(self): self.manager.on_activate()
    def enterEvent(self, event): RZContextManager.get_instance().update_input(self.cursor().pos(), (0,0), "TEXWORKS"); super().enterEvent(event)