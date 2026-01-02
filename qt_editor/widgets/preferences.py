# RZMenu/qt_editor/widgets/preferences.py
from PySide6 import QtWidgets, QtCore, QtGui
from .lib.theme import get_current_theme, get_theme_manager, generate_stylesheet
from .lib.widgets import RZPanelWidget, RZLabel, RZComboBox, RZGroupBox
from .lib.base import RZSmartSlider 
from .keymap_editor import RZKeymapPanel

class RZSidebarItem(QtWidgets.QPushButton):
    """
    Стилизованная кнопка для бокового меню (как в ComfyUI).
    """
    def __init__(self, text, icon_name=None, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setFixedHeight(40)
        self.setCursor(QtCore.Qt.PointingHandCursor)

        # Initial style
        self.setStyleSheet(self._get_style(False))

        # UPDATE: Ensure style refreshes when state changes (clicked by user)
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
    Панель внешнего вида. Реализует смену темы.
    """
    theme_changed_signal = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # --- Theme Selector ---
        grp_theme = RZGroupBox("Color Palette")
        l_theme = QtWidgets.QHBoxLayout(grp_theme)
        
        self.combo_themes = RZComboBox()
        self.combo_themes.addItems(["Dark", "Light", "Blue"])
        
        # Устанавливаем текущее значение
        current_theme_key = get_theme_manager()._current_theme_name
        # Пытаемся найти текущую тему в списке (игнорируя регистр)
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
        
        # --- ZAGLUSHKI (Placeholders for visual similarity to ComfyUI) ---
        
        # Node Settings
        grp_node = RZGroupBox("Nodes (Mockup)")
        form_node = QtWidgets.QFormLayout(grp_node)
        
        slider_opacity = RZSmartSlider(value=1.0, is_int=False)
        form_node.addRow("Node Opacity:", slider_opacity)
        
        slider_font = RZSmartSlider(value=10, is_int=True)
        form_node.addRow("Widget Font Size:", slider_font)
        
        layout.addWidget(grp_node)
        
        # Canvas Settings
        grp_canvas = RZGroupBox("Canvas (Mockup)")
        form_canvas = QtWidgets.QFormLayout(grp_canvas)
        
        # Имитация поля ввода с кнопкой
        w_img_input = QtWidgets.QWidget()
        l_img = QtWidgets.QHBoxLayout(w_img_input)
        l_img.setContentsMargins(0,0,0,0)
        line_img = QtWidgets.QLineEdit()
        line_img.setPlaceholderText("Image URL...")
        btn_upload = QtWidgets.QPushButton("↑")
        btn_upload.setFixedWidth(30)
        l_img.addWidget(line_img)
        l_img.addWidget(btn_upload)
        
        form_canvas.addRow("Background Image:", w_img_input)
        layout.addWidget(grp_canvas)
        
        layout.addStretch()

    def _on_theme_changed(self, text):
        # DIRTY HACK: Меняем тему глобально через менеджер
        theme_key = text.lower()
        get_theme_manager().set_theme(theme_key)
        
        # Сигнализируем окну, что пора обновить QSS
        self.theme_changed_signal.emit()


class RZPreferencesDialog(QtWidgets.QDialog):
    """
    Главное окно настроек в стиле ComfyUI.
    """
    req_global_stylesheet_update = QtCore.Signal(str) # Передает новый QSS

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(800, 600)
        
        self.setObjectName("RZPreferencesDialog") # Для стилизации
        
        # Main Layout: Horizontal Split
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- LEFT: Sidebar ---
        self.sidebar_container = QtWidgets.QWidget()
        self.sidebar_layout = QtWidgets.QVBoxLayout(self.sidebar_container)
        self.sidebar_layout.setContentsMargins(0, 10, 0, 10)
        self.sidebar_layout.setSpacing(2)
        self.sidebar_layout.setAlignment(QtCore.Qt.AlignTop)
        
        # --- RIGHT: Content Stack ---
        self.content_stack = QtWidgets.QStackedWidget()
        
        # Добавляем на лейаут
        main_layout.addWidget(self.sidebar_container, 1) # Stretch 1
        main_layout.addWidget(self.content_stack, 3)     # Stretch 3
        
        # Setup Panels
        self._setup_panels()
        
        # Apply initial theme
        self.update_style()

    def _setup_panels(self):
        # 1. Appearance
        self.panel_appearance = RZAppearancePanel(self)
        self.panel_appearance.theme_changed_signal.connect(self._on_theme_changed_internal)
        self._add_tab("Appearance", self.panel_appearance)
        
        # 2. Keymap (Reusing existing widget)
        self.panel_keymap = RZKeymapPanel(self)
        self._add_tab("Keybinding", self.panel_keymap)
        
        # 3. Dummy Tabs
        self._add_tab("System", QtWidgets.QLabel("System settings placeholder..."))
        self._add_tab("Add-ons", QtWidgets.QLabel("Add-ons manager placeholder..."))
        
        # Select first
        if self.sidebar_layout.count() > 0:
            self.sidebar_layout.itemAt(0).widget().setChecked(True)
            self.content_stack.setCurrentIndex(0)

    def _add_tab(self, name, widget):
        btn = RZSidebarItem(name, parent=self.sidebar_container)
        
        # Logic to switch stack
        index = self.content_stack.addWidget(widget)
        btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(index))
        
        self.sidebar_layout.addWidget(btn)

    def _on_theme_changed_internal(self):
        """
        Called when Appearance panel changes the theme.
        Generates new QSS and forces a deep, aggressive update of all widgets.
        """
        # 1. IMPORTANT: Update the container styles (sidebar & content stack bg)
        # This was missing in previous iterations, causing the background to stay old
        self.update_style()

        # 2. Update Sidebar Items (Custom logic for checked state)
        for i in range(self.sidebar_layout.count()):
            w = self.sidebar_layout.itemAt(i).widget()
            if isinstance(w, RZSidebarItem):
                w.setStyleSheet(w._get_style(w.isChecked()))

        # 3. Deep Aggressive Update for all Inner Widgets
        # We search for ALL widgets to ensure we hit nested layouts/stack pages
        all_widgets = self.findChildren(QtWidgets.QWidget)

        for widget in all_widgets:
            # Skip the sidebar items as we handled them above
            if isinstance(widget, RZSidebarItem):
                continue

            # Check for our custom 'apply_theme' method (Duck Typing)
            # This covers RZGroupBox, RZLabel, RZComboBox, RZLineEdit, etc.
            if hasattr(widget, 'apply_theme') and callable(widget.apply_theme):
                widget.apply_theme()
                
                # FORCE Qt to un-cache the style for this widget
                widget.style().unpolish(widget)
                widget.style().polish(widget)

            # Special handling for RZSmartSlider (Composite widget)
            if hasattr(widget, 'spin') and hasattr(widget, 'label') and hasattr(widget, 'apply_theme'):
                widget.apply_theme()

        # 4. Emit signal to main window to update the rest of the app
        new_qss = generate_stylesheet() # Ensure we send the fresh QSS
        self.req_global_stylesheet_update.emit(new_qss)

    def update_style(self):
        t = get_current_theme()
        # Specific styling for the preferences container
        self.sidebar_container.setStyleSheet(f"background-color: {t['bg_input']}; border-right: 1px solid {t['border_main']};")
        self.content_stack.setStyleSheet(f"background-color: {t['bg_root']};")
        
        # Re-apply global stylesheet to this dialog
        self.setStyleSheet(generate_stylesheet())