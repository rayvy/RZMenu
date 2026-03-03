import os
from PySide6 import QtWidgets, QtGui, QtCore

class IconManager:
    _instance = None
    
    def __init__(self):
        if IconManager._instance is not None:
            raise Exception("IconManager is a singleton!")
            
        current_dir = os.path.dirname(os.path.abspath(__file__)) # utils
        qt_editor_dir = os.path.dirname(current_dir) # qt_editor
        rzmenu_root = os.path.dirname(qt_editor_dir) # RZMenu
        
        # Priority 1: Modern resources (if exists)
        self.icons_dir = os.path.join(rzmenu_root, "resources", "icons")
        # Priority 2: System base icons
        self.base_icons_dir = os.path.join(rzmenu_root, "base_icons")
        
        self._cache = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = IconManager()
        return cls._instance

    def _find_path(self, name: str) -> str:
        """Smarter path discovery for icons, handling prefixes and extensions."""
        # 1. Search in modern icons_dir
        if os.path.exists(self.icons_dir):
            for ext in [".svg", ".png"]:
                path = os.path.join(self.icons_dir, f"{name}{ext}")
                if os.path.exists(path): return path

        # 2. Search in base_icons_dir with smart prefix matching
        if os.path.exists(self.base_icons_dir):
            # Exact match first
            for ext in [".svg", ".png"]:
                path = os.path.join(self.base_icons_dir, f"{name}{ext}")
                if os.path.exists(path): return path
            
            # Pattern match: [number]_[name]
            files = os.listdir(self.base_icons_dir)
            for f in files:
                if "_" in f:
                    parts = f.split("_", 1)
                    if len(parts) > 1:
                        fn_no_ext = os.path.splitext(parts[1])[0]
                        if fn_no_ext == name:
                            return os.path.join(self.base_icons_dir, f)
        return None

    def get_icon(self, name: str, fallback_sp: QtWidgets.QStyle.StandardPixmap = None) -> QtGui.QIcon:
        if name in self._cache:
            return self._cache[name]

        path = self._find_path(name)
        if path:
            icon = QtGui.QIcon(path)
        else:
            style = QtWidgets.QApplication.style()
            if fallback_sp is not None:
                icon = style.standardIcon(fallback_sp)
            else:
                icon = style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxQuestion)

        self._cache[name] = icon
        return icon

