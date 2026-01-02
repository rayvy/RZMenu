# RZMenu/qt_editor/widgets/lib/theme.py
from .theming import THEME_MANAGER

def get_theme_manager():
    """Returns the singleton ThemeManager instance."""
    return THEME_MANAGER

def get_current_theme():
    """Returns the current active theme dictionary based on global config."""
    return THEME_MANAGER.get_theme()

def generate_stylesheet():
    """Generates the QSS stylesheet for the current active theme."""
    return THEME_MANAGER.generate_stylesheet()
