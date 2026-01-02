# RZMenu/qt_editor/widgets/preferences.py
from PySide6 import QtWidgets, QtCore, QtGui
from .lib.theme import get_current_theme, get_theme_manager, generate_stylesheet
from .lib.widgets import RZPanelWidget, RZLabel, RZComboBox, RZGroupBox, RZColorButton
from .lib.base import RZSmartSlider 
from .keymap_editor import RZKeymapPanel

from ..conf.manager import get_config, set_config_value
from ..core.signals import SIGNALS

class RZSidebarItem(QtWidgets.QPushButton):
    """
    Стилизованная кнопка для бокового меню.
    """
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
    """
    Панель внешнего вида. Динамический редактор цветов.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # --- Theme Selector ---
        grp_selector = RZGroupBox("Theme Selection")
        l_sel = QtWidgets.QHBoxLayout(grp_selector)
        
        self.combo_themes = RZComboBox()
        # Загружаем список доступных тем
        themes = get_theme_manager()._themes.keys() # Access keys directly for now
        self.combo_themes.addItems(list(themes))
        
        # Читаем из конфига
        cfg = get_config()
        current_theme_key = cfg.get("appearance", {}).get("theme", "dark")
        
        # Устанавливаем в UI
        index = self.combo_themes.findText(current_theme_key, QtCore.Qt.MatchFixedString | QtCore.Qt.MatchCaseSensitive)
        if index < 0: 
             # Try case-insensitive lookup
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
        
        # --- DYNAMIC COLOR EDITOR ---
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        self.editor_content = QtWidgets.QWidget()
        self.editor_layout = QtWidgets.QVBoxLayout(self.editor_content)
        self.editor_layout.setContentsMargins(5, 5, 5, 5)
        self.editor_layout.setSpacing(15)
        
        self.scroll_area.setWidget(self.editor_content)
        layout.addWidget(self.scroll_area)
        
        # Build the UI based on current theme data
        self._build_editor_ui()

    def _on_theme_changed(self, text):
        theme_key = text
        set_config_value("appearance", "theme", theme_key)
        # Rebuild UI to reflect new theme values
        self._build_editor_ui()

    def _build_editor_ui(self):
        # Clear previous UI
        while self.editor_layout.count():
            item = self.editor_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        theme = get_current_theme()
        
        # Categorize keys
        categories = {
            "Backgrounds": [],
            "Text & Typography": [],
            "Borders": [],
            "Accents": [],
            "Viewport": [],
            "Context": [],
            "Special": [],
            "Misc": []
        }
        
        sorted_keys = sorted(theme.keys())
        for key in sorted_keys:
            if key == "name": continue
            
            if key.startswith("bg_"): categories["Backgrounds"].append(key)
            elif key.startswith("text_"): categories["Text & Typography"].append(key)
            elif key.startswith("border_"): categories["Borders"].append(key)
            elif "accent" in key: categories["Accents"].append(key)
            elif key.startswith("vp_"): categories["Viewport"].append(key)
            elif key.startswith("ctx_"): categories["Context"].append(key)
            elif key in ["selection", "warning", "error", "success"]: categories["Special"].append(key)
            else: categories["Misc"].append(key)
            
        # Create GroupBoxes
        for cat_name, keys in categories.items():
            if not keys: continue
            
            grp = RZGroupBox(cat_name)
            form = QtWidgets.QFormLayout(grp)
            form.setLabelAlignment(QtCore.Qt.AlignLeft)
            form.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
            
            for key in keys:
                # Color Button
                val = theme[key]
                # Filter out non-colors if any exist in json
                if not isinstance(val, str) or (not val.startswith("#") and not val.startswith("rgba")):
                     # Could be an image path or number, skip for now
                     continue

                btn = RZColorButton()
                btn.set_color(val) # Now safe to pass string!
                btn.setFixedHeight(25)
                
                # Connect change signal
                # btn emits [r, g, b, a] list. We need to convert back to hex/rgba string for config.
                btn.colorChanged.connect(lambda col_list, k=key: self._on_color_modified(k, col_list))
                
                lbl = RZLabel(key.replace("_", " ").title())
                form.addRow(lbl, btn)
            
            self.editor_layout.addWidget(grp)
            
        self.editor_layout.addStretch()

    def _on_color_modified(self, key, color_list):
        # Convert [r, g, b, a] to Hex String
        # Using QColor helper
        c = QtGui.QColor()
        c.setRgbF(color_list[0], color_list[1], color_list[2], color_list[3])
        
        # If alpha is 1, use simple Hex, else HexArgb or rgba string
        if color_list[3] >= 0.99:
            new_val = c.name() # #RRGGBB
        else:
            new_val = c.name(QtGui.QColor.HexArgb) # #AARRGGBB
            
        # 1. Update In-Memory Theme (Hack for instant preview)
        get_current_theme()[key] = new_val
        
        # 2. Trigger Global Refresh
        # We need a way to say "Theme data changed, please repaint" without saving to disk every ms
        # For now, let's allow it to repaint.
        # Ideally, we should have a "Dirty" state and save later. 
        # But to keep it simple, we just emit the signal.
        
        # Since we modified the dict in place, generating stylesheet will pick it up.
        new_qss = generate_stylesheet()
        
        # Find parent dialog and ask for update
        parent_dlg = self.window()
        if hasattr(parent_dlg, 'req_global_stylesheet_update'):
             parent_dlg.req_global_stylesheet_update.emit(new_qss)
             # Also Force update self to see result immediately
             parent_dlg.update_deep_style()


class RZPreferencesDialog(QtWidgets.QDialog):
    """
    Главное окно настроек. Слушает глобальный сигнал конфигурации для самообновления.
    """
    req_global_stylesheet_update = QtCore.Signal(str) # For window.py

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(900, 700)
        self.setObjectName("RZPreferencesDialog") 
        
        # Main Layout
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Left: Sidebar
        self.sidebar_container = QtWidgets.QWidget()
        self.sidebar_layout = QtWidgets.QVBoxLayout(self.sidebar_container)
        self.sidebar_layout.setContentsMargins(0, 10, 0, 10)
        self.sidebar_layout.setSpacing(2)
        self.sidebar_layout.setAlignment(QtCore.Qt.AlignTop)
        
        # Right: Stack
        self.content_stack = QtWidgets.QStackedWidget()
        
        main_layout.addWidget(self.sidebar_container, 1) 
        main_layout.addWidget(self.content_stack, 4) # More space for content
        
        self._setup_panels()
        self.update_style()
        
        # Подписываемся на глобальные изменения конфига (например, если сменили тему извне)
        SIGNALS.config_changed.connect(self.on_global_config_changed)

    def _setup_panels(self):
        # 1. Appearance
        self.panel_appearance = RZAppearancePanel(self)
        self._add_tab("Appearance", self.panel_appearance)
        
        # 2. Keymap
        self.panel_keymap = RZKeymapPanel(self)
        self._add_tab("Keybinding", self.panel_keymap)
        
        # 3. Dummy
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
        if section == "appearance":
            self.update_deep_style()

    def update_deep_style(self):
        """Aggressive style refresh for the dialog itself."""
        self.update_style()

        for i in range(self.sidebar_layout.count()):
            w = self.sidebar_layout.itemAt(i).widget()
            if isinstance(w, RZSidebarItem):
                w.setStyleSheet(w._get_style(w.isChecked()))

        all_widgets = self.findChildren(QtWidgets.QWidget)
        for widget in all_widgets:
            if isinstance(widget, RZSidebarItem): continue

            if hasattr(widget, 'apply_theme') and callable(widget.apply_theme):
                widget.apply_theme()
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                
            if isinstance(widget, RZColorButton):
                 widget.update_style()

            if hasattr(widget, 'spin') and hasattr(widget, 'label') and hasattr(widget, 'apply_theme'):
                widget.apply_theme()

    def update_style(self):
        t = get_current_theme()
        self.sidebar_container.setStyleSheet(f"background-color: {t.get('bg_input', '#222')}; border-right: 1px solid {t.get('border_main', '#444')};")
        self.content_stack.setStyleSheet(f"background-color: {t.get('bg_root', '#333')};")
        self.setStyleSheet(generate_stylesheet())