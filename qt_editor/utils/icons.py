import os
import re
from PySide6 import QtWidgets, QtGui, QtCore, QtSvg

class IconManager:
    _instance = None
    
    def __init__(self):
        if IconManager._instance is not None:
            raise Exception("IconManager is a singleton!")
            
        current_dir = os.path.dirname(os.path.abspath(__file__)) # utils
        qt_editor_dir = os.path.dirname(current_dir) # qt_editor
        rzmenu_root = os.path.dirname(qt_editor_dir) # RZMenu
        
        # Priority 1: Modern SVG resources
        self.icons_svg_dir = os.path.join(rzmenu_root, "resources", "icons_svg")
        # Priority 2: Standard icon resources
        self.icons_dir = os.path.join(rzmenu_root, "resources", "icons")
        # Priority 3: Legacy base icons
        self.base_icons_dir = os.path.join(rzmenu_root, "base_icons")
        
        self._cache = {}
        self._svg_cache = {} # Cache for tinted SVGs: (name, color_hex) -> QIcon

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = IconManager()
        return cls._instance

    def _get_theme_color(self, color_key: str) -> str:
        """Helper to get hex color from the current theme."""
        # Simple fallback if theme system is not accessible here
        from ..widgets.lib.theme import get_current_theme
        t = get_current_theme()
        return t.get(color_key, "#FFFFFF")

    def get_icon(self, name: str, color: str = None, size: int = 24) -> QtGui.QIcon:
        """
        Get icon by name. If color is provided (hex or theme key like 'accent'), 
        and the icon is an SVG, it will be dynamically tinted.
        If color is None, automatically uses 'icon_color' from the current theme.
        Pass color='RAW' to skip auto-tinting and get the original icon.
        """
        # Auto-apply theme icon_color when no explicit color given
        if color is None:
            color = self._get_theme_color('icon_color')
        elif color == 'RAW':
            color = None
        
        # Resolve theme key to hex 
        elif not color.startswith('#'):
            color = self._get_theme_color(color)
        
        cache_key = (name, color)
        if cache_key in self._svg_cache:
            return self._svg_cache[cache_key]

        # 1. Try to find SVG first for best quality
        svg_path = os.path.join(self.icons_svg_dir, f"{name}.svg")
        if not os.path.exists(svg_path):
            # Try with -fill suffix if using Phosphor fill icons
            svg_path = os.path.join(self.icons_svg_dir, f"{name}-fill.svg")

        if os.path.exists(svg_path):
            icon = self._load_svg(svg_path, color, size)
            if icon:
                self._svg_cache[cache_key] = icon
                return icon

        # 2. Fallback to legacy discovery (find_path)
        path = self._find_path(name)
        if path:
            icon = QtGui.QIcon(path)
            self._svg_cache[cache_key] = icon
            return icon

        # 3. Last fallback: System icon
        style = QtWidgets.QApplication.style()
        icon = style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxQuestion)
        return icon

    def _load_svg(self, path: str, color: str, size: int) -> QtGui.QIcon:
        """Loads and optionally tints an SVG file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                svg_data = f.read()

            if color:
                # Tinting logic: 
                # Phosphor icons usually have paths without fill (default black)
                # We inject fill/stroke attributes or replace currentColor if present
                if 'currentColor' in svg_data:
                    svg_data = svg_data.replace('currentColor', color)
                else:
                    # Inject fill into the <svg> tag as a default for all paths
                    svg_data = re.sub(r'<svg([^>]*)>', rf'<svg\1 fill="{color}">', svg_data)

            renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg_data.encode('utf-8')))
            if not renderer.isValid():
                return None

            pixmap = QtGui.QPixmap(size, size)
            pixmap.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(pixmap)
            renderer.render(painter)
            painter.end()

            return QtGui.QIcon(pixmap)
        except Exception as e:
            print(f"[IconManager] Error loading SVG {path}: {e}")
            return None

    def _find_path(self, name: str) -> str:
        search_dirs = [self.icons_dir, self.base_icons_dir]
        supported_exts = [".svg", ".png", ".dds", ".jpg", ".jpeg"]

        for d in search_dirs:
            if not os.path.exists(d): continue
            for ext in supported_exts:
                path = os.path.join(d, f"{name}{ext}")
                if os.path.exists(path): return path
        return None

    def clear_cache(self):
        """Clears the icon cache. Call when the theme changes so icons are re-tinted."""
        self._cache.clear()
        self._svg_cache.clear()

