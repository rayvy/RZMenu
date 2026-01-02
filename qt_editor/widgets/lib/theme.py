# RZMenu/qt_editor/widgets/lib/theme.py
from ...utils import logger
from ...conf import get_config

# -----------------------------------------------------------------------------
# Theme Dictionaries (Палитры остаются без изменений)
# -----------------------------------------------------------------------------

THEME_DARK = {
    "name": "Default Dark",
    
    # Base
    "bg_root": "#20232A",
    "bg_panel": "#2C313A",
    "bg_header": "#3A404A",
    "bg_input": "#252930",
    
    # Text
    "text_main": "#E0E2E4",
    "text_dark": "#9DA5B4",
    "text_disabled": "#6A717C",
    "text_bright": "#FFFFFF",
    
    # Borders
    "border_main": "#3A404A",
    "border_input": "#4A505A",
    "border_contrast": "#5F6672",
    
    # Accents
    "accent": "#5298D4",
    "accent_hover": "#6AACDE",
    "accent_text": "#FFFFFF",
    
    # Special
    "selection": "#4A6E91",
    "warning": "#FFB86C",
    "error": "#FF5555",
    "success": "#50FA7B",
    
    # --- Viewport Specific ---
    "vp_bg": "#1E1E1E",
    "vp_selection": "#FFFFFF",
    "vp_active": "#FF8C00",
    "vp_locked": "#FF3232",
    "vp_handle": "#FFFFFF",
    "vp_handle_border": "#000000",
    "vp_type_container": "rgba(60, 60, 60, 200)",
    "vp_type_grid_container": "rgba(50, 50, 55, 200)",
    "vp_type_button": "rgba(70, 90, 110, 255)",
    "vp_type_slider": "rgba(70, 110, 90, 255)",
    "vp_type_anchor": "rgba(255, 0, 0, 100)",
    "vp_type_text": "rgba(0, 0, 0, 0)",

    # Context Colors (for footer, etc)
    "ctx_viewport": "#4772b3",
    "ctx_outliner": "#ffae00",
    "ctx_inspector": "#44aa44",
    "ctx_header": "#cc88cc",
    "ctx_footer": "#88cccc",
    
    # Debug
    "debug_bg": "rgba(0, 0, 0, 200)",
    "debug_border": "#00ff00",
    "debug_text": "#00ff00",
}

THEME_LIGHT = {
    "name": "Default Light",

    # Base (смещены в сторону холодного серо-голубого)
    "bg_root": "#F0F4F8",       # Мягкий светло-голубой фон
    "bg_panel": "#FFFFFF",      # Чистый белый для панелей для контраста
    "bg_header": "#E1E8EE",     # Светло-серый хедер
    "bg_input": "#F7F9FB",      # Очень светлый инпут

    # Text (менее контрастный черный)
    "text_main": "#2C3E50",     # Темно-синий/серый вместо черного
    "text_dark": "#546E7A",     # Мягкий серый
    "text_disabled": "#B0BEC5",
    "text_bright": "#2C3E50",   # В светлой теме bright текст темный

    # Borders
    "border_main": "#CFD8DC",
    "border_input": "#DDE3EA",
    "border_contrast": "#B0BEC5",

    # Accents
    "accent": "#29B6F6",        # Свежий голубой
    "accent_hover": "#4FC3F7",
    "accent_text": "#FFFFFF",

    # Special
    "selection": "#B3E5FC",     # Светло-голубое выделение
    "warning": "#FFB74D",
    "error": "#E57373",
    "success": "#81C784",

    # --- Viewport Specific ---
    "vp_bg": "#CFD8DC",         # Нейтральный фон вьюпорта
    "vp_selection": "#0288D1",
    "vp_active": "#29B6F6",
    "vp_locked": "#D32F2F",
    "vp_handle": "#FFFFFF",
    "vp_handle_border": "#0288D1",

    # Полупрозрачные цвета для элементов во вьюпорте
    "vp_type_container": "rgba(255, 255, 255, 200)",
    "vp_type_grid_container": "rgba(245, 245, 250, 200)",
    "vp_type_button": "rgba(225, 245, 254, 255)",
    "vp_type_slider": "rgba(224, 242, 241, 255)",
    "vp_type_anchor": "rgba(239, 83, 80, 100)",
    "vp_type_text": "rgba(0, 0, 0, 0)",

    # Context Colors
    "ctx_viewport": "#29B6F6",
    "ctx_outliner": "#FFA726",
    "ctx_inspector": "#66BB6A",
    "ctx_header": "#AB47BC",
    "ctx_footer": "#26C6DA",

    # Debug
    "debug_bg": "rgba(255, 255, 255, 220)",
    "debug_border": "#29B6F6",
    "debug_text": "#01579B",
}

THEME_BLUE = {
    "name": "Blue Theme",

    # Base
    "bg_root": "#1A1F2E",
    "bg_panel": "#2A3441",
    "bg_header": "#3A4551",
    "bg_input": "#1E2530",

    # Text
    "text_main": "#E8ECF0",
    "text_dark": "#A8B3C1",
    "text_disabled": "#647085",
    "text_bright": "#FFFFFF",

    # Borders
    "border_main": "#4A5561",
    "border_input": "#5A6571",
    "border_contrast": "#6A7581",

    # Accents
    "accent": "#4FC3F7",
    "accent_hover": "#81D4FA",
    "accent_text": "#FFFFFF",

    # Special
    "selection": "#4A6FA5",
    "warning": "#FFD54F",
    "error": "#E57373",
    "success": "#81C784",

    # --- Viewport Specific ---
    "vp_bg": "#0F1419",
    "vp_selection": "#FFFFFF",
    "vp_active": "#4FC3F7",
    "vp_locked": "#E57373",
    "vp_handle": "#FFFFFF",
    "vp_handle_border": "#000000",
    "vp_type_container": "rgba(40, 50, 70, 200)",
    "vp_type_grid_container": "rgba(30, 40, 55, 200)",
    "vp_type_button": "rgba(50, 70, 90, 255)",
    "vp_type_slider": "rgba(50, 90, 70, 255)",
    "vp_type_anchor": "rgba(255, 0, 0, 100)",
    "vp_type_text": "rgba(0, 0, 0, 0)",

    # Context Colors
    "ctx_viewport": "#4FC3F7",
    "ctx_outliner": "#FFD54F",
    "ctx_inspector": "#81C784",
    "ctx_header": "#BA68C8",
    "ctx_footer": "#4DD0E1",

    # Debug
    "debug_bg": "rgba(0, 0, 0, 200)",
    "debug_border": "#4FC3F7",
    "debug_text": "#4FC3F7",
}


# -----------------------------------------------------------------------------
# Theme Manager Class
# -----------------------------------------------------------------------------

class ThemeManager:
    """
    Stateless manager. Colors are retrieved based on the Global Config.
    """
    
    def __init__(self):
        self._themes = {
            "dark": THEME_DARK,
            "light": THEME_LIGHT,
            "blue": THEME_BLUE,
        }

    def set_theme(self, name: str):
        """Deprecated for direct use. Use ConfigManager.set_value instead."""
        pass 

    def get_theme(self) -> dict:
        """Fetch current theme based on ConfigManager."""
        cfg = get_config()
        # Safe access to nested dict
        theme_name = cfg.get("appearance", {}).get("theme", "dark")
        return self._themes.get(theme_name, self._themes["dark"])

    def generate_stylesheet(self) -> str:
        """Generates a full QSS string based on the CURRENT config theme."""
        t = self.get_theme()
        
        return f"""
        /* --- Root & Panels --- */
        QWidget, QDialog {{
            background-color: {t['bg_root']};
            color: {t['text_main']};
            font-family: sans-serif; 
            font-size: 10pt;
        }}
        
        #RZMEditorWindow {{
            background-color: {t['bg_root']};
        }}
        
        RZMInspectorPanel, RZMOutlinerPanel, RZViewportPanel {{
            background-color: {t['bg_panel']};
            border: 1px solid {t['border_main']};
            border-radius: 4px;
        }}

        /* --- Groups & Tabs --- */
        QGroupBox {{
            background-color: {t['bg_panel']};
            border: 1px solid {t['border_main']};
            border-radius: 4px;
            margin-top: 6px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 4px;
            left: 10px;
            background-color: {t['bg_panel']};
            color: {t['text_dark']};
        }}
        
        QTabWidget::pane {{
            border: 1px solid {t['border_main']};
            background: {t['bg_panel']};
        }}
        QTabBar::tab {{
            background: {t['bg_root']};
            color: {t['text_dark']};
            padding: 5px 10px;
            border: 1px solid {t['border_main']};
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}
        QTabBar::tab:selected, QTabBar::tab:hover {{
            background: {t['bg_panel']};
            color: {t['text_main']};
        }}

        /* --- Inputs & Controls --- */
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            background-color: {t['bg_input']};
            border: 1px solid {t['border_input']};
            border-radius: 3px;
            padding: 3px;
            color: {t['text_main']};
        }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
            border: 1px solid {t['accent']};
        }}
        QComboBox::drop-down {{
            border-left: 1px solid {t['border_input']};
        }}
        
        /* --- Buttons --- */
        QPushButton {{
            background-color: {t['bg_header']};
            color: {t['text_main']};
            border: 1px solid {t['border_input']};
            border-radius: 3px;
            padding: 4px 10px;
        }}
        QPushButton:hover {{
            background-color: {t['accent_hover']};
            color: {t['accent_text']};
        }}
        QPushButton:pressed {{
            background-color: {t['accent']};
        }}
        QPushButton:disabled {{
            color: {t['text_disabled']};
            background-color: {t['bg_input']};
        }}
        
        #BtnSpecial {{ /* Example for specific buttons */
            border: none;
            color: {t['text_dark']};
        }}
        
        /* --- Sliders --- */
        RZSmartSlider QPushButton {{
             background: {t['bg_header']};
             border: none;
             padding: 0px;
        }}
         _RZDragLabel {{
            color: {t['text_dark']};
            padding-right: 4px;
         }}

        /* --- Tables & Trees --- */
        QHeaderView::section {{
            background-color: {t['bg_header']};
            padding: 4px;
            border: 1px solid {t['border_main']};
            color: {t['text_dark']};
        }}
        QTableWidget, QTreeWidget {{
            background-color: {t['bg_input']};
            border: 1px solid {t['border_main']};
        }}
        QTableWidget::item, QTreeWidget::item {{
            color: {t['text_main']};
        }}
        QTableWidget::item:selected, QTreeWidget::item:selected {{
            background-color: {t['selection']};
            color: {t['text_bright']};
        }}
        
        /* --- Splitter --- */
        QSplitter::handle {{
            background-color: {t['bg_root']};
        }}
        QSplitter::handle:hover {{
            background-color: {t['accent']};
        }}

        /* --- Scrollbars --- */
        QScrollBar:vertical {{
            border: none;
            background: {t['bg_root']};
            width: 10px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {t['bg_header']};
            min-height: 20px;
            border-radius: 4px;
        }}
        """

# -----------------------------------------------------------------------------
# Singleton Instance
# -----------------------------------------------------------------------------

THEME_MANAGER = ThemeManager()

def get_theme_manager() -> ThemeManager:
    return THEME_MANAGER

def get_current_theme() -> dict:
    return THEME_MANAGER.get_theme()
    
def generate_stylesheet() -> str:
    return THEME_MANAGER.generate_stylesheet()