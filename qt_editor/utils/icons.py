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
        # Priority 3: System base icons
        self.base_icons_dir = os.path.join(rzmenu_root, "base_icons")
        print(f"[IconsDebug] IconManager Init: icons_dir={self.icons_dir}, base_icons_dir={self.base_icons_dir}")
        self._cache = {}

    def _get_custom_icons_dir(self) -> str:
        """Query Blender for the custom asset library path from Addon Preferences."""
        import bpy
        try:
            addon_name = __package__.split(".")[0] if "." in __package__ else "RZMenu"
            prefs = bpy.context.preferences.addons.get(addon_name)
            if prefs:
                prefs = prefs.preferences
                val = getattr(prefs, "custom_asset_library", "")
                print(f"[IconsDebug] Custom Library from Prefs: '{val}'")
                return val
        except Exception as e:
            print(f"[IconsDebug] Error reading preferences: {e}")
        return ""

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = IconManager()
        return cls._instance

    def _find_path(self, name: str) -> str:
        """Smarter path discovery for icons, handling prefixes, extensions, and custom dirs."""
        search_dirs = []
        # Priority 1: modern resources
        if os.path.exists(self.icons_dir):
            search_dirs.append(self.icons_dir)
        
        # Priority 2: user custom directory
        custom_dir = self._get_custom_icons_dir()
        if custom_dir and os.path.isdir(custom_dir):
            search_dirs.append(custom_dir)
            
        # Priority 3: legacy base_icons
        if os.path.exists(self.base_icons_dir):
            search_dirs.append(self.base_icons_dir)

        supported_exts = [".svg", ".png", ".dds", ".jpg", ".jpeg", ".tga", ".bmp"]

        for d in search_dirs:
            # Exact match first
            for ext in supported_exts:
                path = os.path.join(d, f"{name}{ext}")
                if os.path.exists(path): return path
            
            # Pattern match: [number]_[name]
            try:
                files = os.listdir(d)
                for f in files:
                    if "_" in f:
                        parts = f.split("_", 1)
                        if len(parts) > 1:
                            fn_no_ext, ext = os.path.splitext(parts[1])
                            if fn_no_ext == name and ext.lower() in supported_exts:
                                return os.path.join(d, f)
            except OSError:
                continue
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

