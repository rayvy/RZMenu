# RZMenu/qt_editor/widgets/configurator.py
from PySide6 import QtWidgets, QtCore, QtGui
from .lib.widgets import (
    RZGroupBox, RZPushButton, RZLabel, RZLineEdit, 
    RZComboBox, RZCheckBox, RZSpinBox, RZDoubleSpinBox
)
from .lib.theme import get_current_theme
from .lib.inputs import RZFormulaInput
import bpy

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
        
        self.inp_mod_name.setText(rzm.export_settings.mod_name)
        self.spin_w.setValue(rzm.config.canvas_size[0])
        self.spin_h.setValue(rzm.config.canvas_size[1])
        
        addons = rzm.addons
        self.chk_debug.setChecked(addons.debugger_info)
        self.chk_vfx.setChecked(addons.vfx)
        self.chk_morph.setChecked(addons.shape_morph)
        self.chk_tex.setChecked(addons.tex_works)
        
        self._block = False

    def on_mod_name_changed(self):
        self._call_op("update_export_setting", prop_name="mod_name", val_str=self.inp_mod_name.text(), use_bool=False)

    def on_canvas_changed(self, idx, val):
        self._call_op("update_config_setting", prop_name="canvas_size", index=idx, val_str=str(val), is_int=True)
        
    def on_addon_toggled(self, key, val):
        self._call_op("update_addon_setting", prop_name=key, val_bool=val)


class TexWorksTab(BaseConfigTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        
    def _init_ui(self):
        # 1. Texture Resources
        self.res_layout = self._create_header_section("Texture Resources", "add_tw_resource", "remove_tw_resource")
        
        # 2. Texture Overrides
        self.over_layout = self._create_header_section("Texture Overrides (3DMigoto)", "add_tw_override", "remove_tw_override")
        
        # 3. Global Texture Configurations
        self.config_layout = self._create_header_section("Global Texture Configurations", "add_tw_config", "remove_tw_config")
        
        # 4. Virtual Textures (Atlas)
        self.tex_layout = self._create_header_section("Virtual Textures (Atlas)", "add_tw_texture", "remove_tw_texture")
        
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

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def update_ui(self):
        self._block = True
        if not bpy.context or not bpy.context.scene: return
        rzm = bpy.context.scene.rzm
        addons = rzm.addons
        if not addons.tex_works: 
            self._block = False
            return
            
        # 1. Texture Resources
        self._clear_layout(self.res_layout)
        for i, res in enumerate(addons.tw_resources):
            row = QtWidgets.QHBoxLayout()
            row.addWidget(RZLabel(f"[{i}]"))
            
            inp_res_name = RZLineEdit()
            inp_res_name.setPlaceholderText("Resource Name")
            inp_res_name.setText(res.tex_name)
            inp_res_name.editingFinished.connect(lambda r=res, idx=i, inp=inp_res_name: 
                self.on_item_changed("tw_resources", idx, "tex_name", inp.text()))
            row.addWidget(inp_res_name)
            
            cb_type = RZComboBox()
            cb_type.addItems(["EMPTY", "ON_DISK", "VIRTUAL"])
            cb_type.setCurrentText(res.tex_resource_type)
            cb_type.currentTextChanged.connect(lambda v, idx=i: 
                self.on_item_changed("tw_resources", idx, "tex_resource_type", v))
            row.addWidget(cb_type)
            
            if res.tex_resource_type == "ON_DISK":
                inp_path = RZLineEdit()
                inp_path.setPlaceholderText("Texture Path")
                inp_path.setText(res.tex_path)
                inp_path.editingFinished.connect(lambda r=res, idx=i, inp=inp_path: 
                    self.on_item_changed("tw_resources", idx, "tex_path", inp.text()))
                row.addWidget(inp_path)
            
            self.res_layout.addLayout(row)

        # 2. Texture Overrides
        self._clear_layout(self.over_layout)
        for i, over in enumerate(addons.tw_overrides):
            row = QtWidgets.QHBoxLayout()
            row.addWidget(RZLabel(f"[{i}]"))
            
            inp_name = RZLineEdit()
            inp_name.setText(over.tex_name)
            inp_name.editingFinished.connect(lambda idx=i, inp=inp_name: 
                self.on_item_changed("tw_overrides", idx, "tex_name", inp.text()))
            row.addWidget(inp_name)
            
            inp_hash = RZLineEdit()
            inp_hash.setPlaceholderText("Hash")
            inp_hash.setText(over.tex_hash)
            inp_hash.editingFinished.connect(lambda idx=i, inp=inp_hash: 
                self.on_item_changed("tw_overrides", idx, "tex_hash", inp.text()))
            row.addWidget(inp_hash)
            
            inp_res = RZLineEdit()
            inp_res.setPlaceholderText("Resource")
            inp_res.setText(over.tex_resource_name)
            inp_res.editingFinished.connect(lambda idx=i, inp=inp_res: 
                self.on_item_changed("tw_overrides", idx, "tex_resource_name", inp.text()))
            row.addWidget(inp_res)
            
            self.over_layout.addLayout(row)

        # 3. Global Texture Configurations
        self._clear_layout(self.config_layout)
        for i, cfg in enumerate(addons.tw_texture_configs):
            v_cfg = QtWidgets.QVBoxLayout()
            row1 = QtWidgets.QHBoxLayout()
            
            inp_name = RZLineEdit()
            inp_name.setText(cfg.tw_config_name)
            inp_name.editingFinished.connect(lambda idx=i, inp=inp_name: 
                self.on_item_changed("tw_texture_configs", idx, "tw_config_name", inp.text()))
            row1.addWidget(inp_name)
            
            cb_cs = RZComboBox()
            cb_cs.addItems(["SRGB", "Linear"])
            cb_cs.setCurrentText(cfg.tw_color_space)
            cb_cs.currentTextChanged.connect(lambda v, idx=i: 
                self.on_item_changed("tw_texture_configs", idx, "tw_color_space", v))
            row1.addWidget(cb_cs)
            v_cfg.addLayout(row1)
            
            # Atlas Settings
            row2 = QtWidgets.QHBoxLayout()
            row2.addWidget(RZLabel("Atlas:"))
            
            spin_w = RZSpinBox()
            spin_w.setRange(256, 16384)
            spin_w.setValue(cfg.tw_atlas_settings.tw_width)
            spin_w.valueChanged.connect(lambda v, idx=i: 
                self.on_item_changed("tw_texture_configs", idx, "tw_atlas_settings.tw_width", str(v)))
            row2.addWidget(RZLabel("W:"))
            row2.addWidget(spin_w)
            
            spin_h = RZSpinBox()
            spin_h.setRange(256, 16384)
            spin_h.setValue(cfg.tw_atlas_settings.tw_height)
            spin_h.valueChanged.connect(lambda v, idx=i: 
                self.on_item_changed("tw_texture_configs", idx, "tw_atlas_settings.tw_height", str(v)))
            row2.addWidget(RZLabel("H:"))
            row2.addWidget(spin_h)
            
            inp_fmt = RZLineEdit()
            inp_fmt.setText(cfg.tw_atlas_settings.tw_format)
            inp_fmt.editingFinished.connect(lambda idx=i, inp=inp_fmt: 
                self.on_item_changed("tw_texture_configs", idx, "tw_atlas_settings.tw_format", inp.text()))
            row2.addWidget(RZLabel("Fmt:"))
            row2.addWidget(inp_fmt)
            
            v_cfg.addLayout(row2)
            self.config_layout.addLayout(v_cfg)
            self.config_layout.addWidget(RZLabel("-" * 20)) # Divider

        # 4. Virtual Textures (Atlas)
        self._clear_layout(self.tex_layout)
        for i, tex in enumerate(addons.tw_textures):
            v_tex = QtWidgets.QVBoxLayout()
            
            # Header with Triangle/Expand and Name
            h_head = QtWidgets.QHBoxLayout()
            btn_exp = RZPushButton("▼" if tex.tw_is_expanded else "▶")
            btn_exp.setFixedWidth(25)
            btn_exp.clicked.connect(lambda idx=i, v=not tex.tw_is_expanded: 
                self.on_item_changed("tw_textures", idx, "tw_is_expanded", str(v)))
            h_head.addWidget(btn_exp)
            
            inp_name = RZLineEdit()
            inp_name.setText(tex.tw_name)
            inp_name.editingFinished.connect(lambda idx=i, inp=inp_name: 
                self.on_item_changed("tw_textures", idx, "tw_name", inp.text()))
            h_head.addWidget(inp_name)
            v_tex.addLayout(h_head)
            
            if tex.tw_is_expanded:
                grid = QtWidgets.QGridLayout()
                
                # Base Resource
                grid.addWidget(RZLabel("Base Resource:"), 0, 0)
                inp_base = RZLineEdit()
                inp_base.setText(tex.tw_base_resource_name)
                inp_base.editingFinished.connect(lambda idx=i, inp=inp_base: 
                    self.on_item_changed("tw_textures", idx, "tw_base_resource_name", inp.text()))
                grid.addWidget(inp_base, 0, 1)
                
                # Pos/Size
                grid.addWidget(RZLabel("Pos (X,Y):"), 1, 0)
                h_pos = QtWidgets.QHBoxLayout()
                spin_px = RZSpinBox(); spin_px.setRange(0, 16384); spin_px.setValue(tex.tw_position[0])
                spin_px.valueChanged.connect(lambda v, idx=i: self.on_item_changed("tw_textures", idx, "tw_position", str(v), is_pos=True, axis=0))
                spin_py = RZSpinBox(); spin_py.setRange(0, 16384); spin_py.setValue(tex.tw_position[1])
                spin_py.valueChanged.connect(lambda v, idx=i: self.on_item_changed("tw_textures", idx, "tw_position", str(v), is_pos=True, axis=1))
                h_pos.addWidget(spin_px); h_pos.addWidget(spin_py)
                grid.addLayout(h_pos, 1, 1)
                
                grid.addWidget(RZLabel("Size (W,H):"), 2, 0)
                h_size = QtWidgets.QHBoxLayout()
                spin_sw = RZSpinBox(); spin_sw.setRange(0, 16384); spin_sw.setValue(tex.tw_size[0])
                spin_sw.valueChanged.connect(lambda v, idx=i: self.on_item_changed("tw_textures", idx, "tw_size", str(v), is_size=True, axis=0))
                spin_sh = RZSpinBox(); spin_sh.setRange(0, 16384); spin_sh.setValue(tex.tw_size[1])
                spin_sh.valueChanged.connect(lambda v, idx=i: self.on_item_changed("tw_textures", idx, "tw_size", str(v), is_size=True, axis=1))
                h_size.addWidget(spin_sw); h_size.addWidget(spin_sh)
                grid.addLayout(h_size, 2, 1)
                
                v_tex.addLayout(grid)
                
                # Alternatives
                alt_grp = RZGroupBox("Alternatives")
                v_alt = QtWidgets.QVBoxLayout(alt_grp)
                
                h_alt_ctrl = QtWidgets.QHBoxLayout()
                h_alt_ctrl.addStretch()
                btn_add_alt = RZPushButton("+")
                btn_add_alt.clicked.connect(lambda idx=i: self._call_op("add_tw_alternative", texture_index=idx))
                btn_rem_alt = RZPushButton("-")
                btn_rem_alt.clicked.connect(lambda idx=i: self._call_op("remove_tw_alternative", texture_index=idx))
                h_alt_ctrl.addWidget(btn_add_alt); h_alt_ctrl.addWidget(btn_rem_alt)
                v_alt.addLayout(h_alt_ctrl)
                
                for j, alt in enumerate(tex.tw_alternatives):
                    row_alt = QtWidgets.QHBoxLayout()
                    row_alt.addWidget(RZLabel("Use:"))
                    inp_a_res = RZLineEdit(); inp_a_res.setText(alt.tex_resource_name)
                    inp_a_res.editingFinished.connect(lambda p_idx=i, idx=j, inp=inp_a_res: 
                        self.on_item_changed("alternatives", idx, "tex_resource_name", inp.text(), parent_index=p_idx))
                    row_alt.addWidget(inp_a_res)
                    row_alt.addWidget(RZLabel("If:"))
                    inp_a_cond = RZFormulaInput(); inp_a_cond.setText(alt.tex_condition)
                    inp_a_cond.editingFinished.connect(lambda p_idx=i, idx=j, inp=inp_a_cond: 
                        self.on_item_changed("alternatives", idx, "tex_condition", inp.text(), parent_index=p_idx))
                    row_alt.addWidget(inp_a_cond)
                    v_alt.addLayout(row_alt)
                
                v_tex.addWidget(alt_grp)
                
                # Decals
                decal_grp = RZGroupBox("Decals")
                v_dec = QtWidgets.QVBoxLayout(decal_grp)
                chk_tat = RZCheckBox("Use Tattoo Decal", checked=tex.tw_use_decal_tattoo)
                chk_tat.toggled.connect(lambda v, idx=i: self.on_item_changed("tw_textures", idx, "tw_use_decal_tattoo", str(v)))
                v_dec.addWidget(chk_tat)
                chk_der = RZCheckBox("Use Derma Decal", checked=tex.tw_use_decal_derma)
                chk_der.toggled.connect(lambda v, idx=i: self.on_item_changed("tw_textures", idx, "tw_use_decal_derma", str(v)))
                v_dec.addWidget(chk_der)
                chk_flu = RZCheckBox("Use Fluid Decal", checked=tex.tw_use_decal_fluid)
                chk_flu.toggled.connect(lambda v, idx=i: self.on_item_changed("tw_textures", idx, "tw_use_decal_fluid", str(v)))
                v_dec.addWidget(chk_flu)
                v_tex.addWidget(decal_grp)
                
                # HSV / Morph
                row_hsv = RZCheckBox("Use HSV", checked=tex.tw_use_hsv)
                row_hsv.toggled.connect(lambda v, idx=i: self.on_item_changed("tw_textures", idx, "tw_use_hsv", str(v)))
                v_tex.addWidget(row_hsv)
                if tex.tw_use_hsv:
                    h_hsv = QtWidgets.QHBoxLayout()
                    h_hsv.addWidget(RZLabel("Mode:"))
                    cb_hsv_m = RZComboBox(); cb_hsv_m.addItems(["UNMASKED", "MASKED"]); cb_hsv_m.setCurrentText(tex.tw_hsv_mode)
                    cb_hsv_m.currentTextChanged.connect(lambda v, idx=i: self.on_item_changed("tw_textures", idx, "tw_hsv_mode", v))
                    h_hsv.addWidget(cb_hsv_m)
                    
                    h_hsv.addWidget(RZLabel("Link:"))
                    inp_hsv_link = RZFormulaInput(); inp_hsv_link.setText(tex.tw_hsv_value_link)
                    inp_hsv_link.editingFinished.connect(lambda idx=i, inp=inp_hsv_link: 
                        self.on_item_changed("tw_textures", idx, "tw_hsv_value_link", inp.text()))
                    h_hsv.addWidget(inp_hsv_link)
                    v_tex.addLayout(h_hsv)
                
                row_morph = RZCheckBox("Use Morph", checked=tex.tw_use_morph)
                row_morph.toggled.connect(lambda v, idx=i: self.on_item_changed("tw_textures", idx, "tw_use_morph", str(v)))
                v_tex.addWidget(row_morph)
                if tex.tw_use_morph:
                    h_morph = QtWidgets.QHBoxLayout()
                    h_morph.addWidget(RZLabel("Target:"))
                    inp_m_target = RZLineEdit(); inp_m_target.setText(tex.tw_morph_target_name)
                    inp_m_target.editingFinished.connect(lambda idx=i, inp=inp_m_target: 
                        self.on_item_changed("tw_textures", idx, "tw_morph_target_name", inp.text()))
                    h_morph.addWidget(inp_m_target)
                    
                    h_morph.addWidget(RZLabel("Link:"))
                    inp_morph_link = RZFormulaInput(); inp_morph_link.setText(tex.tw_morph_value_link)
                    inp_morph_link.editingFinished.connect(lambda idx=i, inp=inp_morph_link: 
                        self.on_item_changed("tw_textures", idx, "tw_morph_value_link", inp.text()))
                    h_morph.addWidget(inp_morph_link)
                    v_tex.addLayout(h_morph)

            self.tex_layout.addLayout(v_tex)
            self.tex_layout.addWidget(RZLabel("=" * 30))

        self._block = False

    def on_item_changed(self, coll_name, index, prop_name, val_str, parent_index=-1, is_pos=False, is_size=False, axis=0):
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
        self.update_ui() # Refresh to show changes (like Expand triangle)

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
        self.add_tab("TexWorks", TexWorksTab())
        # Extensible point: self.add_tab("VFX", VFXTab())
        
        self.apply_theme()

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
        
