# RZMenu/qt_editor/widgets/texworks/tabs.py

import os
import bpy
from functools import partial
from PySide6 import QtWidgets, QtCore, QtGui

from ..lib.widgets import (RZPushButton, RZLabel, RZLineEdit, RZComboBox, 
                           RZSpinBox, RZDoubleSpinBox, RZCheckBox, RZGroupBox, RZScrollArea)
from ..lib.theme import get_current_theme
from ...core.signals import SIGNALS
from . import utils

# --- SHARED WIDGETS ---

class RZTabRow(QtWidgets.QWidget):
    clicked = QtCore.Signal(int)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)
        self.buttons = []
        
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
            
            is_active = (i == active_idx)
            style = f"background: {accent if is_active else '#444'}; color: {'white' if is_active else '#999'}; font-weight: {'bold' if is_active else 'normal'}; border-radius: 4px; border: none; padding: 0 10px;"
            btn.setStyleSheet(style)
            
            btn.clicked.connect(partial(self.clicked.emit, i))
            self.layout.addWidget(btn)
            self.buttons.append(btn)
        self.layout.addStretch()

class ScanWorker(QtCore.QThread):
    finished = QtCore.Signal(list)
    def __init__(self, path, subfolder, recursive=False):
        super().__init__()
        self.path = path; self.subfolder = subfolder; self.recursive = recursive
    def run(self):
        files = utils.scan_textures(self.path, self.subfolder, self.recursive)
        self.finished.emit(files)

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
        fmt = utils.get_dds_format(filepath)
        
        lbl_name = RZLabel(f"<b>{name}</b>"); lbl_name.setStyleSheet("font-size: 13px; color: white;")
        lbl_fmt = RZLabel(f"Format: {fmt}"); lbl_fmt.setStyleSheet("color: #888;")
        lbl_path = RZLabel(filepath); lbl_path.setStyleSheet("font-size: 10px; color: #555;")
        
        inf_l.addWidget(lbl_name); inf_l.addWidget(lbl_fmt); inf_l.addWidget(lbl_path); inf_l.addStretch()

    def set_preview(self, pix):
        if pix: 
            self.lbl_preview.setPixmap(pix)
            self.lbl_preview.setAlignment(QtCore.Qt.AlignCenter)
        else:
            self.lbl_preview.setText("E")

class ResourcePreviewWidget(QtWidgets.QWidget):
    """Small thumbnail of a registered resource."""
    def __init__(self, size=64, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.lbl = RZLabel()
        self.lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl.setStyleSheet("background: #000; border: 1px solid #333; border-radius: 2px;")
        self.layout.addWidget(self.lbl)
        
    def update_resource(self, resource_name):
        rzm = bpy.context.scene.rzm
        res = next((r for r in rzm.tw_resources if r.name == resource_name), None)
        
        if not res:
            self.lbl.setPixmap(utils.get_placeholder_pixmap("EMPTY", self.width()))
            return

        if res.type == 'ON_DISK':
            pix = utils.load_texture_to_pixmap(res.path, self.width())
            self.lbl.setPixmap(pix)
        elif res.type == 'VIRTUAL':
            pix = utils.get_placeholder_pixmap("VIRTUAL", self.width(), format_id=res.format)
            self.lbl.setPixmap(pix)
        else:
            self.lbl.setPixmap(utils.get_placeholder_pixmap("EMPTY", self.width()))

# --- TAB: MAIN (SELECTION BASED) ---

class TexWorksDetailView(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(0, 5, 0, 0); self.layout.setSpacing(4)
        self.layout.addStretch()
        
    def add_section(self, title, icon=None):
        box = RZGroupBox(title, self)
        box.layout_box = QtWidgets.QVBoxLayout(box); box.layout_box.setContentsMargins(8, 20, 8, 8); box.layout_box.setSpacing(4)
        self.layout.insertWidget(self.layout.count() - 1, box)
        return box.layout_box

class TexWorksMainTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(5, 5, 5, 5); self.layout.setSpacing(4)
        
        # Selection Bar
        self.w_nav = QtWidgets.QWidget(); self.w_nav.setFixedHeight(75); nav_l = QtWidgets.QVBoxLayout(self.w_nav); nav_l.setContentsMargins(0,0,0,0); self.layout.addWidget(self.w_nav)
        self.row_blocks = RZTabRow(); self.row_blocks.clicked.connect(lambda i: self._set_active('block', i)); nav_l.addWidget(RZLabel("Blocks:")); nav_l.addWidget(self.row_blocks)
        self.w_comps = QtWidgets.QWidget(); comps_l = QtWidgets.QVBoxLayout(self.w_comps); comps_l.setContentsMargins(0,0,0,0); self.w_comps.setFixedHeight(75); nav_l.addWidget(RZLabel("Components:")); self.row_comps = RZTabRow(); self.row_comps.clicked.connect(lambda i: self._set_active('comp', i)); comps_l.addWidget(self.row_comps)
        self.w_slots = QtWidgets.QWidget(); slots_l = QtWidgets.QVBoxLayout(self.w_slots); slots_l.setContentsMargins(0,0,0,0); self.w_slots.setFixedHeight(75); nav_l.addWidget(RZLabel("Slots (Decals):")); self.row_slots = RZTabRow(); self.row_slots.clicked.connect(lambda i: self._set_active('slot', i)); slots_l.addWidget(self.row_slots)
        
        # Detail Area
        self.scroll = RZScrollArea(self); self.layout.addWidget(self.scroll, 1)
        self.details = TexWorksDetailView(self); self.scroll.setWidget(self.details); self.scroll.setWidgetResizable(True)

    def _set_active(self, type, idx):
        rzm = bpy.context.scene.rzm
        if type == 'block': rzm.active_tw_block_index = idx
        elif type == 'comp': rzm.tw_blocks[rzm.active_tw_block_index].active_component_index = idx
        elif type == 'slot':
            b = rzm.tw_blocks[rzm.active_tw_block_index]
            c = b.components[b.active_component_index]
            c.active_slot_index = idx
        self.update_ui()

    def update_ui(self):
        rzm = bpy.context.scene.rzm
        self.row_blocks.sync_items([b.name for b in rzm.tw_blocks], rzm.active_tw_block_index)
        
        while self.details.layout.count() > 1:
            it = self.details.layout.takeAt(0)
            if not it: continue
            
            w = it.widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
            
            lay = it.layout()
            if lay:
                while lay.count():
                    sit = lay.takeAt(0)
                    if sit and sit.widget():
                        sw = sit.widget()
                        sw.hide()
                        sw.setParent(None)
                        sw.deleteLater()
                lay.deleteLater()
            
        b_idx = rzm.active_tw_block_index
        self.w_comps.setVisible(b_idx >= 0 and len(rzm.tw_blocks) > 0)
        if b_idx < 0: return

        block = rzm.tw_blocks[b_idx]
        self.row_comps.sync_items([c.name for c in block.components], block.active_component_index)
        
        c_idx = block.active_component_index
        self.w_slots.setVisible(c_idx >= 0 and len(block.components) > 0)
        
        # 1. Block Section
        s_block_lay = self.details.add_section(f"Block: {block.name}")
        l_res = QtWidgets.QHBoxLayout(); s_block_lay.addLayout(l_res)
        l_res.addWidget(RZLabel("Output: " + block.resource_name, self))
        
        l_back = QtWidgets.QHBoxLayout(); s_block_lay.addLayout(l_back)
        chk_back = RZCheckBox("Use Backdrop", self)
        chk_back.setChecked(block.backdrop_enabled)
        chk_back.toggled.connect(lambda v: setattr(block, "backdrop_enabled", bool(v)))
        l_back.addWidget(chk_back)
        
        self.pre_back = ResourcePreviewWidget(48, self); l_back.addWidget(self.pre_back)
        self.pre_back.update_resource(block.backdrop_resource_name)
        
        # 2. Component Section
        if c_idx >= 0:
            comp = block.components[c_idx]
            self.row_slots.sync_items([s.name for s in comp.slots], comp.active_slot_index)
            s_comp_lay = self.details.add_section(f"Component: {comp.name}")
            
            l_comp_res = QtWidgets.QHBoxLayout(); s_comp_lay.addLayout(l_comp_res)
            l_comp_res.addWidget(RZLabel("Base: " + comp.base_resource_name))
            pre_base = ResourcePreviewWidget(48); l_comp_res.addWidget(pre_base)
            pre_base.update_resource(comp.base_resource_name)
            
            if comp.tex_morph_enabled:
                l_morph = QtWidgets.QHBoxLayout(); s_comp_lay.addLayout(l_morph)
                l_morph.addWidget(RZLabel("Morph: " + comp.tex_morph_resource_name))
                pre_morph = ResourcePreviewWidget(48); l_morph.addWidget(pre_morph)
                pre_morph.update_resource(comp.tex_morph_resource_name)
            
            # 3. Slot Section
            s_idx = comp.active_slot_index
            if 0 <= s_idx < len(comp.slots):
                slot = comp.slots[s_idx]
                s_slot_lay = self.details.add_section(f"Slot: {slot.name}")
                
                # Recursive Decal Search
                l_decal = QtWidgets.QHBoxLayout(); s_slot_lay.addLayout(l_decal)
                l_decal.addWidget(RZLabel("Decal Preview:"))
                pre_decal = RZLabel(); pre_decal.setFixedSize(64, 64); pre_decal.setStyleSheet("background: #000; border: 1px solid #333;")
                l_decal.addWidget(pre_decal)
                
                self._load_slot_decal_async(pre_decal, comp.name, slot.name)
                
                # Utils
                l_calc = QtWidgets.QHBoxLayout(); s_slot_lay.addLayout(l_calc)
                btn_c0 = RZPushButton("Calc P0 (JSON)"); btn_c0.clicked.connect(lambda: bpy.ops.rzm.calc_slot_config(block_index=b_idx, comp_index=c_idx, slot_index=s_idx, target_pass=0))
                btn_c1 = RZPushButton("Calc P1 (JSON)"); btn_c1.clicked.connect(lambda: bpy.ops.rzm.calc_slot_config(block_index=b_idx, comp_index=c_idx, slot_index=s_idx, target_pass=1))
                l_calc.addWidget(btn_c0); l_calc.addWidget(btn_c1)

        # 4. Total Preview (Summary)
        s_total_lay = self.details.add_section("Total Block Preview")
        self.pre_total = RZLabel(); self.pre_total.setFixedHeight(200); self.pre_total.setStyleSheet("background: #000; border: 1px dashed #444;")
        self.pre_total.setAlignment(QtCore.Qt.AlignCenter)
        s_total_lay.addWidget(self.pre_total)
        
        # Async load the composite
        QtCore.QTimer.singleShot(100, lambda: self._update_total_preview(block))

    def _update_total_preview(self, block):
        pix = utils.get_total_block_preview(block, 200)
        self.pre_total.setPixmap(pix)

    def _load_slot_decal_async(self, label, comp_name, slot_name):
        base = utils.get_mod_base_path()
        if not base: return
        
        # Heuristic: TexWorks/<Comp>/<Slot>.png
        path = os.path.join(base, "TexWorks", comp_name, f"{slot_name}.png")
        if os.path.exists(path):
            pix = utils.load_texture_to_pixmap(path, 64)
            if pix: label.setPixmap(pix)
        else:
            label.setText("?")

# --- TAB: RESOURCES ---

class TexWorksResourcesTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(5, 5, 5, 5); self.layout.setSpacing(4)
        
        l_top = QtWidgets.QHBoxLayout(); self.layout.addLayout(l_top)
        self.btn_add = RZPushButton("➕ Add Resource"); self.btn_add.clicked.connect(lambda: bpy.ops.rzm.add_tw_item(collection_name="tw_resources"))
        l_top.addWidget(self.btn_add); l_top.addStretch()
        
        self.scroll = RZScrollArea(); self.layout.addWidget(self.scroll, 1)
        self.container = QtWidgets.QWidget(); self.c_layout = QtWidgets.QVBoxLayout(self.container); self.c_layout.setContentsMargins(0, 0, 0, 0); self.c_layout.setSpacing(2); self.c_layout.addStretch()
        self.scroll.setWidget(self.container); self.scroll.setWidgetResizable(True)

    def update_ui(self):
        rzm = bpy.context.scene.rzm
        while self.c_layout.count() > 1:
            it = self.c_layout.takeAt(0)
            if it:
                if it.widget():
                    w = it.widget()
                    w.hide(); w.setParent(None); w.deleteLater()
                elif it.layout():
                    it.layout().deleteLater()
            
        for i, res in enumerate(rzm.tw_resources):
            item = TexWorksResourceItem(res, i, self)
            self.c_layout.insertWidget(self.c_layout.count() - 1, item)

class TexWorksResourceItem(QtWidgets.QWidget):
    def __init__(self, res, idx, parent=None):
        super().__init__(parent)
        self.res = res; self.idx = idx
        self.setFixedHeight(100) # Slightly taller for path display
        l = QtWidgets.QHBoxLayout(self); l.setContentsMargins(4, 4, 4, 4); l.setSpacing(8)
        
        # Preview
        self.pre = ResourcePreviewWidget(64)
        l.addWidget(self.pre)
        self.pre.update_resource(res.name)
        
        v_l = QtWidgets.QVBoxLayout(); l.addLayout(v_l)
        
        # Name & Remove
        h_top = QtWidgets.QHBoxLayout(); v_l.addLayout(h_top)
        edit_name = RZLineEdit(res.name); edit_name.textChanged.connect(lambda v: setattr(res, "name", v))
        h_top.addWidget(edit_name)
        btn_del = RZPushButton("X"); btn_del.setFixedSize(20, 20); btn_del.clicked.connect(lambda: bpy.ops.rzm.remove_tw_item(collection_name="tw_resources", index=idx))
        h_top.addWidget(btn_del)
        
        # Type & Path/Format
        h_bot = QtWidgets.QHBoxLayout(); v_l.addLayout(h_bot)
        cmb_type = RZComboBox(); cmb_type.addItems(["Empty", "On Disk", "Virtual"])
        idx_t = {'EMPTY':0, 'ON_DISK':1, 'VIRTUAL':2}.get(res.type, 0)
        cmb_type.setCurrentIndex(idx_t)
        cmb_type.currentIndexChanged.connect(self._on_type_changed)
        h_bot.addWidget(cmb_type)
        
        if res.type == 'ON_DISK':
            edit_path = RZLineEdit(res.path); edit_path.setPlaceholderText("Textures/...")
            edit_path.textChanged.connect(lambda v: self._update_path(v))
            h_bot.addWidget(edit_path, 1)
            
            # Show resolved path for debugging
            res_path = utils.get_resource_path(res.name)
            lbl_resolved = RZLabel(f"Resolved: {res_path}" if res_path else "Not Found!"); lbl_resolved.setStyleSheet("color: #666; font-size: 10px;")
            v_l.addWidget(lbl_resolved)
        elif res.type == 'VIRTUAL':
            lbl_fmt = RZLabel(res.format.replace("DXGI_FORMAT_", "")); lbl_fmt.setStyleSheet("color: #888; font-size: 10px;")
            h_bot.addWidget(lbl_fmt)

    def _on_type_changed(self, i):
        t = ['EMPTY', 'ON_DISK', 'VIRTUAL'][i]
        self.res.type = t
        SIGNALS.structure_changed.emit()

    def _update_path(self, path):
        self.res.path = path; self.pre.update_resource(self.res.name)

# --- STANDALONE DEBUG TABS ---

class TexWorksTestTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.btn_scan = RZPushButton("🔄 Scan Textures Folder")
        self.btn_scan.clicked.connect(self.start_scan); self.layout.addWidget(self.btn_scan)
        self.scroll = RZScrollArea(); self.layout.addWidget(self.scroll, 1)
        self.container = QtWidgets.QWidget(); self.c_layout = QtWidgets.QVBoxLayout(self.container)
        self.c_layout.setContentsMargins(0, 0, 0, 0); self.c_layout.setSpacing(2); self.c_layout.addStretch()
        self.scroll.setWidget(self.container); self.scroll.setWidgetResizable(True)
        self.pending_files = []; self._load_timer = QtCore.QTimer(); self._load_timer.timeout.connect(self._load_next_batch)

    def start_scan(self):
        path = utils.get_mod_base_path()
        if not path: return
        self.btn_scan.setEnabled(False); self.btn_scan.setText("⏳ Scanning...")
        while self.c_layout.count() > 1:
            it = self.c_layout.takeAt(0); it.widget().deleteLater() if it.widget() else None
        self.worker = ScanWorker(path, "Textures"); self.worker.finished.connect(self.on_scan_finished); self.worker.start()

    def on_scan_finished(self, files):
        self.btn_scan.setEnabled(True); self.btn_scan.setText("🔄 Scan Textures Folder")
        self.pending_files = files; self._load_timer.start(50)

    def _load_next_batch(self):
        if not self.pending_files: self._load_timer.stop(); return
        for _ in range(3):
            if not self.pending_files: break
            f = self.pending_files.pop(0); item = TexturePreviewItem(f, self)
            self.c_layout.insertWidget(self.c_layout.count() - 1, item)
            pix = utils.load_texture_to_pixmap(f, 90); item.set_preview(pix)

class TexWorksTestSlotsTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.btn_scan = RZPushButton("🔄 Scan TexWorks PNGs (Recursive)")
        self.btn_scan.clicked.connect(self.start_scan); self.layout.addWidget(self.btn_scan)
        self.scroll = RZScrollArea(); self.layout.addWidget(self.scroll, 1)
        self.container = QtWidgets.QWidget(); self.c_layout = QtWidgets.QVBoxLayout(self.container)
        self.c_layout.setContentsMargins(0, 0, 0, 0); self.c_layout.setSpacing(2); self.c_layout.addStretch()
        self.scroll.setWidget(self.container); self.scroll.setWidgetResizable(True)
        self.pending_files = []; self._load_timer = QtCore.QTimer(); self._load_timer.timeout.connect(self._load_next)

    def start_scan(self):
        path = utils.get_mod_base_path()
        if not path: return
        self.btn_scan.setEnabled(False); self.btn_scan.setText("⏳ Scanning...")
        while self.c_layout.count() > 1:
            it = self.c_layout.takeAt(0); it.widget().deleteLater() if it.widget() else None
        self.worker = ScanWorker(path, "TexWorks", True); self.worker.finished.connect(self.on_scan_finished); self.worker.start()

    def on_scan_finished(self, files):
        self.btn_scan.setEnabled(True); self.btn_scan.setText("🔄 Scan TexWorks PNGs (Recursive)")
        self.pending_files = [f for f in files if f.lower().endswith('.png')]; self._load_timer.start(30)

    def _load_next(self):
        if not self.pending_files: self._load_timer.stop(); return
        f = self.pending_files.pop(0); item = TexturePreviewItem(f, self)
        self.c_layout.insertWidget(self.c_layout.count() - 1, item)
        pix = utils.load_texture_to_pixmap(f, 90); item.set_preview(pix)

# --- TABS: OTHER ---

class TexWorksOverridesTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(5, 5, 5, 5); self.layout.setSpacing(4)
        l_top = QtWidgets.QHBoxLayout(); self.layout.addLayout(l_top)
        self.btn_add = RZPushButton("➕ Add Override"); self.btn_add.clicked.connect(lambda: bpy.ops.rzm.add_tw_item(collection_name="tw_overrides"))
        l_top.addWidget(self.btn_add); l_top.addStretch()
        self.scroll = RZScrollArea(); self.layout.addWidget(self.scroll, 1)
        self.container = QtWidgets.QWidget(); self.c_layout = QtWidgets.QVBoxLayout(self.container); self.c_layout.setContentsMargins(0, 0, 0, 0); self.c_layout.setSpacing(2); self.c_layout.addStretch()
        self.scroll.setWidget(self.container); self.scroll.setWidgetResizable(True)

    def update_ui(self):
        rzm = bpy.context.scene.rzm
        while self.c_layout.count() > 1:
            it = self.c_layout.takeAt(0); it.widget().deleteLater() if it.widget() else None
        for i, ov in enumerate(rzm.tw_overrides):
            item = self._create_item(ov, i); self.c_layout.insertWidget(self.c_layout.count() - 1, item)

    def _create_item(self, ov, idx):
        w = QtWidgets.QWidget(self); w.setFixedHeight(60); l = QtWidgets.QHBoxLayout(w); l.setContentsMargins(4, 4, 4, 4)
        edit_name = RZLineEdit(ov.name); edit_name.textChanged.connect(lambda v: setattr(ov, "name", v)); l.addWidget(edit_name)
        edit_hash = RZLineEdit(ov.hash); edit_hash.setPlaceholderText("Hash..."); edit_hash.textChanged.connect(lambda v: setattr(ov, "hash", v)); l.addWidget(edit_hash, 1)
        btn_del = RZPushButton("X"); btn_del.setFixedSize(20, 20); btn_del.clicked.connect(lambda: bpy.ops.rzm.remove_tw_item(collection_name="tw_overrides", index=idx)); l.addWidget(btn_del)
        return w

class TexWorksMaterialsTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(5, 5, 5, 5); self.layout.setSpacing(4)
        l_top = QtWidgets.QHBoxLayout(); self.layout.addLayout(l_top)
        self.btn_add = RZPushButton("➕ Add Material"); self.btn_add.clicked.connect(lambda: bpy.ops.rzm.add_tw_item(collection_name="tw_materials"))
        l_top.addWidget(self.btn_add); l_top.addStretch()
        self.scroll = RZScrollArea(); self.layout.addWidget(self.scroll, 1)
        self.container = QtWidgets.QWidget(); self.c_layout = QtWidgets.QVBoxLayout(self.container); self.c_layout.setContentsMargins(0, 0, 0, 0); self.c_layout.setSpacing(2); self.c_layout.addStretch()
        self.scroll.setWidget(self.container); self.scroll.setWidgetResizable(True)

    def update_ui(self):
        rzm = bpy.context.scene.rzm
        while self.c_layout.count() > 1:
            it = self.c_layout.takeAt(0); it.widget().deleteLater() if it.widget() else None
        for i, mat in enumerate(rzm.tw_materials):
            item = self._create_item(mat, i); self.c_layout.insertWidget(self.c_layout.count() - 1, item)

    def _create_item(self, mat, idx):
        w = QtWidgets.QWidget(self); w.setFixedHeight(40); l = QtWidgets.QHBoxLayout(w); l.setContentsMargins(4, 4, 4, 4)
        l.addWidget(RZLabel(mat.name if mat.name else f"Mat {idx}"))
        btn_del = RZPushButton("X"); btn_del.setFixedSize(20, 20); btn_del.clicked.connect(lambda: bpy.ops.rzm.remove_tw_item(collection_name="tw_materials", index=idx)); l.addWidget(btn_del)
        return w
