import os
from PySide6 import QtWidgets, QtGui, QtCore

class IconManager:
    _instance = None
    
    def __init__(self):
        if IconManager._instance is not None:
            raise Exception("IconManager is a singleton!")
            
        # Path Calculation: 
        # Current file: .../RZMenu/qt_editor/utils/icons.py
        # Need to go up 3 levels to reach RZMenu root
        current_dir = os.path.dirname(os.path.abspath(__file__)) # utils
        qt_editor_dir = os.path.dirname(current_dir) # qt_editor
        rzmenu_root = os.path.dirname(qt_editor_dir) # RZMenu
        
        self.icons_dir = os.path.join(rzmenu_root, "resources", "icons")
        self._cache = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = IconManager()
        return cls._instance

    def get_icon(self, name: str, fallback_sp: QtWidgets.QStyle.StandardPixmap = None) -> QtGui.QIcon:
        """
        Retrieves an icon by name from the resources folder, with a Qt standard fallback.
        :param name: Filename without extension (e.g., 'folder', 'eye')
        :param fallback_sp: Optional Qt StandardPixmap enum for fallback
        """
        if name in self._cache:
            return self._cache[name]

        # 1. Try to load from resources
        icon = None
        for ext in [".svg", ".png"]:
            path = os.path.join(self.icons_dir, f"{name}{ext}")
            if os.path.exists(path):
                icon = QtGui.QIcon(path)
                break

        # 2. If missing, use fallback or default question mark
        if not icon or icon.isNull():
            style = QtWidgets.QApplication.style()
            if fallback_sp is not None:
                icon = style.standardIcon(fallback_sp)
            else:
                icon = style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxQuestion)

        self._cache[name] = icon
        return icon

