# RZMenu/qt_editor/widgets/configurator.py
from PySide6 import QtWidgets, QtCore, QtGui
from .lib.widgets import (
    RZGroupBox, RZPushButton, RZLabel, RZLineEdit, 
    RZComboBox, RZCheckBox, RZSpinBox, RZDoubleSpinBox
)
from .lib.theme import get_current_theme
from .lib.inputs import RZFormulaInput, RZCodeTextEdit, RZIniHighlighter
import bpy
from ..core.signals import SIGNALS

class BaseConfigTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.layout.addWidget(self.scroll_area)
        
        self.content = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout(self.content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_area.setWidget(self.content)

        self._block = False

    def add_section(self, title):
        grp = RZGroupBox(title)
        vbox = QtWidgets.QVBoxLayout(grp)
        vbox.setSpacing(5)
        self.scroll_layout.addWidget(grp)
        return vbox

    def update_ui(self):
        # Override in subclasses
        pass
        
    def _call_op(self, op_id, **kwargs):
        if self._block: return
        # Execute operator safely
        try:
            op = getattr(bpy.ops.rzm, op_id)
            op(**kwargs)
        except Exception as e:
            print(f"Error calling {op_id}: {e}")

    def add_move_controls(self, widget, layout, coll_name, **hierarchy):
        """Adds Up/Down buttons to a layout for reshuffling. Uses widget's item_index property."""
        h_ctrl = QtWidgets.QHBoxLayout()
        btn_up = RZPushButton("↑"); btn_up.setFixedWidth(25)
        btn_up.clicked.connect(lambda: self._call_op("move_tw_item", collection_name=coll_name, 
                                                     index=widget.property("item_index"), direction='UP', **hierarchy))
        
        btn_down = RZPushButton("↓"); btn_down.setFixedWidth(25)
        btn_down.clicked.connect(lambda: self._call_op("move_tw_item", collection_name=coll_name, 
                                                       index=widget.property("item_index"), direction='DOWN', **hierarchy))
        h_ctrl.addWidget(btn_up); h_ctrl.addWidget(btn_down)
        layout.addLayout(h_ctrl)

class GeneralTab(BaseConfigTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        
    def _init_ui(self):
        # --- Project Settings ---
        l_proj = self.add_section("Project Settings")
        
        # Mod Name
        h_mod = QtWidgets.QHBoxLayout()
        h_mod.addWidget(RZLabel("Mod Name:"))
        self.inp_mod_name = RZLineEdit()
        self.inp_mod_name.editingFinished.connect(self.on_mod_name_changed)
        h_mod.addWidget(self.inp_mod_name)
        l_proj.addLayout(h_mod)
        
        # Canvas Size
        h_canvas = QtWidgets.QHBoxLayout()
        h_canvas.addWidget(RZLabel("Canvas:"))
        self.spin_w = RZSpinBox()
        self.spin_w.setRange(0, 8192)
        self.spin_w.valueChanged.connect(lambda v: self.on_canvas_changed(0, v))
        self.spin_h = RZSpinBox()
        self.spin_h.setRange(0, 8192)
        self.spin_h.valueChanged.connect(lambda v: self.on_canvas_changed(1, v))
        h_canvas.addWidget(self.spin_w)
        h_canvas.addWidget(RZLabel("x"))
        h_canvas.addWidget(self.spin_h)
        l_proj.addLayout(h_canvas)

        # --- Addons ---
        l_addons = self.add_section("Addons")
        
        self.chk_debug = RZCheckBox("Enable Debugger Info")
        self.chk_debug.toggled.connect(lambda v: self.on_addon_toggled("debugger_info", v))
        l_addons.addWidget(self.chk_debug)

        self.chk_facetexworkspreseted = RZCheckBox("Enable Face Makeup ")
        self.chk_facetexworkspreseted.toggled.connect(lambda v: self.on_addon_toggled("facetexworkspreseted", v))
        l_addons.addWidget(self.chk_facetexworkspreseted)
        
        self.chk_vfx = RZCheckBox("Enable VFX")
        self.chk_vfx.toggled.connect(lambda v: self.on_addon_toggled("vfx", v))
        l_addons.addWidget(self.chk_vfx)
        
        self.chk_morph = RZCheckBox("Shape Morph")
        self.chk_morph.toggled.connect(lambda v: self.on_addon_toggled("shape_morph", v))
        l_addons.addWidget(self.chk_morph)
        
        self.chk_tex = RZCheckBox("TexWorks")
        self.chk_tex.toggled.connect(lambda v: self.on_addon_toggled("tex_works", v))
        l_addons.addWidget(self.chk_tex)
        
        self.scroll_layout.addStretch()

    def update_ui(self):
        self._block = True
        if not bpy.context or not bpy.context.scene: return
        rzm = bpy.context.scene.rzm
        
        # Stateful Update
        if self.inp_mod_name.text() != rzm.export_settings.mod_name:
            self.inp_mod_name.setText(rzm.export_settings.mod_name)
            
        if self.spin_w.value() != rzm.config.canvas_size[0]:
            self.spin_w.setValue(rzm.config.canvas_size[0])
            
        if self.spin_h.value() != rzm.config.canvas_size[1]:
            self.spin_h.setValue(rzm.config.canvas_size[1])
        
        addons = rzm.addons
        if self.chk_debug.isChecked() != addons.debugger_info:
            self.chk_debug.setChecked(addons.debugger_info)
            
        if self.chk_vfx.isChecked() != addons.vfx:
            self.chk_vfx.setChecked(addons.vfx)
            
        if self.chk_morph.isChecked() != addons.shape_morph:
            self.chk_morph.setChecked(addons.shape_morph)
            
        if self.chk_tex.isChecked() != addons.tex_works:
            self.chk_tex.setChecked(addons.tex_works)
            
        if self.chk_facetexworkspreseted.isChecked() != addons.facetexworkspreseted:
            self.chk_facetexworkspreseted.setChecked(addons.facetexworkspreseted)
        
        self._block = False

    def on_mod_name_changed(self):
        if self._block: return
        self._call_op("update_export_setting", prop_name="mod_name", val_str=self.inp_mod_name.text(), use_bool=False)

    def on_canvas_changed(self, idx, val):
        if self._block: return
        self._call_op("update_config_setting", prop_name="canvas_size", index=idx, val_str=str(val), is_int=True)
        
    def on_addon_toggled(self, key, val):
        if self._block: return
        self._call_op("update_addon_setting", prop_name=key, val_bool=val)


class TexWorksLegacyTab(BaseConfigTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        
    def _init_ui(self):
        from .lib.ui_helpers import ListItemManager

        # 1. Texture Resources
        self.res_layout = self._create_header_section("Texture Resources", "add_tw_resource", "remove_tw_resource")
        self.res_manager = ListItemManager(self.res_layout, self._create_res_widget, self._update_res_widget)
        
        # 2. Texture Overrides
        self.over_layout = self._create_header_section("Texture Overrides (3DMigoto)", "add_tw_override", "remove_tw_override")
        self.over_manager = ListItemManager(self.over_layout, self._create_over_widget, self._update_over_widget)
        
        # 3. Global Texture Configurations
        self.config_layout = self._create_header_section("Global Texture Configurations", "add_tw_config", "remove_tw_config")
        self.config_manager = ListItemManager(self.config_layout, self._create_cfg_widget, self._update_cfg_widget)
        
        # 4. Virtual Textures (Atlas)
        self.tex_layout = self._create_header_section("Virtual Textures (Atlas)", "add_tw_texture", "remove_tw_texture")
        self.tex_manager = ListItemManager(self.tex_layout, self._create_tex_widget, self._update_tex_widget)
        
        self.scroll_layout.addStretch()

    def _create_header_section(self, title, add_op, rem_op):
        v_box = self.add_section(title)
        
        h_ctrl = QtWidgets.QHBoxLayout()
        h_ctrl.addStretch()
        btn_add = RZPushButton("+")
        btn_add.setFixedWidth(30)
        btn_add.clicked.connect(lambda: self._call_op(add_op))
        
        btn_rem = RZPushButton("-")
        btn_rem.setFixedWidth(30)
        btn_rem.clicked.connect(lambda: self._call_op(rem_op))
        
        h_ctrl.addWidget(btn_add)
        h_ctrl.addWidget(btn_rem)
        
        v_box.insertLayout(0, h_ctrl)
        
        content = QtWidgets.QVBoxLayout()
        content.setSpacing(5)
        v_box.addLayout(content)
        return content

    # --- Widget Creators & Updaters ---

    # 1. Resources
    def _create_res_widget(self, index):
        w = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        
        lbl_idx = RZLabel(f"[{index}]")
        row.addWidget(lbl_idx)
        
        inp_res_name = RZLineEdit()
        inp_res_name.setPlaceholderText("Resource Name")
        inp_res_name.editingFinished.connect(lambda: self.on_res_name_changed(index, inp_res_name.text()))
        row.addWidget(inp_res_name)
        
        cb_type = RZComboBox()
        cb_type.addItems(["EMPTY", "ON_DISK", "VIRTUAL"])
        cb_type.currentTextChanged.connect(lambda v: self.on_res_type_changed(index, v))
        row.addWidget(cb_type)
        
        inp_path = RZLineEdit()
        inp_path.setPlaceholderText("Texture Path")
        inp_path.editingFinished.connect(lambda: self.on_res_path_changed(index, inp_path.text()))
        row.addWidget(inp_path) # Always add, toggle visibility

        # Store refs
        w.refs = {
            'lbl': lbl_idx, 'name': inp_res_name, 
            'type': cb_type, 'path': inp_path
        }
        return w

    def _update_res_widget(self, widget, res, index, parent_index=-1):
        r = widget.refs
        r['lbl'].setText(f"[{index}]")
        
        if r['name'].text() != res.tex_name:
            r['name'].setText(res.tex_name)
            
        if r['type'].currentText() != res.tex_resource_type:
            # Block signals if possible? No simple way without subclass, so check in handler
            r['type'].blockSignals(True)
            r['type'].setCurrentText(res.tex_resource_type)
            r['type'].blockSignals(False)
            
        # Path visibility
        is_disk = (res.tex_resource_type == "ON_DISK")
        r['path'].setVisible(is_disk)
        if is_disk and r['path'].text() != res.tex_path:
            r['path'].setText(res.tex_path)

        # Update handlers with new index closure?
        # WARNING: The lambda in create captures 'index' by value at creation time.
        # But if items are removed/reordered, the index passed to create MIGHT NOT MATCH logic index.
        # HOWEVER, we are rebuilding the list if count changes in ListItemManager? No, reuse widgets.
        # So we MUST update the callback inputs!
        # Since we use lambdas in create, we need a way to update the index they use, OR lookup index dynamically.
        # Dynamic lookup is safer: 
        # But 'index' is simple integer.
        # BETTER: Store index in widget property, read it in handler.
        widget.setProperty("item_index", index)

    # Handlers using dynamic index
    def _get_idx(self, widget):
        # We need to find the widget's index.
        # Or better: Standardize handlers to taking the widget and finding its index or use stored prop.
        # Let's use the layout index?
        # Simpler: In _create_, use a helper that binds to widget.
        pass

    # REVISED HANDLERS FOR DYNAMIC UPDATES
    # Lambda captures variables from scope. Updating widget.property is not enough if lambda used 'index' valid at creation.
    # Solutions:
    # 1. Reconnect signals on every update (Expensive?)
    # 2. Use a custom signal that passes the widget itself, look up index.
    # 3. Use `widget.property("item_index")` inside the lambda?
    #    lambda: self.on_res_name_changed(w.property("item_index"), w.refs['name'].text())
    
    # 2. Overrides
    def _create_over_widget(self, index):
        w = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        
        lbl = RZLabel(f"[{index}]")
        row.addWidget(lbl)
        
        inp_name = RZLineEdit()
        inp_name.editingFinished.connect(lambda: self.on_item_changed("tw_overrides", w.property("item_index"), "tex_name", inp_name.text()))
        row.addWidget(inp_name)
        
        inp_hash = RZLineEdit()
        inp_hash.setPlaceholderText("Hash")
        inp_hash.editingFinished.connect(lambda: self.on_item_changed("tw_overrides", w.property("item_index"), "tex_hash", inp_hash.text()))
        row.addWidget(inp_hash)
        
        inp_res = RZLineEdit()
        inp_res.setPlaceholderText("Resource")
        inp_res.editingFinished.connect(lambda: self.on_item_changed("tw_overrides", w.property("item_index"), "tex_resource_name", inp_res.text()))
        row.addWidget(inp_res)
        
        w.refs = {'lbl': lbl, 'name': inp_name, 'hash': inp_hash, 'res': inp_res}
        return w

    def _update_over_widget(self, widget, over, index, parent_index=-1):
        widget.setProperty("item_index", index) # Update logical index
        r = widget.refs
        r['lbl'].setText(f"[{index}]")
        
        if r['name'].text() != over.tex_name: r['name'].setText(over.tex_name)
        if r['hash'].text() != over.tex_hash: r['hash'].setText(over.tex_hash)
        if r['res'].text() != over.tex_resource_name: r['res'].setText(over.tex_resource_name)

    # 3. Configs
    def _create_cfg_widget(self, index):
        w = QtWidgets.QWidget()
        v_cfg = QtWidgets.QVBoxLayout(w)
        v_cfg.setContentsMargins(0, 0, 0, 0)
        
        # Row 1
        row1 = QtWidgets.QHBoxLayout()
        inp_name = RZLineEdit()
        inp_name.editingFinished.connect(lambda: self.on_item_changed("tw_texture_configs", w.property("item_index"), "tw_config_name", inp_name.text()))
        row1.addWidget(inp_name)
        
        cb_cs = RZComboBox()
        cb_cs.addItems(["SRGB", "Linear"])
        cb_cs.currentTextChanged.connect(lambda v: self.on_item_changed("tw_texture_configs", w.property("item_index"), "tw_color_space", v))
        row1.addWidget(cb_cs)
        v_cfg.addLayout(row1)
        
        # Row 2 (Atlas)
        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(RZLabel("Atlas:"))
        
        spin_w = RZSpinBox(); spin_w.setRange(256, 16384)
        spin_w.valueChanged.connect(lambda v: self.on_item_changed("tw_texture_configs", w.property("item_index"), "tw_atlas_settings.tw_width", str(v)))
        row2.addWidget(RZLabel("W:")); row2.addWidget(spin_w)
        
        spin_h = RZSpinBox(); spin_h.setRange(256, 16384)
        spin_h.valueChanged.connect(lambda v: self.on_item_changed("tw_texture_configs", w.property("item_index"), "tw_atlas_settings.tw_height", str(v)))
        row2.addWidget(RZLabel("H:")); row2.addWidget(spin_h)
        
        inp_fmt = RZLineEdit()
        inp_fmt.editingFinished.connect(lambda: self.on_item_changed("tw_texture_configs", w.property("item_index"), "tw_atlas_settings.tw_format", inp_fmt.text()))
        row2.addWidget(RZLabel("Fmt:")); row2.addWidget(inp_fmt)
        v_cfg.addLayout(row2)
        v_cfg.addWidget(RZLabel("-" * 20))
        
        w.refs = {'name': inp_name, 'cs': cb_cs, 'w': spin_w, 'h': spin_h, 'fmt': inp_fmt}
        return w

    def _update_cfg_widget(self, widget, cfg, index, parent_index=-1):
        widget.setProperty("item_index", index)
        r = widget.refs
        
        if r['name'].text() != cfg.tw_config_name: r['name'].setText(cfg.tw_config_name)
        if r['cs'].currentText() != cfg.tw_color_space: 
            r['cs'].blockSignals(True); r['cs'].setCurrentText(cfg.tw_color_space); r['cs'].blockSignals(False)
            
        if r['w'].value() != cfg.tw_atlas_settings.tw_width: 
            r['w'].blockSignals(True); r['w'].setValue(cfg.tw_atlas_settings.tw_width); r['w'].blockSignals(False)
        if r['h'].value() != cfg.tw_atlas_settings.tw_height: 
            r['h'].blockSignals(True); r['h'].setValue(cfg.tw_atlas_settings.tw_height); r['h'].blockSignals(False)
            
        if r['fmt'].text() != cfg.tw_atlas_settings.tw_format: r['fmt'].setText(cfg.tw_atlas_settings.tw_format)

    # 4. Textures (Virtual) - Complex
    # 4. Textures (Virtual) - Complex
    def _create_tex_widget(self, index):
        w = QtWidgets.QWidget()
        v_tex = QtWidgets.QVBoxLayout(w)
        v_tex.setContentsMargins(0, 0, 0, 0)
        
        # Header
        h_head = QtWidgets.QHBoxLayout()
        btn_exp = RZPushButton("▶")
        btn_exp.setFixedWidth(25)
        # Toggle expand logic needs the item
        btn_exp.clicked.connect(lambda: self.on_item_changed("tw_textures", w.property("item_index"), "tw_is_expanded", 
                                                             "False" if btn_exp.text() == "▼" else "True"))
        h_head.addWidget(btn_exp)
        
        inp_name = RZLineEdit()
        inp_name.editingFinished.connect(lambda: self.on_item_changed("tw_textures", w.property("item_index"), "tw_name", inp_name.text()))
        h_head.addWidget(inp_name)
        v_tex.addLayout(h_head)
        
        # Details Container
        details = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(details)
        grid.setContentsMargins(10, 0, 0, 0)
        
        grid.addWidget(RZLabel("Base Resource:"), 0, 0)
        inp_base = RZLineEdit()
        inp_base.editingFinished.connect(lambda: self.on_item_changed("tw_textures", w.property("item_index"), "tw_base_resource_name", inp_base.text()))
        grid.addWidget(inp_base, 0, 1)
        
        # Pos
        h_pos = QtWidgets.QHBoxLayout()
        spin_px = RZSpinBox(); spin_px.setRange(0, 16384)
        spin_px.valueChanged.connect(lambda v: self.on_item_changed("tw_textures", w.property("item_index"), "tw_position", str(v), is_pos=True, axis=0))
        spin_py = RZSpinBox(); spin_py.setRange(0, 16384)
        spin_py.valueChanged.connect(lambda v: self.on_item_changed("tw_textures", w.property("item_index"), "tw_position", str(v), is_pos=True, axis=1))
        h_pos.addWidget(spin_px); h_pos.addWidget(spin_py)
        grid.addWidget(RZLabel("Pos:"), 1, 0); grid.addLayout(h_pos, 1, 1)

        # Size
        h_size = QtWidgets.QHBoxLayout()
        spin_sw = RZSpinBox(); spin_sw.setRange(0, 16384)
        spin_sw.valueChanged.connect(lambda v: self.on_item_changed("tw_textures", w.property("item_index"), "tw_size", str(v), is_size=True, axis=0))
        spin_sh = RZSpinBox(); spin_sh.setRange(0, 16384)
        spin_sh.valueChanged.connect(lambda v: self.on_item_changed("tw_textures", w.property("item_index"), "tw_size", str(v), is_size=True, axis=1))
        h_size.addWidget(spin_sw); h_size.addWidget(spin_sh)
        grid.addWidget(RZLabel("Size:"), 2, 0); grid.addLayout(h_size, 2, 1)
        
        v_tex.addWidget(details)
        
        # Alternatives (List within List)
        alt_grp = RZGroupBox("Alternatives")
        v_alt = QtWidgets.QVBoxLayout(alt_grp)
        
        h_alt_ctrl = QtWidgets.QHBoxLayout()
        h_alt_ctrl.addStretch()
        btn_add_alt = RZPushButton("+")
        btn_add_alt.clicked.connect(lambda: self._call_op("add_tw_alternative", texture_index=w.property("item_index")))
        btn_rem_alt = RZPushButton("-")
        btn_rem_alt.clicked.connect(lambda: self._call_op("remove_tw_alternative", texture_index=w.property("item_index")))
        h_alt_ctrl.addWidget(btn_add_alt); h_alt_ctrl.addWidget(btn_rem_alt)
        v_alt.addLayout(h_alt_ctrl)
        
        l_alts = QtWidgets.QVBoxLayout()
        v_alt.addLayout(l_alts)
        v_tex.addWidget(alt_grp)
        
        from .lib.ui_helpers import ListItemManager
        alt_manager = ListItemManager(l_alts, self._create_alt_widget, self._update_alt_widget)

        w.refs = {
            'exp': btn_exp, 'name': inp_name, 'details': details, 
            'base': inp_base, 'px': spin_px, 'py': spin_py, 'sw': spin_sw, 'sh': spin_sh,
            'alt_manager': alt_manager
        }
        return w

    def _create_alt_widget(self, index):
        w = QtWidgets.QWidget()
        row_alt = QtWidgets.QHBoxLayout(w)
        row_alt.setContentsMargins(0, 0, 0, 0)
        
        row_alt.addWidget(RZLabel("Use:"))
        inp_a_res = RZLineEdit()
        inp_a_res.editingFinished.connect(lambda: self.on_item_changed("alternatives", w.property("item_index"), "tex_resource_name", inp_a_res.text(), parent_index=w.property("parent_index")))
        row_alt.addWidget(inp_a_res)
        
        row_alt.addWidget(RZLabel("If:"))
        inp_a_cond = RZFormulaInput()
        inp_a_cond.editingFinished.connect(lambda: self.on_item_changed("alternatives", w.property("item_index"), "tex_condition", inp_a_cond.text(), parent_index=w.property("parent_index")))
        row_alt.addWidget(inp_a_cond)
        
        w.refs = {'res': inp_a_res, 'cond': inp_a_cond}
        return w
        
    def _update_alt_widget(self, widget, alt, index, parent_index=-1):
        widget.setProperty("item_index", index)
        widget.setProperty("parent_index", parent_index)
        r = widget.refs
        if r['res'].text() != alt.tex_resource_name: r['res'].setText(alt.tex_resource_name)
        if r['cond'].text() != alt.tex_condition: r['cond'].setText(alt.tex_condition)

    def _update_tex_widget(self, widget, tex, index, parent_index=-1):
        widget.setProperty("item_index", index)
        r = widget.refs
        
        # Expanded State
        exp_txt = "▼" if tex.tw_is_expanded else "▶"
        if r['exp'].text() != exp_txt: r['exp'].setText(exp_txt)
        r['details'].setVisible(tex.tw_is_expanded)
        r['alt_manager'].layout.parentWidget().setVisible(tex.tw_is_expanded)
        
        # Basic Props
        if r['name'].text() != tex.tw_name: r['name'].setText(tex.tw_name)
        if r['base'].text() != tex.tw_base_resource_name: r['base'].setText(tex.tw_base_resource_name)
        
        # Pos/Size
        for ax, s, val in [(0, 'px', 0), (1, 'py', 1)]:
             if r[s].value() != tex.tw_position[val]: 
                  r[s].blockSignals(True); r[s].setValue(tex.tw_position[val]); r[s].blockSignals(False)
        for ax, s, val in [(0, 'sw', 0), (1, 'sh', 1)]:
             if r[s].value() != tex.tw_size[val]: 
                  r[s].blockSignals(True); r[s].setValue(tex.tw_size[val]); r[s].blockSignals(False)

        # Sync Alts
        if tex.tw_is_expanded:
            r['alt_manager'].sync(tex.tw_alternatives, parent_index=index)

    def update_ui(self):
        self._block = True
        if not bpy.context or not bpy.context.scene: return
        rzm = bpy.context.scene.rzm
        addons = rzm.addons
        if not addons.tex_works: 
            self._block = False
            return
            
        # Sync Lists using Managers
        self.res_manager.sync(addons.tw_resources)
        self.over_manager.sync(addons.tw_overrides)
        self.config_manager.sync(addons.tw_texture_configs)
        self.tex_manager.sync(addons.tw_textures)

        self._block = False

    # I need to FIX the logic - Done.

    def _create_res_widget(self, index):
        w = QtWidgets.QWidget()
        w.setProperty("item_index", index) # Initialize
        row = QtWidgets.QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        
        lbl_idx = RZLabel(f"[{index}]")
        row.addWidget(lbl_idx)
        
        inp_res_name = RZLineEdit()
        inp_res_name.setPlaceholderText("Resource Name")
        inp_res_name.editingFinished.connect(lambda: self.on_item_changed("tw_resources", w.property("item_index"), "tex_name", inp_res_name.text()))
        row.addWidget(inp_res_name)
        
        cb_type = RZComboBox()
        cb_type.addItems(["EMPTY", "ON_DISK", "VIRTUAL"])
        cb_type.currentTextChanged.connect(lambda v: self.on_item_changed("tw_resources", w.property("item_index"), "tex_resource_type", v))
        row.addWidget(cb_type)
        
        inp_path = RZLineEdit()
        inp_path.setPlaceholderText("Texture Path")
        inp_path.editingFinished.connect(lambda: self.on_item_changed("tw_resources", w.property("item_index"), "tex_path", inp_path.text()))
        row.addWidget(inp_path)

        w.refs = {'lbl': lbl_idx, 'name': inp_res_name, 'type': cb_type, 'path': inp_path}
        return w

    def on_item_changed(self, coll_name, index, prop_name, val_str, parent_index=-1, is_pos=False, is_size=False, axis=0):
        if self._block: return
        actual_prop = prop_name
        if is_pos:
            actual_prop = f"tw_position[{axis}]"
        elif is_size:
            actual_prop = f"tw_size[{axis}]"
        
        self._call_op("update_tw_item", 
                  collection_name=coll_name, 
                  index=index, 
                  prop_name=actual_prop, 
                  value_str=val_str, 
                  parent_index=parent_index)
        self.update_ui()




class SnippetTab(BaseConfigTab):
    """
    Tab for editing Pre/Post Code Snippets (INI syntax).
    """
    def __init__(self, property_name="", title="", parent=None):
        super().__init__(parent)
        self.property_name = property_name # e.g. "pre_snippet"
        self.title = title
        self._init_ui()

    def _init_ui(self):
        # We want the text edit to fill the space, so we don't use the default scroll area layout from BaseConfigTab?
        # BaseConfigTab puts everything in a scroll area. For a large text edit, 
        # it's often better to have the text edit itself be the scrollable widget.
        
        # Let's bypass the base layout slightly or just clear it.
        # Base class: self.layout -> scroll_area -> content -> scroll_layout
        
        # We can just add the editor to scroll_layout, but make sure it expands?
        # Or better, hide the scroll area and add our editor directly to self.layout
        self.scroll_area.hide()
        
        # Container for editor
        container = QtWidgets.QWidget()
        l = QtWidgets.QVBoxLayout(container)
        l.setContentsMargins(0, 0, 0, 0)
        
        l.addWidget(RZLabel(f"{self.title} (INI Syntax):"))
        
        self.editor = RZCodeTextEdit()
        self.editor.set_highlighter(RZIniHighlighter)
        self.editor.editingFinished.connect(self.on_text_changed)
        
        # Ensure it expands
        self.editor.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        
        l.addWidget(self.editor)
        self.layout.addWidget(container)

    def update_ui(self):
        self._block = True
        if not bpy.context or not bpy.context.scene: return
        rzm = bpy.context.scene.rzm
        config = rzm.config
        
        # Check if property exists (user might not have added multiple lines to p_settings yet)
        if not hasattr(config, self.property_name):
            if self.editor.isEnabled():
                self.editor.setPlainText(f"Error: Property '{self.property_name}' not found in RZMenuConfig.\nPlease update p_settings.py")
                self.editor.setEnabled(False)
            return
            
        self.editor.setEnabled(True)
        val = getattr(config, self.property_name)
        if self.editor.toPlainText() != val:
            self.editor.setPlainText(val)
            
        self._block = False

    def on_text_changed(self):
        if self._block: return
        # Use generic update_config_setting op
        # Note: update_config_setting takes 'prop_name', 'val_str'
        self._call_op("update_config_setting", 
                      prop_name=self.property_name, 
                      val_str=self.editor.toPlainText(), 
                      is_int=False)


class RZConfiguratorManager(QtWidgets.QWidget):
    """
    Main widget for the Configurator Panel.
    Features a horizontal tab bar and stacked content pages.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # --- Custom Tab Bar ---
        self.tab_bar = QtWidgets.QTabBar()
        self.tab_bar.setDrawBase(False)
        self.tab_bar.setExpanding(False)
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        self.layout.addWidget(self.tab_bar)
        
        # --- Stacked Content ---
        self.stack = QtWidgets.QStackedWidget()
        self.layout.addWidget(self.stack)
        
        # --- Register Tabs ---
        self.tabs = [] # List of (Name, WidgetInstance)
        
        self.add_tab("General", GeneralTab())
        self.add_tab("TexWorks (Legacy)", TexWorksLegacyTab())
        self.add_tab("PreSnippet", SnippetTab("pre_snippet", "Pre-Injection Code"))
        self.add_tab("PostSnippet", SnippetTab("post_snippet", "Post-Injection Code"))
        # Extensible point: self.add_tab("VFX", VFXTab())
        
        self.apply_theme()
        
        # Subscribe to updates
        SIGNALS.structure_changed.connect(self.refresh_current)

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
        # Style the tab bar to look integrated
        self.tab_bar.setStyleSheet(f"""
            QTabBar::tab {{
                background: {t.get('bg_modal', t.get('bg_input', '#252930'))}; /* darker fallback */
                color: {t.get('text_dim', t.get('text_dark', '#9DA5B4'))};
                padding: 8px 16px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {t.get('bg_panel', '#2C313A')};
                color: {t.get('text_main', '#E0E2E4')};
                font-weight: bold;
            }}
            QTabBar::tab:hover {{
                color: {t.get('text_main', '#E0E2E4')};
            }}
        """)
        self.stack.setStyleSheet(f"background-color: {t.get('bg_panel', '#2C313A')};")
        
