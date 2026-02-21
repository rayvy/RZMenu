# RZMenu/qt_editor/widgets/texworks_panel.py
from PySide6 import QtWidgets, QtCore, QtGui
import bpy
from functools import partial

from .panel_base import RZEditorPanel
from .configurator import BaseConfigTab
from .lib.widgets import RZPushButton, RZLabel, RZLineEdit, RZComboBox, RZSpinBox, RZDoubleSpinBox, RZCheckBox, RZGroupBox
from .lib.theme import get_current_theme
from ..core.signals import SIGNALS

class TexWorksManager(QtWidgets.QWidget):
    """
    (black) TEXWORKS Main Block Module: Полностью неработоспособен.
    Main manager for the standalone TexWorks panel.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        self.tab_bar = QtWidgets.QTabBar()
        self.tab_bar.setDrawBase(False)
        self.tab_bar.setExpanding(False)
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        self.layout.addWidget(self.tab_bar)
        
        self.stack = QtWidgets.QStackedWidget()
        self.layout.addWidget(self.stack)
        
        self.tabs = []
        self._init_tabs()
        self.apply_theme()
        
        # Subscribe to structure changes for immediate refresh
        SIGNALS.structure_changed.connect(self.refresh_current)

    def _init_tabs(self):
        # Local imports to avoid circular dependencies if strictly structured, 
        # but here classes are in same file below.
        self.add_tab("Overrides", TexWorksOverridesTab())
        self.add_tab("Resources", TexWorksResourcesTab())
        self.add_tab("Main", TexWorksMainTab())
        self.add_tab("Materials", TexWorksMaterialsTab())

    def add_tab(self, name, widget):
        self.tab_bar.addTab(name)
        self.stack.addWidget(widget)
        self.tabs.append((name, widget))

    def _on_tab_changed(self, index):
        self.stack.setCurrentIndex(index)
        self.refresh_current()

    def refresh_current(self):
        index = self.stack.currentIndex()
        if 0 <= index < len(self.tabs):
            widget = self.tabs[index][1]
            widget.update_ui()

    def on_activate(self):
        self.refresh_current()

    def apply_theme(self):
        t = get_current_theme()
        self.tab_bar.setStyleSheet(f"""
            QTabBar::tab {{
                background: {t.get('bg_modal', '#252930')};
                color: {t.get('text_dim', '#9DA5B4')};
                padding: 6px 12px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
                font-size: 11px;
            }}
            QTabBar::tab:selected {{
                background: {t.get('bg_panel', '#2C313A')};
                color: {t.get('text_main', '#E0E2E4')};
                font-weight: bold;
            }}
        """)
        self.stack.setStyleSheet(f"background-color: {t.get('bg_panel', '#2C313A')};")

class RZMTexWorksPanel(RZEditorPanel):
    """
    Stand-alone panel for TexWorks configuration.
    """
    PANEL_ID = "TEXWORKS"
    PANEL_NAME = "TexWorks"
    PANEL_ICON = "image" 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.manager = TexWorksManager()
        self.layout.addWidget(self.manager)

    @classmethod
    def get_panel_info(cls):
        return {
            "id": cls.PANEL_ID,
            "name": cls.PANEL_NAME,
            "icon": cls.PANEL_ICON
        }

    def on_activate(self):
        self.manager.on_activate()
        
    def update_theme_styles(self):
        self.manager.apply_theme()

    def enterEvent(self, event):
        from ..context import RZContextManager
        RZContextManager.get_instance().update_input(
             self.cursor().pos(), (0,0), "TEXWORKS"
        )
        super().enterEvent(event)

# --- REFINED TAB WIDGETS ---

class TexWorksResourcesTab(BaseConfigTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        l = self.add_section("Resources & Virtual Textures")
        h_ctrl = QtWidgets.QHBoxLayout()
        btn_add = RZPushButton("Add Resource")
        btn_add.clicked.connect(lambda: (self._call_op("add_tw_resource"), self.update_ui()))
        h_ctrl.addWidget(btn_add); h_ctrl.addStretch()
        l.addLayout(h_ctrl)

        self.res_list = QtWidgets.QVBoxLayout()
        self.res_list.setSpacing(1)
        l.addLayout(self.res_list)
        from .lib.ui_helpers import ListItemManager
        self.manager = ListItemManager(self.res_list, self._create_item, self._update_item)

    def _create_item(self, index):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 2)
        
        # Header Row
        row = QtWidgets.QHBoxLayout(); row.setContentsMargins(0, 0, 0, 0)
        lbl = RZLabel(f"[{index}]"); row.addWidget(lbl)
        
        name = RZLineEdit(); name.setPlaceholderText("Resource Name")
        name.editingFinished.connect(lambda: self.on_item_changed("resources", w.property("item_index"), "name", name.text()))
        row.addWidget(name)
        
        cb_type = RZComboBox(); cb_type.addItems(["EMPTY", "ON_DISK", "VIRTUAL"])
        cb_type.currentTextChanged.connect(lambda v: (self.on_item_changed("resources", w.property("item_index"), "type", v), self.update_ui()))
        row.addWidget(cb_type)
        
        self.add_move_controls(w, row, "resources")
        
        btn_rem = RZPushButton("×"); btn_rem.setFixedWidth(25)
        btn_rem.clicked.connect(lambda: (self._call_op("remove_tw_resource", index=w.property("item_index")), self.update_ui()))
        row.addWidget(btn_rem)
        v.addLayout(row)
        
        # Separator line
        line = QtWidgets.QFrame(); line.setFrameShape(QtWidgets.QFrame.HLine); line.setFrameShadow(QtWidgets.QFrame.Sunken)
        line.setStyleSheet("background-color: #3e4451; margin: 2px 0;")
        v.addWidget(line)
        
        # Details
        details = QtWidgets.QWidget(); v_det = QtWidgets.QVBoxLayout(details); v_det.setContentsMargins(20, 0, 0, 0)
        
        # Path (For ON_DISK)
        h_path = QtWidgets.QWidget(); l_path = QtWidgets.QHBoxLayout(h_path); l_path.setContentsMargins(0, 0, 0, 0)
        path = RZLineEdit(); path.setPlaceholderText("Path")
        path.editingFinished.connect(lambda: self.on_item_changed("resources", w.property("item_index"), "path", path.text()))
        l_path.addWidget(RZLabel("Path:")); l_path.addWidget(path)
        v_det.addWidget(h_path)
        
        # Res/Format (For VIRTUAL)
        h_fmt = QtWidgets.QWidget(); l_fmt = QtWidgets.QHBoxLayout(h_fmt); l_fmt.setContentsMargins(0, 0, 0, 0)
        l_fmt.addWidget(RZLabel("Res:"))
        res_x = RZSpinBox(); res_x.setRange(1, 16384); res_x.setSuffix(" x")
        res_x.valueChanged.connect(lambda v: self.on_item_changed("resources", w.property("item_index"), "resolution[0]", str(v)))
        l_fmt.addWidget(res_x)
        res_y = RZSpinBox(); res_y.setRange(1, 16384)
        res_y.valueChanged.connect(lambda v: self.on_item_changed("resources", w.property("item_index"), "resolution[1]", str(v)))
        l_fmt.addWidget(res_y)
        
        l_fmt.addWidget(RZLabel("Format:"))
        cb_fmt = RZComboBox()
        cb_fmt.addItems([
            'DXGI_FORMAT_R8G8B8A8_TYPELESS', 'DXGI_FORMAT_R8G8B8A8_UNORM', 
            'DXGI_FORMAT_R8G8B8A8_UNORM_SRGB', 'DXGI_FORMAT_R8G8_TYPELESS', 
            'DXGI_FORMAT_R32_FLOAT', 'DXGI_FORMAT_BC7_UNORM'
        ])
        cb_fmt.currentTextChanged.connect(lambda v: self.on_item_changed("resources", w.property("item_index"), "format", v))
        l_fmt.addWidget(cb_fmt)
        v_det.addWidget(h_fmt)
        
        v.addWidget(details)
        w.refs = {'lbl': lbl, 'name': name, 'type': cb_type, 'path': path, 'res_x': res_x, 'res_y': res_y, 'cb_fmt': cb_fmt, 'details': details, 'h_path': h_path, 'h_fmt': h_fmt}
        return w

    def _update_item(self, w, item, index, parent_index=-1):
        w.setProperty("item_index", index)
        r = w.refs
        r['lbl'].setText(f"[{index}]")
        if r['name'].text() != item.name: r['name'].setText(item.name)
        if r['type'].currentText() != item.type:
            r['type'].blockSignals(True); r['type'].setCurrentText(item.type); r['type'].blockSignals(False)
        
        # Visibility logic
        is_virtual = (item.type == 'VIRTUAL')
        is_disk = (item.type == 'ON_DISK')
        
        r['details'].setVisible(item.type != 'EMPTY')
        r['h_path'].setVisible(is_disk)
        r['h_fmt'].setVisible(is_virtual) # Only show format/res for Virtual as requested
        
        if is_disk and r['path'].text() != item.path: r['path'].setText(item.path)
        
        if is_virtual:
            if r['res_x'].value() != item.resolution[0]: r['res_x'].setValue(item.resolution[0])
            if r['res_y'].value() != item.resolution[1]: r['res_y'].setValue(item.resolution[1])
            if r['cb_fmt'].currentText() != item.format:
                r['cb_fmt'].blockSignals(True); r['cb_fmt'].setCurrentText(item.format); r['cb_fmt'].blockSignals(False)

    def update_ui(self):
        self._block = True
        if not bpy.context or not bpy.context.scene: return
        self.manager.sync(bpy.context.scene.rzm.tw_resources)
        self._block = False

    def on_item_changed(self, coll, index, prop, val):
        if self._block: return
        self._call_op("update_tw_item", collection_name=coll, index=index, prop_name=prop, value_str=val)

class TexWorksOverridesTab(BaseConfigTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        l = self.add_section("Static Texture Overrides (Hash Based)")
        h_ctrl = QtWidgets.QHBoxLayout()
        btn_add = RZPushButton("Add Override")
        btn_add.clicked.connect(lambda: (self._call_op("add_tw_override"), self.update_ui()))
        h_ctrl.addWidget(btn_add); h_ctrl.addStretch()
        l.addLayout(h_ctrl)

        self.list = QtWidgets.QVBoxLayout()
        l.addLayout(self.list)
        from .lib.ui_helpers import ListItemManager
        self.manager = ListItemManager(self.list, self._create_item, self._update_item)

    def _create_item(self, index):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 5)
        
        # Row 1: Name + Controls
        r1 = QtWidgets.QHBoxLayout(); r1.setContentsMargins(0, 0, 0, 0)
        lbl = RZLabel(f"[{index}]"); r1.addWidget(lbl)
        name = RZLineEdit(); name.setPlaceholderText("Override Name")
        name.editingFinished.connect(lambda: self.on_item_changed("overrides", w.property("item_index"), "name", name.text()))
        r1.addWidget(name)
        
        r1.addStretch()
        self.add_move_controls(w, r1, "overrides")
        btn_rem = RZPushButton("×"); btn_rem.setFixedWidth(25)
        btn_rem.clicked.connect(lambda: (self._call_op("remove_tw_override", index=w.property("item_index")), self.update_ui()))
        r1.addWidget(btn_rem)
        v.addLayout(r1)
        
        # Row 2: Hash + Resource
        r2 = QtWidgets.QHBoxLayout(); r2.setContentsMargins(20, 0, 0, 0)
        hsh = RZLineEdit(); hsh.setPlaceholderText("Hash")
        hsh.setFixedWidth(120) 
        hsh.editingFinished.connect(lambda: self.on_item_changed("overrides", w.property("item_index"), "hash", hsh.text()))
        r2.addWidget(hsh)
        
        res = RZLineEdit(); res.setPlaceholderText("Resource Name")
        res.editingFinished.connect(lambda: self.on_item_changed("overrides", w.property("item_index"), "resource_name", res.text()))
        r2.addWidget(res)
        v.addLayout(r2)
        
        line = QtWidgets.QFrame(); line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setStyleSheet("background-color: #3e4451; margin-top: 4px;")
        v.addWidget(line)

        w.refs = {'lbl': lbl, 'name': name, 'hash': hsh, 'res': res}
        return w

    def _update_item(self, w, item, index, parent_index=-1):
        w.setProperty("item_index", index)
        r = w.refs
        r['lbl'].setText(f"[{index}]")
        if r['name'].text() != item.name: r['name'].setText(item.name)
        if r['hash'].text() != item.hash: r['hash'].setText(item.hash)
        if r['res'].text() != item.resource_name: r['res'].setText(item.resource_name)

    def update_ui(self):
        self._block = True
        if not bpy.context or not bpy.context.scene: return
        self.manager.sync(bpy.context.scene.rzm.tw_overrides)
        self._block = False

    def on_item_changed(self, coll, index, prop, val):
        if self._block: return
        self._call_op("update_tw_item", collection_name=coll, index=index, prop_name=prop, value_str=val)

class TexWorksMaterialsTab(BaseConfigTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        l = self.add_section("Materials & Blending")
        h_ctrl = QtWidgets.QHBoxLayout()
        btn_add = RZPushButton("Add Material")
        btn_add.clicked.connect(lambda: (self._call_op("add_tw_material"), self.update_ui()))
        h_ctrl.addWidget(btn_add); h_ctrl.addStretch()
        l.addLayout(h_ctrl)
        self.list = QtWidgets.QVBoxLayout()
        l.addLayout(self.list)
        from .lib.ui_helpers import ListItemManager
        self.manager = ListItemManager(self.list, self._create_item, self._update_item)

    def _create_item(self, index):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 5)
        
        # Row 1: ID, Name, Blend, Controls
        r1 = QtWidgets.QHBoxLayout(); r1.setContentsMargins(0, 0, 0, 0)
        lbl = RZLabel(f"[{index}]"); r1.addWidget(lbl)
        name = RZLineEdit(); name.setPlaceholderText("Material Name")
        name.editingFinished.connect(lambda: self.on_item_changed("materials", w.property("item_index"), "name", name.text()))
        r1.addWidget(name)
        
        cb_blend = RZComboBox(); cb_blend.addItems(["LERP", "ADD", "MULTIPLY", "OVERLAY"])
        cb_blend.currentTextChanged.connect(lambda v: self.on_item_changed("materials", w.property("item_index"), "diffuse_blend_mode", v))
        r1.addWidget(cb_blend)
        
        r1.addStretch()
        self.add_move_controls(w, r1, "materials")
        btn_rem = RZPushButton("×"); btn_rem.setFixedWidth(25)
        btn_rem.clicked.connect(lambda: (self._call_op("remove_tw_material", index=w.property("item_index")), self.update_ui()))
        r1.addWidget(btn_rem)
        v.addLayout(r1)
        
        # Row 2: Parameters
        r2 = QtWidgets.QHBoxLayout(); r2.setContentsMargins(20, 0, 0, 0)
        r2.addWidget(RZLabel("Params:"))
        h_params = QtWidgets.QHBoxLayout()
        param_spins = []
        for i in range(4):
            spin = RZDoubleSpinBox(); spin.setRange(-100.0, 100.0)
            spin.setFixedWidth(60)
            spin.valueChanged.connect(lambda v, i=i: self.on_item_changed("materials", w.property("item_index"), f"parameters[{i}]", str(v)))
            h_params.addWidget(spin)
            param_spins.append(spin)
        r2.addLayout(h_params)
        r2.addStretch()
        v.addLayout(r2)
        
        line = QtWidgets.QFrame(); line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setStyleSheet("background-color: #3e4451; margin-top: 4px;")
        v.addWidget(line)

        w.refs = {'lbl': lbl, 'name': name, 'blend': cb_blend, 'param_spins': param_spins}
        return w

    def _update_item(self, w, item, index, parent_index=-1):
        w.setProperty("item_index", index)
        r = w.refs
        r['lbl'].setText(f"[{index}]")
        if r['name'].text() != item.name: r['name'].setText(item.name)
        if r['blend'].currentText() != item.diffuse_blend_mode:
            r['blend'].blockSignals(True); r['blend'].setCurrentText(item.diffuse_blend_mode); r['blend'].blockSignals(False)
        for i in range(4):
            spin = r['param_spins'][i]
            if abs(spin.value() - item.parameters[i]) > 0.001:
                spin.blockSignals(True); spin.setValue(item.parameters[i]); spin.blockSignals(False)

    def update_ui(self):
        self._block = True
        if not bpy.context or not bpy.context.scene: return
        self.manager.sync(bpy.context.scene.rzm.tw_materials)
        self._block = False

    def on_item_changed(self, coll, index, prop, val):
        if self._block: return
        self._call_op("update_tw_item", collection_name=coll, index=index, prop_name=prop, value_str=val)

class TexWorksMainTab(BaseConfigTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        l = self.add_section("Main Render Stack")
        btn = RZPushButton("Add Output Block")
        btn.clicked.connect(lambda: (self._call_op("add_tw_block"), self.update_ui()))
        l.addWidget(btn)
        self.list = QtWidgets.QVBoxLayout()
        self.list.setSpacing(10)
        l.addLayout(self.list)
        from .lib.ui_helpers import ListItemManager
        self.block_manager = ListItemManager(self.list, self._create_block, self._update_block)

    def _on_val(self, coll, idx, prop, val, block_index=-1, comp_index=-1, slot_index=-1):
        if self._block: return
        
        # Build kwargs dynamically
        kwargs = {
            'collection_name': coll, 
            'index': idx, 
            'prop_name': prop, 
            'value_str': str(val)
        }
        if block_index >= 0: kwargs['block_index'] = block_index
        if comp_index >= 0: kwargs['comp_index'] = comp_index
        if slot_index >= 0: kwargs['slot_index'] = slot_index
        
        # (red) Blender Bridge: Прямое обращение к данным в обход моста.
        # Вызов оператора напрямую или через непрозрачный механизм _call_op.
        self._call_op("update_tw_item", **kwargs)
        
        # Refresh UI for structure changes
        if prop in ['tw_is_expanded', 'backdrop_enabled', 'tex_morph_enabled', 'mask_enabled', 'hsv_enabled', 'multi_pass_mode', 'use_shared_textures', 'use_shared_config']:
            self.update_ui()

    # --- BLOCK ---
    def _create_block(self, index):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 0)
        box = RZGroupBox("Main Block"); v.addWidget(box)
        box.setStyleSheet("QGroupBox { border: 2px solid #5C5CFF; margin-top: 10px; }")
        vl = QtWidgets.QVBoxLayout(box); vl.setContentsMargins(5, 10, 5, 5); vl.setSpacing(2)
        
        # (yellow) TexWorks (UX/UI): Layout & Alignment разваливается. Hardcoded layout construction.
        # Header
        h = QtWidgets.QHBoxLayout(); h.setContentsMargins(0,0,0,0)
        lbl = RZLabel("[0]"); h.addWidget(lbl)
        self.add_move_controls(w, h, "blocks")
        
        name = RZLineEdit(); name.setPlaceholderText("Block Name")
        name.editingFinished.connect(lambda: self._on_val("blocks", w.property("item_index"), "name", name.text()))
        h.addWidget(name)
        
        res = RZLineEdit(); res.setPlaceholderText("Output Res")
        res.editingFinished.connect(lambda: self._on_val("blocks", w.property("item_index"), "resource_name", res.text()))
        h.addWidget(res)
        
        cb_type = RZComboBox(); cb_type.addItems(["DIFFUSE", "MATERIAL", "NORMAL"])
        cb_type.currentTextChanged.connect(lambda v: self._on_val("blocks", w.property("item_index"), "shader_type", v))
        h.addWidget(cb_type)
        
        dup = RZPushButton("Duplicate"); dup.setFixedWidth(80)
        dup.clicked.connect(lambda: (self._call_op("duplicate_tw_block", index=w.property("item_index")), self.update_ui()))
        h.addWidget(dup)
        
        rem = RZPushButton("×"); rem.setFixedWidth(25)
        rem.clicked.connect(lambda: (self._call_op("remove_tw_block", index=w.property("item_index")), self.update_ui()))
        h.addWidget(rem)
        vl.addLayout(h)
        
        # Details (Backdrop)
        hb = QtWidgets.QHBoxLayout(); hb.setContentsMargins(20, 0, 0, 0)
        b_chk = RZCheckBox("Backdrop")
        b_chk.toggled.connect(lambda v: self._on_val("blocks", w.property("item_index"), "backdrop_enabled", str(v)))
        hb.addWidget(b_chk)
        
        hb.addWidget(b_res)
        vl.addLayout(hb)

        # Shared Textures
        hs = QtWidgets.QHBoxLayout(); hs.setContentsMargins(20, 0, 0, 0)
        s_chk = RZCheckBox("Shared Textures")
        s_chk.toggled.connect(lambda v: self._on_val("blocks", w.property("item_index"), "use_shared_textures", str(v)))
        hs.addWidget(s_chk)
        
        s_block = RZLineEdit(); s_block.setPlaceholderText("Source Block")
        s_block.editingFinished.connect(lambda: self._on_val("blocks", w.property("item_index"), "shared_textures_block", s_block.text()))
        hs.addWidget(s_block)
        
        hs.addWidget(RZLabel("UV Rescale:"))
        uv_scale = RZDoubleSpinBox(); uv_scale.setRange(0.01, 10.0); uv_scale.setSingleStep(0.1); uv_scale.setFixedWidth(60)
        uv_scale.valueChanged.connect(lambda v: self._on_val("blocks", w.property("item_index"), "uv_rescale", str(v)))
        hs.addWidget(uv_scale)
        vl.addLayout(hs)
        
        # Backdrop Rect
        hrb = QtWidgets.QHBoxLayout(); hrb.setContentsMargins(20, 0, 0, 0)
        hrb.addWidget(RZLabel("Backdrop Rect:"))
        b_rect_spins = []
        for i in range(4):
            spin = RZSpinBox(); spin.setRange(0, 16384); spin.setFixedWidth(60)
            spin.valueChanged.connect(lambda v, i=i: self._on_val("blocks", w.property("item_index"), f"backdrop_rect[{i}]", str(v)))
            hrb.addWidget(spin); b_rect_spins.append(spin)
        vl.addLayout(hrb)
        
        # Components List
        cl = QtWidgets.QVBoxLayout(); vl.addLayout(cl)
        btn_c = RZPushButton("+ Component")
        # Ensure we read item_index at click time
        btn_c.clicked.connect(lambda: (self._call_op("add_tw_component", block_index=w.property("item_index")), self.update_ui()))
        vl.addWidget(btn_c)
        
        from .lib.ui_helpers import ListItemManager
        c_mgr = ListItemManager(cl, self._create_comp, self._update_comp)
        
        w.refs = {
            'lbl': lbl, 'name': name, 'res': res, 'cb_type': cb_type, 
            'b_chk': b_chk, 'b_res': b_res, 'b_rect_spins': b_rect_spins, 
            's_chk': s_chk, 's_block': s_block, 'uv_scale': uv_scale,
            'c_mgr': c_mgr
        }
        return w

    def _update_block(self, w, item, index, parent_index=-1):
        w.setProperty("item_index", index)
        r = w.refs; r['lbl'].setText(f"[{index}]")
        
        if r['name'].text() != item.name: r['name'].setText(item.name)
        if r['res'].text() != item.resource_name: r['res'].setText(item.resource_name)
        if r['cb_type'].currentText() != item.shader_type:
            r['cb_type'].blockSignals(True); r['cb_type'].setCurrentText(item.shader_type); r['cb_type'].blockSignals(False)
            
        w.refs['b_chk'].setChecked(item.backdrop_enabled)
        w.refs['b_res'].setText(item.backdrop_resource_name)
        w.refs['b_res'].setVisible(item.backdrop_enabled)
        for i, s in enumerate(w.refs['b_rect_spins']):
            s.setValue(item.backdrop_rect[i])
            s.setVisible(item.backdrop_enabled)

        w.refs['s_chk'].setChecked(item.use_shared_textures)
        w.refs['s_block'].setText(item.shared_textures_block)
        w.refs['s_block'].setVisible(item.use_shared_textures)
        w.refs['uv_scale'].setValue(item.uv_rescale)
        
        w.refs['c_mgr'].update(item.components, parent_index=index)

    # --- COMPONENT ---
    def _create_comp(self, index):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w); v.setContentsMargins(10, 0, 0, 0)
        box = RZGroupBox("Component"); v.addWidget(box)
        box.setStyleSheet("QGroupBox { border: 1.5px solid #4CAF50; margin-top: 5px; }")
        vl = QtWidgets.QVBoxLayout(box); vl.setContentsMargins(5, 8, 5, 5); vl.setSpacing(2)
        
        # Header Row
        h = QtWidgets.QHBoxLayout(); h.setContentsMargins(0, 0, 0, 0)
        exp = RZPushButton("▼"); exp.setFixedSize(20, 20)
        exp.clicked.connect(lambda: self._on_val("components", w.property("item_index"), "tw_is_expanded", str(not w.property("expanded")), block_index=w.property("block_index")))
        h.addWidget(exp)
        
        self.add_move_controls(w, h, "components", block_index=w.property("block_index"))
        
        name = RZLineEdit(); name.setPlaceholderText("Comp Name")
        name.editingFinished.connect(lambda: self._on_val("components", w.property("item_index"), "name", name.text(), block_index=w.property("block_index")))
        h.addWidget(name)
        
        base = RZLineEdit(); base.setPlaceholderText("Base Resource")
        base.editingFinished.connect(lambda: self._on_val("components", w.property("item_index"), "base_resource_name", base.text(), block_index=w.property("block_index")))
        h.addWidget(base)
        
        rem = RZPushButton("×"); rem.setFixedWidth(25)
        rem.clicked.connect(lambda: (self._call_op("remove_tw_component", block_index=w.property("block_index"), index=w.property("item_index")), self.update_ui()))
        h.addWidget(rem)
        vl.addLayout(h)
        
        # Details (Collapsible)
        details = QtWidgets.QWidget(); v_det = QtWidgets.QVBoxLayout(details); v_det.setContentsMargins(20, 0, 0, 0)
        
        # TexMorph
        hm = QtWidgets.QHBoxLayout(); hm.setContentsMargins(0, 0, 0, 0)
        m_chk = RZCheckBox("TexMorph")
        m_chk.toggled.connect(lambda v: self._on_val("components", w.property("item_index"), "tex_morph_enabled", str(v), block_index=w.property("block_index")))
        hm.addWidget(m_chk)
        m_res = RZLineEdit(); m_res.setPlaceholderText("Morph Res")
        m_res.editingFinished.connect(lambda: self._on_val("components", w.property("item_index"), "tex_morph_resource_name", m_res.text(), block_index=w.property("block_index")))
        hm.addWidget(m_res)
        m_link = RZLineEdit(); m_link.setPlaceholderText("Morph Link ($)")
        m_link.editingFinished.connect(lambda: self._on_val("components", w.property("item_index"), "tex_morph_link", m_link.text(), block_index=w.property("block_index")))
        hm.addWidget(m_link)
        v_det.addLayout(hm)
        
        # Component Technical (Rects/Mask)
        ht = QtWidgets.QHBoxLayout(); ht.setContentsMargins(0, 0, 0, 0)
        c_mask = RZCheckBox("C.Mask")
        c_mask.toggled.connect(lambda v: self._on_val("components", w.property("item_index"), "mask_enabled", str(v), block_index=w.property("block_index")))
        ht.addWidget(c_mask)
        
        ht.addWidget(RZLabel("B.Rect:"))
        base_rect_spins = []
        for i in range(4):
            spin = RZSpinBox(); spin.setRange(0, 16384); spin.setFixedWidth(50)
            spin.valueChanged.connect(lambda v, i=i: self._on_val("components", w.property("item_index"), f"base_rect[{i}]", str(v), block_index=w.property("block_index")))
            ht.addWidget(spin); base_rect_spins.append(spin)
            
        ht.addWidget(RZLabel("Rect:"))
        rect_spins = []
        for i in range(4):
            spin = RZSpinBox(); spin.setRange(0, 16384); spin.setFixedWidth(50)
            spin.valueChanged.connect(lambda v, i=i: self._on_val("components", w.property("item_index"), f"rect[{i}]", str(v), block_index=w.property("block_index")))
            ht.addWidget(spin); rect_spins.append(spin)
        v_det.addLayout(ht)

        # Shared Config
        hc = QtWidgets.QHBoxLayout(); hc.setContentsMargins(0, 0, 0, 0)
        c_shared = RZCheckBox("Shared Config")
        c_shared.toggled.connect(lambda v: self._on_val("components", w.property("item_index"), "use_shared_config", str(v), block_index=w.property("block_index")))
        hc.addWidget(c_shared)
        
        c_sh_block = RZLineEdit(); c_sh_block.setPlaceholderText("Src Block")
        c_sh_block.editingFinished.connect(lambda: self._on_val("components", w.property("item_index"), "shared_config_block", c_sh_block.text(), block_index=w.property("block_index")))
        hc.addWidget(c_sh_block)
        
        c_sh_comp = RZLineEdit(); c_sh_comp.setPlaceholderText("Src Comp")
        c_sh_comp.editingFinished.connect(lambda: self._on_val("components", w.property("item_index"), "shared_config_component", c_sh_comp.text(), block_index=w.property("block_index")))
        hc.addWidget(c_sh_comp)
        v_det.addLayout(hc)
        
        # Slots Section
        sl = QtWidgets.QVBoxLayout(); v_det.addLayout(sl)
        btn_s = RZPushButton("+ Slot")
        btn_s.clicked.connect(lambda: (self._call_op("add_tw_slot", block_index=w.property("block_index"), comp_index=w.property("item_index")), self.update_ui()))
        v_det.addWidget(btn_s)
        
        from .lib.ui_helpers import ListItemManager
        s_mgr = ListItemManager(sl, self._create_slot, self._update_slot)
        
        vl.addWidget(details)
        w.refs = {
            'exp': exp, 'name': name, 'base': base, 'details': details, 
            'm_chk': m_chk, 'm_res': m_res, 'm_link': m_link, 
            'c_mask': c_mask, 'base_rect': base_rect_spins, 'rect': rect_spins, 
            'c_shared': c_shared, 'c_sh_block': c_sh_block, 'c_sh_comp': c_sh_comp,
            's_mgr': s_mgr
        }
        return w

    def _update_comp(self, w, item, index, parent_index=-1):
        w.setProperty("item_index", index)
        w.setProperty("block_index", parent_index) # Critical for children
        w.setProperty("expanded", item.tw_is_expanded)
        
        r = w.refs
        r['exp'].setText("▼" if item.tw_is_expanded else "▶")
        r['details'].setVisible(item.tw_is_expanded)
        
        if r['name'].text() != item.name: r['name'].setText(item.name)
        if r['base'].text() != item.base_resource_name: r['base'].setText(item.base_resource_name)
        
        r['m_chk'].setChecked(item.tex_morph_enabled)
        r['m_res'].setVisible(item.tex_morph_enabled); r['m_link'].setVisible(item.tex_morph_enabled)
        r['m_res'].setText(item.tex_morph_resource_name); r['m_link'].setText(item.tex_morph_link)
        
        r['c_mask'].setChecked(item.mask_enabled)
        
        for i in range(4):
            if r['base_rect'][i].value() != item.base_rect[i]: r['base_rect'][i].setValue(item.base_rect[i])
        for i in range(4):
            if r['rect'][i].value() != item.rect[i]: r['rect'][i].setValue(item.rect[i])

        r['c_shared'].setChecked(item.use_shared_config)
        r['c_sh_block'].setText(item.shared_config_block); r['c_sh_block'].setVisible(item.use_shared_config)
        r['c_sh_comp'].setText(item.shared_config_component); r['c_sh_comp'].setVisible(item.use_shared_config)
            
        r['s_mgr'].update(item.slots, block_index=parent_index, comp_index=index)

    # --- SLOT ---
    def _create_slot(self, index):
        w = QtWidgets.QWidget(); v = QtWidgets.QVBoxLayout(w); v.setContentsMargins(10, 0, 0, 0)
        box = RZGroupBox("Slot"); v.addWidget(box)
        box.setStyleSheet("QGroupBox { border: 1px dashed #FF9800; margin-top: 3px; }")
        vl = QtWidgets.QVBoxLayout(box); vl.setContentsMargins(5, 5, 5, 5); vl.setSpacing(2)
        
        h = QtWidgets.QHBoxLayout(); h.setContentsMargins(0,0,0,0)
        lbl = RZLabel("[0]"); h.addWidget(lbl)
        
        # Parent indices set dynamically during update, read dynamically during action
        self.add_move_controls(w, h, "slots", block_index=w.property("block_index"), comp_index=w.property("comp_index"))
        
        name = RZLineEdit(); name.setPlaceholderText("Slot Name")
        name.editingFinished.connect(lambda: self._on_val("slots", w.property("item_index"), "name", name.text(), block_index=w.property("block_index"), comp_index=w.property("comp_index")))
        h.addWidget(name)
        
        rem = RZPushButton("×"); rem.setFixedWidth(25)
        rem.clicked.connect(lambda: (self._call_op("remove_tw_slot", block_index=w.property("block_index"), comp_index=w.property("comp_index"), index=w.property("item_index")), self.update_ui()))
        h.addWidget(rem)
        vl.addLayout(h)
        
        # Technical Rect Row
        hr = QtWidgets.QHBoxLayout(); hr.setContentsMargins(20, 0, 0, 0)
        
        # Rect
        hr.addWidget(RZLabel("Rect:"))
        rect_spins = []
        for i in range(4):
            spin = RZSpinBox(); spin.setRange(0, 16384); spin.setFixedWidth(45)
            spin.valueChanged.connect(lambda v, i=i: self._on_val("slots", w.property("item_index"), f"rect[{i}]", str(v), block_index=w.property("block_index"), comp_index=w.property("comp_index")))
            hr.addWidget(spin)
            rect_spins.append(spin)

        hr.addWidget(RZLabel("Rot/Dum:")); 
        rot = RZSpinBox(); rot.setRange(0, 360); rot.setFixedWidth(50)
        rot.valueChanged.connect(lambda v: self._on_val("slots", w.property("item_index"), "rotation", str(v), block_index=w.property("block_index"), comp_index=w.property("comp_index")))
        hr.addWidget(rot)
        
        dummy = RZSpinBox(); dummy.setRange(0, 100); dummy.setFixedWidth(40); dummy.setToolTip("Dummy Value")
        dummy.valueChanged.connect(lambda v: self._on_val("slots", w.property("item_index"), "dummy", str(v), block_index=w.property("block_index"), comp_index=w.property("comp_index")))
        hr.addWidget(dummy)
        
        mir = RZCheckBox("M"); mir.toggled.connect(lambda v: self._on_val("slots", w.property("item_index"), "mirror", str(v), block_index=w.property("block_index"), comp_index=w.property("comp_index")))
        hr.addWidget(mir)
        
        flp = RZCheckBox("F"); flp.toggled.connect(lambda v: self._on_val("slots", w.property("item_index"), "flip", str(v), block_index=w.property("block_index"), comp_index=w.property("comp_index")))
        hr.addWidget(flp)
        vl.addLayout(hr)
        
        # Masking Layout
        hmk = QtWidgets.QHBoxLayout(); hmk.setContentsMargins(20, 0, 0, 0)
        m_chk = RZCheckBox("Use Mask")
        m_chk.toggled.connect(lambda v: self._on_val("slots", w.property("item_index"), "mask_enabled", str(v), block_index=w.property("block_index"), comp_index=w.property("comp_index")))
        hmk.addWidget(m_chk)
        
        m_src = RZComboBox(); m_src.addItems(['TEXTURE_ALPHA', 'SEPARATE_MASK', 'CHANNEL_R', 'CHANNEL_G', 'CHANNEL_B'])
        m_src.currentTextChanged.connect(lambda v: self._on_val("slots", w.property("item_index"), "mask_source", v, block_index=w.property("block_index"), comp_index=w.property("comp_index")))
        hmk.addWidget(m_src)
        
        p0 = RZCheckBox("P0"); p0.toggled.connect(lambda v: self._on_val("slots", w.property("item_index"), "pass0_use_mask", str(v), block_index=w.property("block_index"), comp_index=w.property("comp_index")))
        hmk.addWidget(p0)
        
        p1 = RZCheckBox("P1"); p1.toggled.connect(lambda v: self._on_val("slots", w.property("item_index"), "pass1_use_mask", str(v), block_index=w.property("block_index"), comp_index=w.property("comp_index")))
        hmk.addWidget(p1)
        vl.addLayout(hmk)

        # Multi-Pass Layout
        hmp = QtWidgets.QHBoxLayout(); hmp.setContentsMargins(20, 0, 0, 0)
        mp_m = RZComboBox(); mp_m.addItems(['NONE', 'DUPLICATE', 'INDIVIDUAL'])
        mp_m.currentTextChanged.connect(lambda v: self._on_val("slots", w.property("item_index"), "multi_pass_mode", v, block_index=w.property("block_index"), comp_index=w.property("comp_index")))
        hmp.addWidget(RZLabel("Pass:")); hmp.addWidget(mp_m)
        vl.addLayout(hmp)

        # Pass Details (Conditional)
        pass_det = QtWidgets.QWidget(); v_pass = QtWidgets.QVBoxLayout(pass_det); v_pass.setContentsMargins(20, 0, 0, 0); v_pass.setSpacing(1)
        
        hpr = QtWidgets.QHBoxLayout(); hpr.setContentsMargins(0, 0, 0, 0)
        hpr.addWidget(RZLabel("P.Rect:"))
        p_rect_spins = []
        for i in range(4):
            spin = RZSpinBox(); spin.setRange(0, 16384); spin.setFixedWidth(45)
            spin.valueChanged.connect(lambda v, i=i: self._on_val("slots", w.property("item_index"), f"multi_pass_rect[{i}]", str(v), block_index=w.property("block_index"), comp_index=w.property("comp_index")))
            hpr.addWidget(spin); p_rect_spins.append(spin)
            
        hpr.addWidget(RZLabel("R/D:")); 
        p_rot = RZSpinBox(); p_rot.setRange(0, 360); p_rot.setFixedWidth(50)
        p_rot.valueChanged.connect(lambda v: self._on_val("slots", w.property("item_index"), "multi_pass_rotation", str(v), block_index=w.property("block_index"), comp_index=w.property("comp_index")))
        hpr.addWidget(p_rot)
        
        p_dum = RZSpinBox(); p_dum.setRange(0, 100); p_dum.setFixedWidth(40)
        p_dum.valueChanged.connect(lambda v: self._on_val("slots", w.property("item_index"), "multi_pass_dummy", str(v), block_index=w.property("block_index"), comp_index=w.property("comp_index")))
        hpr.addWidget(p_dum)

        p_mir = RZCheckBox("M"); p_mir.toggled.connect(lambda v: self._on_val("slots", w.property("item_index"), "multi_pass_mirror", str(v), block_index=w.property("block_index"), comp_index=w.property("comp_index")))
        hpr.addWidget(p_mir)
        
        p_flp = RZCheckBox("F"); p_flp.toggled.connect(lambda v: self._on_val("slots", w.property("item_index"), "multi_pass_flip", str(v), block_index=w.property("block_index"), comp_index=w.property("comp_index")))
        hpr.addWidget(p_flp)
        v_pass.addLayout(hpr)
        
        vl.addWidget(pass_det)
        
        # HSV Layout
        hsv_h = QtWidgets.QHBoxLayout(); hsv_h.setContentsMargins(20, 0, 0, 0)
        hsv_chk = RZCheckBox("HSV")
        hsv_chk.toggled.connect(lambda v: self._on_val("slots", w.property("item_index"), "hsv_enabled", str(v), block_index=w.property("block_index"), comp_index=w.property("comp_index")))
        hsv_h.addWidget(hsv_chk)
        
        hsv_m_chk = RZCheckBox("Use HSV Mask")
        hsv_m_chk.toggled.connect(lambda v: self._on_val("slots", w.property("item_index"), "hsv_mask_enabled", str(v), block_index=w.property("block_index"), comp_index=w.property("comp_index")))
        hsv_h.addWidget(hsv_m_chk)
        
        hsv_link = RZLineEdit(); hsv_link.setPlaceholderText("HSV Variable ($)")
        hsv_link.editingFinished.connect(lambda: self._on_val("slots", w.property("item_index"), "hsv_link", hsv_link.text(), block_index=w.property("block_index"), comp_index=w.property("comp_index")))
        hsv_h.addWidget(hsv_link)
        vl.addLayout(hsv_h)
        
        # HSV Base
        hsv_b = QtWidgets.QHBoxLayout(); hsv_b.setContentsMargins(40, 0, 0, 0)
        hsv_b.addWidget(RZLabel("HSV Base:"))
        hsv_base_spins = []
        for i in range(4):
            spin = RZDoubleSpinBox(); spin.setRange(-10.0, 10.0); spin.setFixedWidth(50)
            spin.valueChanged.connect(lambda v, i=i: self._on_val("slots", w.property("item_index"), f"hsv_base[{i}]", str(v), block_index=w.property("block_index"), comp_index=w.property("comp_index")))
            hsv_b.addWidget(spin); hsv_base_spins.append(spin)
        vl.addLayout(hsv_b)
        
        # Layers List
        ll = QtWidgets.QVBoxLayout(); vl.addLayout(ll)
        btn_l = RZPushButton("+ Layer")
        btn_l.clicked.connect(lambda: (self._call_op("add_tw_decal_layer", block_index=w.property("block_index"), comp_index=w.property("comp_index"), slot_index=w.property("item_index")), self.update_ui()))
        vl.addWidget(btn_l)
        
        from .lib.ui_helpers import ListItemManager
        # (black) TEXWORKS Редактор слоев: Модуль "мертв". Decal Layers logic might be broken in ListItemManager or sync.
        l_mgr = ListItemManager(ll, self._create_layer, self._update_layer)

        
        w.refs = {'lbl': lbl, 'name': name, 'rect_spins': rect_spins, 'rot': rot, 'dummy': dummy, 'mir': mir, 'flp': flp, 
                  'm_chk': m_chk, 'm_src': m_src, 'p0': p0, 'p1': p1, 'mp_m': mp_m, 'pass_det': pass_det, 'p_rect': p_rect_spins,
                  'p_rot': p_rot, 'p_dum': p_dum, 'p_mir': p_mir, 'p_flp': p_flp,
                  'hsv_chk': hsv_chk, 'hsv_m_chk': hsv_m_chk, 'hsv_link': hsv_link, 'hsv_base': hsv_base_spins, 'l_mgr': l_mgr}
        return w

    def _update_slot(self, w, item, index, parent_index=-1):
        # We need to find block_index. The component (w.parent().parent()...) has it.
        # But easier: Component Widget passed it down if we traverse widget tree or ListItemManager logic supports context.
        # RZ approach: The parent_index passed here is 'comp_index'. 
        # We must find block_index from the container's property if set, or we rely on the widget property persisting.
        
        # (red) Hardcoding vs Framework: Fragile parent traversal. 
        # Если иерархия виджетов изменится (например добавлен Layout wrapper), цикл сломается.
        # Strategy: Walk up to find the Component Widget
        p = w.parent()
        b_idx = -1
        while p:
            # The Component widget sets property "block_index"
            if p.property("block_index") is not None: 
                b_idx = p.property("block_index")
                break
            p = p.parent()
            
        w.setProperty("item_index", index)
        w.setProperty("comp_index", parent_index)
        w.setProperty("block_index", b_idx)

        
        r = w.refs; r['lbl'].setText(f"[{index}]")
        
        if r['name'].text() != item.name: r['name'].setText(item.name)
        
        for i in range(4):
            if r['rect_spins'][i].value() != item.rect[i]: r['rect_spins'][i].setValue(item.rect[i])
            if r['p_rect'][i].value() != item.multi_pass_rect[i]: r['p_rect'][i].setValue(item.multi_pass_rect[i])
            if abs(r['hsv_base'][i].value() - item.hsv_base[i]) > 0.001: r['hsv_base'][i].setValue(item.hsv_base[i])
            
        r['rot'].setValue(item.rotation); r['dummy'].setValue(item.dummy)
        r['mir'].setChecked(item.mirror); r['flp'].setChecked(item.flip)
        
        r['m_chk'].setChecked(item.mask_enabled)
        r['m_src'].setCurrentText(item.mask_source)
        r['p0'].setChecked(item.pass0_use_mask); r['p1'].setChecked(item.pass1_use_mask)
        
        r['mp_m'].setCurrentText(item.multi_pass_mode)
        r['pass_det'].setVisible(item.multi_pass_mode != 'NONE')
        
        r['p_rot'].setValue(item.multi_pass_rotation)
        r['p_dum'].setValue(item.multi_pass_dummy)
        r['p_mir'].setChecked(item.multi_pass_mirror); r['p_flp'].setChecked(item.multi_pass_flip)
        
        r['hsv_chk'].setChecked(item.hsv_enabled)
        r['hsv_m_chk'].setChecked(item.hsv_mask_enabled)
        r['hsv_link'].setVisible(item.hsv_enabled); r['hsv_link'].setText(item.hsv_link)
        r['hsv_base'][0].parentWidget().setVisible(item.hsv_enabled)
        
        r['l_mgr'].sync(item.decal_layers, parent_index=index)

    # --- LAYER ---
    def _create_layer(self, index):
        w = QtWidgets.QWidget(); row = QtWidgets.QHBoxLayout(w); row.setContentsMargins(5, 0, 0, 0)
        lbl = RZLabel("[0]"); row.addWidget(lbl)
        
        self.add_move_controls(w, row, "decal_layers", 
                         block_index=w.property("block_index"), comp_index=w.property("comp_index"), slot_index=w.property("parent_index"))
        
        name = RZLineEdit(); name.setPlaceholderText("Layer Name")
        name.editingFinished.connect(lambda: self._on_val("decal_layers", w.property("item_index"), "name", name.text(),
                                   block_index=w.property("block_index"), comp_index=w.property("comp_index"), slot_index=w.property("parent_index")))
        row.addWidget(name)
        
        cnt = RZSpinBox(); cnt.setRange(1, 128); cnt.setFixedWidth(50)
        cnt.valueChanged.connect(lambda: self._on_val("decal_layers", w.property("item_index"), "count", str(cnt.value()),
                                   block_index=w.property("block_index"), comp_index=w.property("comp_index"), slot_index=w.property("parent_index")))
        row.addWidget(cnt)
        
        act = RZCheckBox(""); act.setToolTip("Active")
        act.toggled.connect(lambda v: self._on_val("decal_layers", w.property("item_index"), "active", str(v),
                                   block_index=w.property("block_index"), comp_index=w.property("comp_index"), slot_index=w.property("parent_index")))
        row.addWidget(act)

        rem = RZPushButton("×"); rem.setFixedWidth(25)
        rem.clicked.connect(lambda: (self._call_op("remove_tw_decal_layer", block_index=w.property("block_index"),
                                   comp_index=w.property("comp_index"), slot_index=w.property("parent_index"), index=w.property("item_index")), self.update_ui()))
        row.addWidget(rem)
        w.refs = {'lbl': lbl, 'name': name, 'cnt': cnt, 'act': act}
        return w

    def _update_layer(self, w, item, index, parent_index=-1):
        # Find ancestors similar to Slot, but deeper
        p = w.parent()
        b_idx = -1; c_idx = -1
        while p:
            if b_idx == -1 and p.property("block_index") is not None: b_idx = p.property("block_index")
            if c_idx == -1 and p.property("comp_index") is not None: c_idx = p.property("comp_index")
            if b_idx != -1 and c_idx != -1: break
            p = p.parent()
        
        # (red) Hardcoding vs Framework: Fragile parent traversal (Copy-Paste Logic).
        # Similar issue as in _update_slot. Breaks if hierarchy changes.
            
        w.setProperty("item_index", index)
        w.setProperty("parent_index", parent_index) # This is slot index
        w.setProperty("block_index", b_idx)
        w.setProperty("comp_index", c_idx)
        
        r = w.refs; r['lbl'].setText(f"[{index}]")
        if r['name'].text() != item.name: r['name'].setText(item.name)
        r['cnt'].setValue(item.count)
        r['act'].setChecked(item.active)

    def update_ui(self):
        self._block = True
        if not bpy.context or not bpy.context.scene: return
        try:
            self.block_manager.sync(bpy.context.scene.rzm.tw_blocks)
        except Exception as e:
            print(f"Error syncing TexWorks blocks: {e}")
        self._block = False