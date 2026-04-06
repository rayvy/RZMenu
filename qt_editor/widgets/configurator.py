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


import threading
import time
import os

class AsyncFontLoader(QtCore.QThread):
    """
    Background thread that builds the full font registry once.
    Result: {family: {style: (abs_path, font_index)}}
    """
    fonts_loaded = QtCore.Signal(dict)
    _cache = None

    def run(self):
        if AsyncFontLoader._cache is not None:
            self.fonts_loaded.emit(AsyncFontLoader._cache)
            return
        try:
            from ...utils.font_utils import build_font_registry, reset_registry
            reset_registry()  # Ensure fresh scan (handles addon reloads)
            registry = build_font_registry()
            
            # --- Variable Font Support (Qt Enrichment) ---
            # For each family, ask Qt if there are styles we missed (e.g. named instances in variable fonts)
            # --- Оказывается удаление данного куска кода не приводит к ускорению запуска редактора, так что проблема не в нём---
            try:
                db = QtGui.QFontDatabase()
                for family in list(registry.keys()):
                    styles = registry[family]
                    if "Regular" not in styles:
                        continue
                    
                    path, index = styles["Regular"]
                    # Ask Qt for styles of this specific family
                    available_styles = db.styles(family)
                    for s in available_styles:
                        if s not in styles:
                            # Map the new style to the same file (Variable Font behavior)
                            styles[s] = (path, index)
            except Exception as e:
                print(f"[FontsDebug] Qt Enrichment failed: {e}")

            AsyncFontLoader._cache = registry
            self.fonts_loaded.emit(registry)
        except Exception as e:
            print(f"Error building font registry: {e}")
            import traceback; traceback.print_exc()
            self.fonts_loaded.emit({})

class RZFontDelegate(QtWidgets.QStyledItemDelegate):
    """
    Renders font family names in their respective actual font for preview.
    (Expects data to be family name)
    """
    def paint(self, painter, option, index):
        painter.save()
        family = index.data(QtCore.Qt.DisplayRole)
        # itemData holds the path if we want, but displayRole is usually enough for Font()
        
        # Determine colors
        t = get_current_theme()
        is_selected = option.state & QtWidgets.QStyle.State_Selected
        text_color = QtGui.QColor(t.get('text_main', '#E0E2E4')) if not is_selected else QtGui.QColor("#FFF")
        
        # 1. Background
        if is_selected:
            painter.fillRect(option.rect, QtGui.QColor(t.get('accent', '#5298D4')))
        
        # 2. Draw preview text
        font = QtGui.QFont(family)
        font.setPixelSize(14)
        painter.setFont(font)
        painter.setPen(text_color)
        
        rect = option.rect.adjusted(10, 0, -10, 0)
        painter.drawText(rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, family)
        
        painter.restore()

    def sizeHint(self, option, index):
        return QtCore.QSize(200, 30)

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
        
        # Mod Name removed.
        
        # Canvas Size
        h_canvas = QtWidgets.QHBoxLayout()
        h_canvas.addWidget(RZLabel("Canvas:"))
        self.spin_w = RZSpinBox()
        self.spin_w.setRange(0, 8192)
        self.spin_w.valueChanged.connect(lambda v: self.on_canvas_changed(0, v))
        self.spin_h = RZSpinBox()
        self.spin_h.setRange(0, 8192)
        self.spin_h.valueChanged.connect(lambda v: self.on_canvas_changed(1, v))
        h_canvas.addWidget(self.spin_h)
        l_proj.addLayout(h_canvas)

        # Interpolation Speed
        h_interp = QtWidgets.QHBoxLayout()
        h_interp.addWidget(RZLabel("Interpolation Speed:"))
        self.spin_interp = RZDoubleSpinBox()
        self.spin_interp.setRange(0.1, 100.0)
        self.spin_interp.setSingleStep(0.1)
        self.spin_interp.valueChanged.connect(self.on_interpolation_changed)
        h_interp.addWidget(self.spin_interp)
        l_proj.addLayout(h_interp)

        # Menu Keybind (moved here from Mod Info tab)
        h_key = QtWidgets.QHBoxLayout()
        h_key.addWidget(RZLabel("Menu Keybind:"))
        self.inp_keybind = RZLineEdit()
        self.inp_keybind.setPlaceholderText("/")
        self.inp_keybind.editingFinished.connect(self.on_keybind_changed)
        h_key.addWidget(self.inp_keybind)
        l_proj.addLayout(h_key)

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

        # --- Textures ---
        l_textures = self.add_section("Textures")
        
        self.chk_tex = RZCheckBox("TexWorks")
        self.chk_tex.toggled.connect(lambda v: self.on_addon_toggled("tex_works", v))
        l_textures.addWidget(self.chk_tex)
        
        self.chk_texture_slots = RZCheckBox("Export Texture Slots")
        self.chk_texture_slots.toggled.connect(self.on_texture_slots_toggled)
        l_textures.addWidget(self.chk_texture_slots)

        
        self.scroll_layout.addStretch()

    def update_ui(self):
        self._block = True
        if not bpy.context or not bpy.context.scene: return
        rzm = bpy.context.scene.rzm
        
        # Stateful Update
        # Stateful Update
            
        if self.spin_w.value() != rzm.config.canvas_size[0]:
            self.spin_w.setValue(rzm.config.canvas_size[0])
            
        if self.spin_h.value() != rzm.config.canvas_size[1]:
            self.spin_h.setValue(rzm.config.canvas_size[1])
            
        if self.spin_interp.value() != rzm.config.custom_interpolation_speed:
            self.spin_interp.setValue(rzm.config.custom_interpolation_speed)

        # Keybind
        meta = rzm.meta_data
        if self.inp_keybind.text() != meta.menu_keybind:
            self.inp_keybind.setText(meta.menu_keybind)

        
        addons = rzm.addons
        if self.chk_debug.isChecked() != addons.debugger_info:
            self.chk_debug.setChecked(addons.debugger_info)
            
        if self.chk_vfx.isChecked() != addons.vfx:
            self.chk_vfx.setChecked(addons.vfx)
            
        if self.chk_morph.isChecked() != addons.shape_morph:
            self.chk_morph.setChecked(addons.shape_morph)
            
        if self.chk_facetexworkspreseted.isChecked() != addons.facetexworkspreseted:
            self.chk_facetexworkspreseted.setChecked(addons.facetexworkspreseted)
            
        if self.chk_tex.isChecked() != addons.tex_works:
            self.chk_tex.setChecked(addons.tex_works)
            
        if self.chk_texture_slots.isChecked() != rzm.export_texture_slots:
            self.chk_texture_slots.setChecked(rzm.export_texture_slots)

        
        self._block = False

    # on_mod_name_changed removed

    def on_interpolation_changed(self, value):
        if self._block: return
        try:
            bpy.context.scene.rzm.config.custom_interpolation_speed = value
        except Exception as e:
            print(f"Error setting interpolation speed: {e}")

    def on_keybind_changed(self):
        if self._block: return
        self._call_op("update_metadata_setting", prop_name="menu_keybind",
                      val_str=self.inp_keybind.text(), val_bool=False, use_bool=False)

    def on_canvas_changed(self, idx, val):
        if self._block: return
        self._call_op("update_config_setting", prop_name="canvas_size", index=idx, val_str=str(val), is_int=True)
        
    def on_addon_toggled(self, key, val):
        if self._block: return
        self._call_op("update_addon_setting", prop_name=key, val_bool=val)

    def on_texture_slots_toggled(self, val):
        if self._block: return
        self._call_op("update_export_setting", prop_name="export_texture_slots", val_bool=val, use_bool=True)







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
        if self._block: return
        self._block = True
        try:
            if not bpy.context or not bpy.context.scene: return
            rzm = bpy.context.scene.rzm
            config = rzm.config
            
            # Check if property exists
            if not hasattr(config, self.property_name):
                if self.editor.isEnabled():
                    self.editor.setPlainText(f"Error: Property '{self.property_name}' not found in RZMenuConfig.\nPlease update p_settings.py")
                    self.editor.setEnabled(False)
                return
                
            self.editor.setEnabled(True)
            val = getattr(config, self.property_name)
            
            # CRITICAL: Cancel pending debouncer to avoid sync loops
            # If we are receiving data from Blender, we must not commit it back.
            if hasattr(self.editor, 'debouncer'):
                self.editor.debouncer.cancel()

            if self.editor.toPlainText() != val:
                self.editor.blockSignals(True)
                self.editor.setPlainText(val)
                self.editor.blockSignals(False)
        finally:
            self._block = False

    def on_text_changed(self):
        if self._block: return
        
        # SAFETY 1: Only commit if this tab is actually the ACTIVE one.
        # This prevents background tabs (which may not have been updated from Blender yet)
        # from overwriting data with their initial empty state.
        parent_manager = self.parentWidget()
        while parent_manager and not hasattr(parent_manager, 'stack'):
            parent_manager = parent_manager.parentWidget()
        
        if parent_manager:
            idx = parent_manager.stack.indexOf(self)
            if idx != parent_manager.stack.currentIndex():
                return

        if not bpy.context or not bpy.context.scene: return
        rzm = bpy.context.scene.rzm
        current_val = getattr(rzm.config, self.property_name, "")
        new_val = self.editor.toPlainText()

        # SAFETY 2: If Blender has data but UI is empty, and user didn't explicitly clear it,
        # skip to avoid accidental wipes during initialization.
        if current_val and not new_val and not self.editor.hasFocus():
            print(f"[RZM] Refused to overwrite '{self.property_name}' with empty text (Safety)")
            return

        # Use generic update_config_setting op
        self._call_op("update_config_setting", 
                      prop_name=self.property_name, 
                      val_str=new_val, 
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
        self.inp_author = self._add_global_field(l_base, "Artist Name (Global):", "author_name")

        # --- 2. Technical & Description ---
        l_tech = self.add_section("Lore & Technical")
        self.inp_req = self._add_field(l_tech, "Requirements:", "requirements")
        self.inp_respect = self._add_field(l_tech, "Credits To:", "community_respect")
        
        self.inp_pre_desc = self._add_global_field(l_tech, "Pre-Description (Global):", "pre_description")
        self.inp_post_desc = self._add_global_field(l_tech, "Post-Description (Global):", "post_description")

        # --- 3. Main Mod Info Text ---
        l_desc = self.add_section("Mod Info Template (Exported)")
        
        # Reset to default button
        btn_reset = RZPushButton("↺  Reset to Default Template")
        btn_reset.clicked.connect(self._on_reset_mod_info)
        l_desc.addWidget(btn_reset)

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

    def _add_global_field(self, layout, label, prop_name):
        h = QtWidgets.QHBoxLayout()
        h.addWidget(RZLabel(label))
        inp = RZLineEdit()
        inp.editingFinished.connect(lambda: self._on_global_changed(prop_name, inp.text()))
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
        self.inp_req.setText(meta.requirements)
        self.inp_respect.setText(meta.community_respect)
        
        # Addon Prefs (Global)
        from ...operators.tier_ops import get_prefs
        prefs = get_prefs(bpy.context)
        if prefs:
            self.inp_author.setText(prefs.author_name)
            self.inp_pre_desc.setText(prefs.pre_description)
            self.inp_post_desc.setText(prefs.post_description)

        # Editor
        self.editor.set_text_safe(config.mod_info)

        self._block = False

    def _on_reset_mod_info(self):
        """Resets mod_info to the default template text from constants."""
        try:
            from ...data.constants import DEFAULT_MOD_INFO_TEXT
            self._call_op("update_config_setting", prop_name="mod_info",
                          val_str=DEFAULT_MOD_INFO_TEXT, is_int=False)
            self.editor.set_text_safe(DEFAULT_MOD_INFO_TEXT)
        except Exception as e:
            print(f"[ModInfoTab] Reset failed: {e}")

    def _on_meta_changed(self, prop, val, bool_mode=False):
        if self._block: return
        self._call_op("update_metadata_setting", prop_name=prop, val_str=str(val), val_bool=bool(val), use_bool=bool_mode)

    def _on_global_changed(self, prop, val):
        if self._block: return
        self._call_op("update_global_setting", prop_name=prop, val_str=str(val))

    def on_mod_info_finished(self):
        if self._block: return
        self._call_op("update_config_setting", prop_name="mod_info", val_str=self.editor.text(), is_int=False)

class FontsTab(BaseConfigTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.slot_widgets = []
        self.font_registry = {}  # {family: {style: (path, index)}}
        self._init_ui()

    def _init_ui(self):
        for i in range(4):
            l_slot = self.add_section(f"Font Slot {i+1}")

            # --- 1. Mode ---
            h_src = QtWidgets.QHBoxLayout()
            h_src.addWidget(RZLabel("Mode:"))
            combo_src = RZComboBox()
            combo_src.addItems(["Windows Arial (Default)", "Custom / System Search"])
            combo_src.currentIndexChanged.connect(lambda idx, s=i, c=combo_src: self.on_source_changed(s, c))
            h_src.addWidget(combo_src)
            l_slot.addLayout(h_src)

            # --- 2. Family ComboBox --- (Custom Mode)
            h_fam = QtWidgets.QHBoxLayout()
            h_fam.addWidget(RZLabel("Family:"))
            combo_fam = RZComboBox()
            combo_fam.setEditable(True)
            combo_fam.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
            combo_fam.lineEdit().setPlaceholderText("Loading fonts…")
            combo_fam.setItemDelegate(RZFontDelegate())
            combo_fam.activated.connect(lambda idx, s=i, cf=combo_fam: self.on_family_selected(s, cf))
            h_fam.addWidget(combo_fam, 1)
            l_slot.addLayout(h_fam)

            # --- 3. Style ComboBox --- (Custom Mode)
            h_style = QtWidgets.QHBoxLayout()
            h_style.addWidget(RZLabel("Style:"))
            combo_style = RZComboBox()
            combo_style.addItem("Regular")
            combo_style.activated.connect(lambda idx, s=i, cf=combo_fam, cs=combo_style: self.on_style_selected(s, cf, cs))
            h_style.addWidget(combo_style, 1)
            l_slot.addLayout(h_style)

            # --- 4. Path ---
            h_path = QtWidgets.QHBoxLayout()
            h_path.addWidget(RZLabel("Font Path:"))
            inp_path = RZLineEdit()
            inp_path.setPlaceholderText("Select family/style above or enter path manually…")
            inp_path.editingFinished.connect(lambda s=i, inp=inp_path: self.on_path_changed(s, inp))
            h_path.addWidget(inp_path, 1)
            l_slot.addLayout(h_path)

            # --- 5. Font Index (shown only for .ttc) ---
            h_index = QtWidgets.QHBoxLayout()
            lbl_index = RZLabel("TTC Index:")
            spin_index = RZSpinBox()
            spin_index.setRange(0, 99)
            spin_index.setFixedWidth(60)
            spin_index.valueChanged.connect(lambda val, s=i: self.on_index_changed(s, val))
            h_index.addWidget(lbl_index)
            h_index.addWidget(spin_index)
            h_index.addStretch()
            lbl_index.setVisible(False); spin_index.setVisible(False)
            l_slot.addLayout(h_index)

            # --- 6. Metrics ---
            h_cell_den = QtWidgets.QHBoxLayout()
            h_cell_den.addWidget(RZLabel("Cell:"))
            spin_cell = RZSpinBox()
            spin_cell.setRange(16, 256)
            spin_cell.valueChanged.connect(lambda val, s=i: self.on_cell_changed(s, val))
            h_cell_den.addWidget(spin_cell)
            h_cell_den.addSpacing(20)
            h_cell_den.addWidget(RZLabel("Density:"))
            spin_den = RZDoubleSpinBox()
            spin_den.setRange(0.1, 1.0); spin_den.setSingleStep(0.01)
            spin_den.valueChanged.connect(lambda val, s=i: self.on_den_changed(s, val))
            h_cell_den.addWidget(spin_den)
            l_slot.addLayout(h_cell_den)

            self.slot_widgets.append({
                'src': combo_src,
                'fam_combo': combo_fam,
                'fam_layout': h_fam,
                'style_combo': combo_style,
                'style_layout': h_style,
                'path': inp_path,
                'path_layout': h_path,
                'index_lbl': lbl_index,
                'index_spin': spin_index,
                'cell': spin_cell,
                'den': spin_den,
            })

        # Background registry scanner
        self.font_loader = AsyncFontLoader(self)
        self.font_loader.fonts_loaded.connect(self._on_registry_ready)
        self.font_loader.start()

    def _on_registry_ready(self, registry: dict):
        """Called when background thread built the font registry."""
        self.font_registry = registry
        # Populate all Family comboboxes from registry
        families = sorted(registry.keys(), key=str.lower)
        for w in self.slot_widgets:
            cb = w['fam_combo']
            cb.blockSignals(True)
            cb.clear()
            cb.addItems(families)
            cb.lineEdit().setPlaceholderText("Select font…")
            cb.blockSignals(False)
        self.update_ui()

    def _set_custom_row_visible(self, w: dict, visible: bool):
        """Show/hide Custom-mode widgets."""
        for key in ('fam_layout', 'style_layout', 'path_layout'):
            layout = w[key]
            for j in range(layout.count()):
                cw = layout.itemAt(j).widget()
                if cw: cw.setVisible(visible)

    def _set_ttc_visible(self, w: dict, visible: bool):
        w['index_lbl'].setVisible(visible)
        w['index_spin'].setVisible(visible)

    def _populate_styles(self, w: dict, family: str, current_style: str = "Regular"):
        """Fill style combo for the given family."""
        styles = list(self.font_registry.get(family, {}).keys())
        styles.sort(key=lambda s: (0 if s == "Regular" else 1, s))
        if not styles:
            styles = ["Regular"]
        cb = w['style_combo']
        cb.blockSignals(True)
        cb.clear()
        cb.addItems(styles)
        idx = cb.findText(current_style)
        cb.setCurrentIndex(max(0, idx))
        cb.blockSignals(False)

    def update_ui(self):
        self._block = True
        try:
            if not bpy.context or not bpy.context.scene:
                return
            fonts = bpy.context.scene.rzm.fonts

            sources = ['DEFAULT', 'CUSTOM']
            for i in range(min(4, len(fonts))):
                slot = fonts[i]
                w = self.slot_widgets[i]
                try:
                    # 1. Mode
                    src_key = slot.font_source
                    if src_key not in sources:
                        if src_key in ('ARIAL', 'CONSOLAS', 'SEGOE'): src_key = 'DEFAULT'
                        elif src_key == 'SYSTEM': src_key = 'CUSTOM'
                    src_idx = sources.index(src_key) if src_key in sources else 0
                    if w['src'].currentIndex() != src_idx:
                        w['src'].setCurrentIndex(src_idx)

                    is_custom = src_key == 'CUSTOM'
                    self._set_custom_row_visible(w, is_custom)

                    # .ttc index visibility
                    current_path = slot.custom_path if is_custom else ""
                    is_ttc = current_path.lower().endswith('.ttc')
                    self._set_ttc_visible(w, is_custom and is_ttc)

                    if is_custom:
                        # --- Sync Family + Style combos from path (path = source of truth) ---
                        from ...utils.font_utils import find_by_path
                        result = find_by_path(current_path) if current_path else None

                        w['fam_combo'].blockSignals(True)
                        w['style_combo'].blockSignals(True)

                        if result:
                            fam, style, _ = result
                            # Set family
                            fam_idx = w['fam_combo'].findText(fam)
                            if fam_idx >= 0:
                                w['fam_combo'].setCurrentIndex(fam_idx)
                            else:
                                w['fam_combo'].lineEdit().setText(fam)
                            # Set styles for this family
                            self._populate_styles(w, fam, style)
                        elif current_path:
                            # Unknown path: show filename in family field
                            w['fam_combo'].setCurrentIndex(-1)
                            w['fam_combo'].lineEdit().setText(os.path.basename(current_path))
                            w['style_combo'].clear()
                            w['style_combo'].addItem("—")
                        else:
                            # Empty path
                            w['fam_combo'].setCurrentIndex(-1)
                            w['fam_combo'].lineEdit().clear()
                            w['style_combo'].clear()
                            w['style_combo'].addItem("Regular")

                        w['fam_combo'].blockSignals(False)
                        w['style_combo'].blockSignals(False)

                        # Sync path field
                        if w['path'].text() != current_path:
                            w['path'].setText(current_path)

                        # Sync index spin
                        if is_ttc:
                            w['index_spin'].blockSignals(True)
                            w['index_spin'].setValue(slot.font_index)
                            w['index_spin'].blockSignals(False)

                    if w['cell'].value() != slot.cell_size:
                        w['cell'].setValue(slot.cell_size)
                    if abs(w['den'].value() - slot.density) > 0.001:
                        w['den'].setValue(slot.density)

                except Exception as e:
                    print(f"Error update slot UI [{i}]: {e}")
                    import traceback; traceback.print_exc()
        finally:
            self._block = False

    # ── User Actions ─────────────────────────────────────────────────────────

    def on_source_changed(self, slot_idx, combo):
        if self._block: return
        sources = ['DEFAULT', 'CUSTOM']
        src_val = sources[min(combo.currentIndex(), 1)]
        self._call_font_op(slot_idx, "font_source", val_str=src_val)
        if src_val == 'DEFAULT':
            arial = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', 'arial.ttf')
            self._call_font_op(slot_idx, "custom_path", val_str=arial if os.path.exists(arial) else "")
        self.update_ui()

    def on_family_selected(self, slot_idx, combo_fam):
        """User chose a family → pick Regular (or first) style and write path."""
        if self._block: return
        family = combo_fam.currentText()
        if not family or family == "Loading fonts…":
            return

        w = self.slot_widgets[slot_idx]
        # Populate style combo for new family
        self._populate_styles(w, family, "Regular")
        # Resolve path
        self._apply_family_style(slot_idx, family, "Regular")

    def on_style_selected(self, slot_idx, combo_fam, combo_style):
        """User chose a style → write path."""
        if self._block: return
        family = combo_fam.currentText()
        style = combo_style.currentText()
        if not family or style == "—":
            return
        self._apply_family_style(slot_idx, family, style)

    def _apply_family_style(self, slot_idx, family, style):
        """Resolve (family, style) → (path, index) and save to slot."""
        from ...utils.font_utils import get_font_entry
        path, index = get_font_entry(family, style)
        print(f"[FontsDebug] Apply Family Style: Slot {slot_idx+1}, Fam: {family}, Style: {style} -> Path: {path}, Index: {index}")
        if not path:
            # Fallback: on-demand scan
            from ...utils.font_utils import find_system_font
            path = find_system_font(family)
            index = 0

        if path:
            self._call_font_op(slot_idx, "custom_path", val_str=path)
            self._call_font_op(slot_idx, "font_style_name", val_str=style)
            self._call_font_op(slot_idx, "font_index", val_int=index, use_int=True)
            # Immediately update path field so user sees result
            w = self.slot_widgets[slot_idx]
            w['path'].blockSignals(True); w['path'].setText(path); w['path'].blockSignals(False)
            # Show/hide TTC index field
            is_ttc = path.lower().endswith('.ttc')
            self._set_ttc_visible(w, is_ttc)
            if is_ttc:
                w['index_spin'].blockSignals(True); w['index_spin'].setValue(index); w['index_spin'].blockSignals(False)
        else:
            print(f"[FontsTab] Could not resolve path for '{family}' / '{style}'")

    def on_path_changed(self, slot_idx, inp):
        if self._block: return
        self._call_font_op(slot_idx, "custom_path", val_str=inp.text())
        # Reset style name to unknown (will be re-resolved on next update_ui)
        self._call_font_op(slot_idx, "font_style_name", val_str="")
        self.update_ui()

    def on_index_changed(self, slot_idx, val):
        if self._block: return
        self._call_font_op(slot_idx, "font_index", val_int=val, use_int=True)

    def on_cell_changed(self, slot_idx, val):
        if self._block: return
        self._call_font_op(slot_idx, "cell_size", val_int=val, use_int=True)

    def on_den_changed(self, slot_idx, val):
        if self._block: return
        self._call_font_op(slot_idx, "density", val_float=val, use_float=True)

    def _call_font_op(self, slot_idx, prop, val_str="", val_int=0, val_float=0.0, val_bool=False, use_int=False, use_float=False, use_bool=False):
        try:
            bpy.ops.rzm.update_font_setting(
                slot_index=slot_idx, prop_name=prop,
                val_str=val_str, val_int=val_int,
                val_float=val_float, val_bool=val_bool,
                use_int=use_int, use_float=use_float, use_bool=use_bool
            )
        except Exception as e:
            print(f"Error updating font setting: {e}")


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
        self.add_tab("Fonts", FontsTab())
        self.add_tab("Mod Info", ModInfoTab())
        self.add_tab("PreSnippet", SnippetTab("pre_snippet", "Pre-Injection Code"))

        self.add_tab("PostSnippet", SnippetTab("post_snippet", "Post-Injection Code"))

        # Extensible point: self.add_tab("VFX", VFXTab())
        
        self.apply_theme()
        
        # Subscribe to updates
        SIGNALS.structure_changed.connect(self.refresh_current)
        SIGNALS.data_changed.connect(self.refresh_current)

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
        
