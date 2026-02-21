# RZMenu/qt_editor/widgets/configurator.py
from PySide6 import QtWidgets, QtCore, QtGui
from .lib.widgets import (
    RZGroupBox, RZPushButton, RZLabel, RZLineEdit, 
    RZComboBox, RZCheckBox, RZSpinBox, RZDoubleSpinBox
)
from .lib.theme import get_current_theme
from .lib.inputs import RZFormulaInput, RZCodeTextEdit, RZIniHighlighter, RZModInfoTextEdit
import bpy
from ..core import read as core_read
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

class ModInfoTab(BaseConfigTab):
    """
    Substantial tab for Mod Info and Metadata.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        # --- 1. Base Metadata ---
        l_base = self.add_section("Identity & Version")
        
        self.inp_char = self._add_field(l_base, "Character:", "character_name")
        self.inp_outfit = self._add_field(l_base, "Outfit:", "outfit_name")
        self.inp_ver = self._add_field(l_base, "Version:", "version_num")
        self.inp_author = self._add_field(l_base, "Author:", "author_name")

        # --- 2. релизная инфа ---
        l_release = self.add_section("Release Info")
        
        h_tier = QtWidgets.QHBoxLayout()
        h_tier.addWidget(RZLabel("Tier:"))
        self.combo_tier = RZComboBox()
        self.combo_tier.addItems(["PUBLIC", "TIER_1", "TIER_2", "SPICED", "WIP"])
        self.combo_tier.currentTextChanged.connect(lambda v: self._on_meta_changed("patreon_tier", v))
        h_tier.addWidget(self.combo_tier)
        l_release.addLayout(h_tier)

        self.chk_nsfw = RZCheckBox("NSFW Content")
        self.chk_nsfw.toggled.connect(lambda v: self._on_meta_changed("is_nsfw", v, bool_mode=True))
        l_release.addWidget(self.chk_nsfw)

        # --- 3. Техничка ---
        l_tech = self.add_section("Technical")
        self.inp_key = self._add_field(l_tech, "Keybind:", "menu_keybind")
        self.inp_req = self._add_field(l_tech, "Requirements:", "requirements")
        self.inp_respect = self._add_field(l_tech, "Credits To:", "community_respect")

        # --- 4. Main Mod Info Text ---
        l_desc = self.add_section("Mod Info Template (Exported)")
        
        self.editor = RZModInfoTextEdit()
        self.editor.editingFinished.connect(self.on_mod_info_finished)
        l_desc.addWidget(self.editor)

    def _add_field(self, layout, label, prop_name):
        h = QtWidgets.QHBoxLayout()
        h.addWidget(RZLabel(label))
        inp = RZLineEdit()
        inp.editingFinished.connect(lambda: self._on_meta_changed(prop_name, inp.text()))
        h.addWidget(inp)
        layout.addLayout(h)
        return inp

    def update_ui(self):
        self._block = True
        if not bpy.context or not bpy.context.scene: return
        meta = bpy.context.scene.rzm.meta_data
        config = bpy.context.scene.rzm.config

        # Update text fields
        self.inp_char.setText(meta.character_name)
        self.inp_outfit.setText(meta.outfit_name)
        self.inp_ver.setText(meta.version_num)
        self.inp_author.setText(meta.author_name)
        self.inp_key.setText(meta.menu_keybind)
        self.inp_req.setText(meta.requirements)
        self.inp_respect.setText(meta.community_respect)

        # Combo
        idx = self.combo_tier.findText(meta.patreon_tier)
        if idx != -1: self.combo_tier.setCurrentIndex(idx)

        # Check
        self.chk_nsfw.setChecked(meta.is_nsfw)

        # Editor
        self.editor.set_text_safe(config.mod_info)

        self._block = False

    def _on_meta_changed(self, prop, val, bool_mode=False):
        if self._block: return
        self._call_op("update_metadata_setting", prop_name=prop, val_str=str(val), val_bool=bool(val), use_bool=bool_mode)

    def on_mod_info_finished(self):
        if self._block: return
        self._call_op("update_config_setting", prop_name="mod_info", val_str=self.editor.text(), is_int=False)


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
        self.add_tab("Mod Info", ModInfoTab())
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
        
