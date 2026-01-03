# ... (imports remain the same)
from PySide6 import QtWidgets, QtCore, QtGui
from .lib.theme import get_current_theme, get_theme_manager, generate_stylesheet
from .lib.widgets import RZPanelWidget, RZLabel, RZComboBox, RZGroupBox, RZColorButton
from .lib.base import RZSmartSlider 
from .keymap_editor import RZKeymapPanel
from ..conf.manager import get_config, set_config_value
from ..core.signals import SIGNALS

# ... (RZFilePicker and RZSidebarItem remain the same) ...
class RZFilePicker(QtWidgets.QWidget):
    pathChanged = QtCore.Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        self.line_edit = QtWidgets.QLineEdit()
        self.line_edit.setReadOnly(True)
        self.line_edit.setPlaceholderText("Select image...")
        self.btn_browse = QtWidgets.QPushButton("...")
        self.btn_browse.setFixedWidth(30)
        self.btn_browse.clicked.connect(self._on_browse)
        layout.addWidget(self.line_edit)
        layout.addWidget(self.btn_browse)
    def set_path(self, path):
        self.line_edit.setText(path or "")
    def _on_browse(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Background Image", "", 
            "Images (*.png *.jpg *.jpeg *.gif);;All Files (*)"
        )
        if path:
            self.set_path(path)
            self.pathChanged.emit(path)

class RZSidebarItem(QtWidgets.QPushButton):
    def __init__(self, text, icon_name=None, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setFixedHeight(40)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setStyleSheet(self._get_style(False))
        self.toggled.connect(lambda checked: self.setStyleSheet(self._get_style(checked)))
    def _get_style(self, active):
        t = get_current_theme()
        bg = t.get('selection', '#444') if active else "transparent"
        fg = t.get('text_bright', '#FFF') if active else t.get('text_main', '#DDD')
        accent = t.get('accent', '#5298D4')
        border_left = f"4px solid {accent}" if active else "4px solid transparent"
        font_weight = "bold" if active else "normal"
        return f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: none;
                border-left: {border_left};
                text-align: left;
                padding-left: 15px;
                font-size: 11pt;
                font-weight: {font_weight};
                border-radius: 0px; 
            }}
            QPushButton:hover {{
                background-color: {t.get('bg_header', '#333')};
            }}
        """
    def setChecked(self, checked):
        super().setChecked(checked)
        self.setStyleSheet(self._get_style(checked))


class RZAppearancePanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # --- Theme Selector ---
        grp_selector = RZGroupBox("Theme Selection")
        l_sel = QtWidgets.QHBoxLayout(grp_selector)
        
        self.combo_themes = RZComboBox()
        themes = get_theme_manager().get_available_themes()
        self.combo_themes.addItems(list(themes))
        
        cfg = get_config()
        current_theme_key = cfg.get("appearance", {}).get("theme", "dark")
        
        index = self.combo_themes.findText(current_theme_key, QtCore.Qt.MatchFixedString | QtCore.Qt.MatchCaseSensitive)
        if index < 0:
             for i in range(self.combo_themes.count()):
                 if self.combo_themes.itemText(i).lower() == current_theme_key.lower():
                     index = i
                     break
        if index >= 0:
            self.combo_themes.setCurrentIndex(index)

        self.combo_themes.currentTextChanged.connect(self._on_theme_changed)
        
        l_sel.addWidget(RZLabel("Active Theme:"))
        l_sel.addWidget(self.combo_themes)
        l_sel.addStretch()
        layout.addWidget(grp_selector)
        
        # --- DYNAMIC EDITOR ---
        self.editor_tabs = QtWidgets.QTabWidget()
        self.editor_tabs.setObjectName("ThemeEditorTabs")
        layout.addWidget(self.editor_tabs)
        
        # --- BOTTOM BUTTONS ---
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_save = QtWidgets.QPushButton("Save Theme")
        self.btn_save.setFixedHeight(30)
        self.btn_save_copy = QtWidgets.QPushButton("Save Copy As...")
        self.btn_save_copy.setFixedHeight(30)
        self.btn_reset = QtWidgets.QPushButton("Reset Theme")
        self.btn_reset.setFixedHeight(30)
        self.btn_reset.setObjectName("BtnWarning")
        
        self.btn_save.clicked.connect(self._on_save_clicked)
        self.btn_save_copy.clicked.connect(self._on_save_copy_clicked)
        self.btn_reset.clicked.connect(self._on_reset_clicked)
        
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_save_copy)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_reset)
        layout.addLayout(btn_layout)

        self._build_editor_ui()

    def _on_theme_changed(self, text):
        theme_key = text
        set_config_value("appearance", "theme", theme_key)
        self._build_editor_ui()

    def _clear_tabs(self):
        while self.editor_tabs.count():
            w = self.editor_tabs.widget(0)
            self.editor_tabs.removeTab(0)
            if w: w.deleteLater()

    def _build_editor_ui(self):
        self._clear_tabs()
        theme = get_current_theme()

        self.editor_tabs.addTab(self._build_global_tab(theme), "Global")
        self.editor_tabs.addTab(self._build_panels_tab(theme), "Panels")
        self.editor_tabs.addTab(self._build_widgets_tab(theme), "Widgets")
        self.editor_tabs.addTab(self._build_viewport_tab(theme), "Viewport")

    def _create_scroll_content(self):
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        scroll.setWidget(content)
        return scroll, layout

    def _build_global_tab(self, theme):
        scroll, layout = self._create_scroll_content()
        grp_bg = RZGroupBox("Window Background")
        form_bg = QtWidgets.QFormLayout(grp_bg)
        
        self.combo_scope = RZComboBox()
        self.combo_scope.addItems(["Unified", "Individual"])
        self.combo_scope.setCurrentText(theme.get("bg_scope", "Unified"))
        self.combo_scope.currentTextChanged.connect(lambda t: self._on_generic_change("bg_scope", t))
        form_bg.addRow(RZLabel("Scope Mode:"), self.combo_scope)

        self.combo_bg_type = RZComboBox()
        self.combo_bg_type.addItems(["Solid Color", "Image", "Gradient"])
        current_type = theme.get("bg_type", "solid")
        type_map_inv = {"solid": "Solid Color", "image": "Image", "gradient": "Gradient"}
        self.combo_bg_type.setCurrentText(type_map_inv.get(current_type, "Solid Color"))
        self.combo_bg_type.currentTextChanged.connect(self._on_bg_type_changed)
        form_bg.addRow(RZLabel("Background Type:"), self.combo_bg_type)
        
        btn_root = RZColorButton(); btn_root.set_color(theme.get("bg_root", "#20232A"))
        btn_root.colorChanged.connect(lambda c: self._on_color_modified("bg_root", c))
        form_bg.addRow(RZLabel("Window Background:"), btn_root)

        self.file_picker = RZFilePicker()
        self.file_picker.set_path(theme.get("bg_image", ""))
        self.file_picker.pathChanged.connect(self._on_bg_image_changed)
        self.combo_fit = RZComboBox()
        self.combo_fit.addItems(["Cover", "Contain", "Stretch", "Tile"])
        self.combo_fit.setCurrentText(theme.get("bg_fit", "Cover"))
        self.combo_fit.currentTextChanged.connect(lambda t: self._on_generic_change("bg_fit", t))
        self.lbl_img = RZLabel("Image Path:")
        self.lbl_fit = RZLabel("Fit Mode:")
        form_bg.addRow(self.lbl_img, self.file_picker)
        form_bg.addRow(self.lbl_fit, self.combo_fit)

        self.cont_grad = QtWidgets.QWidget()
        l_grad = QtWidgets.QVBoxLayout(self.cont_grad); l_grad.setContentsMargins(0,0,0,0)
        h_grad_col = QtWidgets.QHBoxLayout()
        self.btn_grad1 = RZColorButton(); self.btn_grad1.set_color(theme.get("bg_grad_1", "#333"))
        self.btn_grad1.colorChanged.connect(lambda c: self._on_color_modified("bg_grad_1", c))
        self.btn_grad2 = RZColorButton(); self.btn_grad2.set_color(theme.get("bg_grad_2", "#000"))
        self.btn_grad2.colorChanged.connect(lambda c: self._on_color_modified("bg_grad_2", c))
        h_grad_col.addWidget(RZLabel("Start:")); h_grad_col.addWidget(self.btn_grad1)
        h_grad_col.addWidget(RZLabel("End:")); h_grad_col.addWidget(self.btn_grad2)
        l_grad.addLayout(h_grad_col)
        self.combo_grad_dir = RZComboBox(); self.combo_grad_dir.addItems(["Vertical", "Horizontal", "Diagonal"])
        self.combo_grad_dir.setCurrentText(theme.get("bg_grad_dir", "Vertical"))
        self.combo_grad_dir.currentTextChanged.connect(lambda t: self._on_generic_change("bg_grad_dir", t))
        h_grad_dir = QtWidgets.QHBoxLayout(); h_grad_dir.addWidget(RZLabel("Direction:")); h_grad_dir.addWidget(self.combo_grad_dir)
        l_grad.addLayout(h_grad_dir)
        form_bg.addRow(RZLabel("Gradient Colors:"), self.cont_grad)

        self.sl_opacity = RZSmartSlider(is_int=False); self.sl_opacity.spin.setRange(0.0, 1.0)
        self.sl_opacity.set_value_from_backend(theme.get("panel_opacity", 1.0))
        self.sl_opacity.value_changed.connect(lambda v: self._on_generic_change("panel_opacity", v))
        self.lbl_op = RZLabel("Glass Opacity:")
        form_bg.addRow(self.lbl_op, self.sl_opacity)

        btn_overlay = RZColorButton(); btn_overlay.set_color(theme.get("overlay_color", "#000"))
        btn_overlay.colorChanged.connect(lambda c: self._on_color_modified("overlay_color", c))
        form_bg.addRow(RZLabel("Glass Tint:"), btn_overlay)

        layout.addWidget(grp_bg)
        layout.addStretch()
        self._update_visibility(current_type)
        return scroll

    def _build_panels_tab(self, theme):
        scroll, layout = self._create_scroll_content()
        grp_struct = RZGroupBox("Structural Colors")
        form_struct = QtWidgets.QFormLayout(grp_struct)
        struct_keys = [
            ("Panel Base", "bg_panel"),
            ("Toolbar (Header)", "bg_header_main"),
            ("Footer", "bg_footer_main"),
            ("Area Header", "bg_area_header"),
        ]
        for label, key in struct_keys:
            btn = RZColorButton(); btn.set_color(theme.get(key, "#333"))
            btn.colorChanged.connect(lambda c, k=key: self._on_color_modified(k, c))
            form_struct.addRow(RZLabel(label), btn)
        layout.addWidget(grp_struct)

        grp_ctx = RZGroupBox("Context Colors")
        form_ctx = QtWidgets.QFormLayout(grp_ctx)
        for key in sorted(theme.keys()):
            if key.startswith("ctx_"):
                btn = RZColorButton(); btn.set_color(theme[key])
                btn.colorChanged.connect(lambda c, k=key: self._on_color_modified(k, c))
                form_ctx.addRow(RZLabel(key.replace("ctx_", "").title()), btn)
        layout.addWidget(grp_ctx)
        layout.addStretch()
        return scroll

    def _build_widgets_tab(self, theme):
        scroll, layout = self._create_scroll_content()
        groups = {
            "Widget Backgrounds": ["bg_header", "bg_input", "handle_splitter"],
            "Borders": ["border_main", "border_input", "border_contrast"],
            "Accents": ["accent", "accent_hover", "accent_text"],
            "Text": ["text_main", "text_dark", "text_disabled", "text_bright"],
            "States": ["selection", "warning", "error", "success"]
        }
        for name, keys in groups.items():
            grp = RZGroupBox(name); form = QtWidgets.QFormLayout(grp)
            for key in keys:
                if key in theme:
                    btn = RZColorButton(); btn.set_color(theme[key])
                    btn.colorChanged.connect(lambda c, k=key: self._on_color_modified(k, c))
                    form.addRow(RZLabel(key.replace("_", " ").title()), btn)
            layout.addWidget(grp)
        layout.addStretch()
        return scroll

    def _build_viewport_tab(self, theme):
        scroll, layout = self._create_scroll_content()
        grp = RZGroupBox("Visuals")
        form = QtWidgets.QFormLayout(grp)
        for key in sorted(theme.keys()):
            if key.startswith("vp_"):
                val = theme[key]
                if isinstance(val, str) and (val.startswith("#") or val.startswith("rgba")):
                    btn = RZColorButton(); btn.set_color(val)
                    btn.colorChanged.connect(lambda c, k=key: self._on_color_modified(k, c))
                    form.addRow(RZLabel(key.replace("vp_", "").replace("_", " ").title()), btn)
        layout.addWidget(grp)
        layout.addStretch()
        return scroll

    def _on_reset_clicked(self):
        theme_id = self.combo_themes.currentText()
        if QtWidgets.QMessageBox.question(self, "Reset Theme", f"Are you sure you want to reset '{theme_id}' to defaults?") == QtWidgets.QMessageBox.Yes:
            if get_theme_manager().reset_theme(theme_id):
                self._trigger_global_refresh()
                self._build_editor_ui()
                QtWidgets.QMessageBox.information(self, "Reset Complete", f"Theme '{theme_id}' has been reset.")

    def _update_visibility(self, bg_type):
        is_image = (bg_type == "image")
        is_grad = (bg_type == "gradient")
        
        self.file_picker.setVisible(is_image)
        self.lbl_img.setVisible(is_image)
        self.combo_fit.setVisible(is_image)
        self.lbl_fit.setVisible(is_image)
        
        self.cont_grad.setVisible(is_grad)
        
        # Opacity is mostly useful in Unified mode (Glass), but let's keep it visible
        self.lbl_op.setVisible(True)
        self.sl_opacity.setVisible(True)

    def _on_bg_type_changed(self, text):
        type_map = {"Solid Color": "solid", "Image": "image", "Gradient": "gradient"}
        new_type = type_map.get(text, "solid")
        
        get_current_theme()["bg_type"] = new_type
        self._update_visibility(new_type)
        self._trigger_global_refresh()
  
    def _on_bg_image_changed(self, path):
        theme = get_current_theme()
        theme["bg_image"] = path
        theme["bg_type"] = "image"
        
        self.combo_bg_type.blockSignals(True)
        self.combo_bg_type.setCurrentText("Image")
        self.combo_bg_type.blockSignals(False)
        self._update_visibility("image")
        self._trigger_global_refresh()

    def _on_generic_change(self, key, value):
        get_current_theme()[key] = value
        self._trigger_global_refresh()

    def _on_color_modified(self, key, color_list):
        if key is not None:
            c = QtGui.QColor()
            c.setRgbF(color_list[0], color_list[1], color_list[2], color_list[3])
            if color_list[3] >= 0.99: new_val = c.name() 
            else: new_val = c.name(QtGui.QColor.HexArgb)
            get_current_theme()[key] = new_val
        self._trigger_global_refresh()

    def _trigger_global_refresh(self):
        new_qss = generate_stylesheet()
        parent_dlg = self.window()
        if hasattr(parent_dlg, 'req_global_stylesheet_update'):
             parent_dlg.req_global_stylesheet_update.emit(new_qss)
             parent_dlg.update_deep_style()
        
        # Notify other windows (like the Main Editor)
        SIGNALS.config_changed.emit("appearance")

    def _on_save_clicked(self):
        theme_id = self.combo_themes.currentText().lower()
        theme_data = get_current_theme()
        get_theme_manager().save_theme(theme_id, theme_data)
        QtWidgets.QMessageBox.information(self, "Theme Saved", f"Theme '{theme_id}' saved.")

    def _on_save_copy_clicked(self):
        new_name, ok = QtWidgets.QInputDialog.getText(self, "Save Theme Copy", "Enter name:", text=self.combo_themes.currentText() + "_Copy")
        if ok and new_name:
            theme_id = new_name.lower().replace(" ", "_")
            theme_data = get_current_theme()
            get_theme_manager().save_theme(theme_id, theme_data)
            self.combo_themes.blockSignals(True)
            self.combo_themes.clear()
            self.combo_themes.addItems(list(get_theme_manager().get_available_themes()))
            index = self.combo_themes.findText(theme_id, QtCore.Qt.MatchFixedString)
            if index >= 0: self.combo_themes.setCurrentIndex(index)
            self.combo_themes.blockSignals(False)
            set_config_value("appearance", "theme", theme_id)
            QtWidgets.QMessageBox.information(self, "Theme Created", f"Theme '{new_name}' created.")

# (RZPreferencesDialog remains mostly the same, just needed for context)
class RZPreferencesDialog(QtWidgets.QDialog):
    req_global_stylesheet_update = QtCore.Signal(str) 
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(900, 700)
        self.setObjectName("RZPreferencesDialog") 
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.sidebar_container = QtWidgets.QWidget()
        self.sidebar_layout = QtWidgets.QVBoxLayout(self.sidebar_container)
        self.sidebar_layout.setContentsMargins(0, 10, 0, 10)
        self.sidebar_layout.setSpacing(2)
        self.sidebar_layout.setAlignment(QtCore.Qt.AlignTop)
        self.content_stack = QtWidgets.QStackedWidget()
        main_layout.addWidget(self.sidebar_container, 1) 
        main_layout.addWidget(self.content_stack, 4) 
        self._setup_panels()
        self.update_style()
        SIGNALS.config_changed.connect(self.on_global_config_changed)
    def _setup_panels(self):
        self.panel_appearance = RZAppearancePanel(self)
        self._add_tab("Appearance", self.panel_appearance)
        self.panel_keymap = RZKeymapPanel(self)
        self._add_tab("Keybinding", self.panel_keymap)
        self._add_tab("System", QtWidgets.QLabel("System settings placeholder..."))
        if self.sidebar_layout.count() > 0:
            self.sidebar_layout.itemAt(0).widget().setChecked(True)
            self.content_stack.setCurrentIndex(0)
    def _add_tab(self, name, widget):
        btn = RZSidebarItem(name, parent=self.sidebar_container)
        index = self.content_stack.addWidget(widget)
        btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(index))
        self.sidebar_layout.addWidget(btn)
    def on_global_config_changed(self, section):
        if section == "appearance": self.update_deep_style()
    def update_deep_style(self):
        self.update_style()
        for i in range(self.sidebar_layout.count()):
            w = self.sidebar_layout.itemAt(i).widget()
            if isinstance(w, RZSidebarItem): w.setStyleSheet(w._get_style(w.isChecked()))
        all_widgets = self.findChildren(QtWidgets.QWidget)
        for widget in all_widgets:
            if isinstance(widget, RZSidebarItem): continue
            if hasattr(widget, 'apply_theme') and callable(widget.apply_theme):
                widget.apply_theme()
                widget.style().unpolish(widget)
                widget.style().polish(widget)
            if isinstance(widget, RZColorButton): widget.update_style()
            if hasattr(widget, 'spin') and hasattr(widget, 'label') and hasattr(widget, 'apply_theme'): widget.apply_theme()
    def update_style(self):
        t = get_current_theme()
        self.sidebar_container.setStyleSheet(f"background-color: {t.get('bg_input', '#222')}; border-right: 1px solid {t.get('border_main', '#444')};")
        self.content_stack.setStyleSheet(f"background-color: {t.get('bg_root', '#333')};")
        self.setStyleSheet(generate_stylesheet())