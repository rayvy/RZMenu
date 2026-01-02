# RZMenu/qt_editor/widgets/lib/theming/manager.py
from . import definitions
from .generator import generate_qss

class ThemeManager:
    """
    Modular Theme Manager. 
    Handles retrieval of theme data and stylesheet generation.
    """
    
    def __init__(self):
        # Initial hardcoded themes from definitions.py
        self._themes = {
            "dark": definitions.THEME_DARK,
            "light": definitions.THEME_LIGHT,
            "blue": definitions.THEME_BLUE,
        }

    def get_available_themes(self) -> list:
        """Returns a list of available theme identifiers."""
        return list(self._themes.keys())

    def get_theme(self, name: str) -> dict:
        """
        Returns the theme dictionary for the given name.
        Falls back to 'dark' if the name is not found.
        """
        return self._themes.get(name, self._themes.get("dark"))

    def generate_stylesheet(self, name: str) -> str:
        """
        Generates a QSS string for the specified theme name.
        """
        theme_dict = self.get_theme(name)
        return generate_qss(theme_dict)

