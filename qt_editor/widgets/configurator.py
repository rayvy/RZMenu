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
        # Placeholder for full implementation
        l_main = self.add_section("TexWorks Configuration")
        l_main.addWidget(RZLabel("Common Settings (Placeholder)"))
        
        h_common = QtWidgets.QHBoxLayout()
        h_common.addWidget(RZLabel("Format:"))
        self.cb_fmt = RZComboBox()
        self.cb_fmt.addItems(["DXGI_FORMAT_R8G8B8A8_TYPELESS", "DXGI_FORMAT_BC7_UNORM", "DXGI_FORMAT_B8G8R8A8_UNORM"])
        h_common.addWidget(self.cb_fmt)
        l_main.addLayout(h_common)
        
        self.add_section("Resources & Overrides")
        self.scroll_layout.addWidget(RZLabel("List of resources will appear here."))
        
        self.scroll_layout.addStretch()

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
        
