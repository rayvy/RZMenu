# RZMenu/qt_editor/widgets/preferences.py
from PySide6 import QtWidgets, QtCore, QtGui
from .lib.theme import get_current_theme, generate_stylesheet, get_theme_manager
from .lib.widgets import RZPanelWidget, RZLabel, RZComboBox, RZGroupBox
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
        
        bg = t['selection'] if active else "transparent"
        fg = t['text_bright'] if active else t['text_main']
        border_left = f"4px solid {t['accent']}" if active else "4px solid transparent"
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
                background-color: {t['bg_header']};
            }}
        """

    def setChecked(self, checked):
        super().setChecked(checked)
        self.setStyleSheet(self._get_style(checked))


class RZAppearancePanel(QtWidgets.QWidget):
    """
    Панель внешнего вида. При изменении пишет данные в ConfigManager.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # --- Theme Selector ---
        grp_theme = RZGroupBox("Color Palette")
        l_theme = QtWidgets.QHBoxLayout(grp_theme)
        
        self.combo_themes = RZComboBox()
        
        # Load themes from manager
        themes = get_theme_manager().get_available_themes()
        display_themes = [t.title() for t in themes]
        self.combo_themes.addItems(display_themes)
        
        # Читаем из конфига
        cfg = get_config()
        current_theme_key = cfg.get("appearance", {}).get("theme", "dark")
        
        # Устанавливаем в UI
        index = -1
        for i in range(self.combo_themes.count()):
            if self.combo_themes.itemText(i).lower() == current_theme_key.lower():
                index = i
                break
        if index >= 0:
            self.combo_themes.setCurrentIndex(index)

        self.combo_themes.currentTextChanged.connect(self._on_theme_changed)
        
        l_theme.addWidget(RZLabel("Interface Theme:"))
        l_theme.addWidget(self.combo_themes)
        l_theme.addStretch()
        layout.addWidget(grp_theme)
        
        layout.addStretch()

    def _on_theme_changed(self, text):
        # Пишем в конфиг -> ConfigManager сохранит и отправит сигнал
        theme_key = text.lower()
        set_config_value("appearance", "theme", theme_key)


class RZPreferencesDialog(QtWidgets.QDialog):
    """
    Главное окно настроек. Слушает глобальный сигнал конфигурации для самообновления.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(800, 600)
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
        main_layout.addWidget(self.content_stack, 3)     
        
        self._setup_panels()
        self.update_style()
        
        # Подписываемся на глобальные изменения конфига
        SIGNALS.config_changed.connect(self.on_global_config_changed)

    def _setup_panels(self):
        # 1. Appearance
        self.panel_appearance = RZAppearancePanel(self)
        self._add_tab("Appearance", self.panel_appearance)
        
        # 2. Keymap
        self.panel_keymap = RZKeymapPanel(self)
        self._add_tab("Keybinding", self.panel_keymap)
        
        # 3. Dummy (пока оставим как плейсхолдеры, но без функционала)
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
        """
        Реагируем на изменение любой настройки.
        Если это 'appearance', делаем полный рефреш стилей.
        """
        if section == "appearance":
            self.update_deep_style()

    def update_deep_style(self):
        """Aggressive style refresh for the dialog itself."""
        # 1. Update Containers
        self.update_style()

        # 2. Update Sidebar Items
        for i in range(self.sidebar_layout.count()):
            w = self.sidebar_layout.itemAt(i).widget()
            if isinstance(w, RZSidebarItem):
                w.setStyleSheet(w._get_style(w.isChecked()))

        # 3. Update Children (Duck Typing)
        all_widgets = self.findChildren(QtWidgets.QWidget)
        for widget in all_widgets:
            if isinstance(widget, RZSidebarItem): continue

            if hasattr(widget, 'apply_theme') and callable(widget.apply_theme):
                widget.apply_theme()
                widget.style().unpolish(widget)
                widget.style().polish(widget)

            if hasattr(widget, 'spin') and hasattr(widget, 'label') and hasattr(widget, 'apply_theme'):
                widget.apply_theme()

    def update_style(self):
        t = get_current_theme()
        self.sidebar_container.setStyleSheet(f"background-color: {t['bg_input']}; border-right: 1px solid {t['border_main']};")
        self.content_stack.setStyleSheet(f"background-color: {t['bg_root']};")
        self.setStyleSheet(generate_stylesheet())