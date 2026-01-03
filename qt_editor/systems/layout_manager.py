# qt_editor/systems/layout_manager.py

import json
import os
from PySide6 import QtWidgets, QtCore

from ..widgets.area import RZAreaWidget
from ..conf.manager import ConfigManager

# Default layout structure matching the original hardcoded window
# Horizontal Splitter: [Outliner (200), Viewport (600), Inspector (300)]
DEFAULT_LAYOUT = {
    "type": "SPLITTER",
    "orientation": 1, # Qt.Horizontal
    "sizes": [200, 600, 300],
    "children": [
        {"type": "AREA", "panel_id": "OUTLINER"},
        {"type": "AREA", "panel_id": "VIEWPORT"},
        {"type": "AREA", "panel_id": "INSPECTOR"}
    ]
}

class LayoutManager:
    FILENAME = "layouts.json"

    def __init__(self):
        self.user_layouts = {}
        self.load_user_layouts()

    def get_layout_names(self):
        """Return list of available layout names."""
        names = ["Default"] + list(self.user_layouts.keys())
        return names

    def get_layout_data(self, name):
        """Get data for a specific layout."""
        if name == "Default":
            return DEFAULT_LAYOUT
        return self.user_layouts.get(name, DEFAULT_LAYOUT)

    # -------------------------------------------------------------------------
    # SERIALIZATION (Save)
    # -------------------------------------------------------------------------
    def get_layout_state(self, widget) -> dict:
        """
        Recursively serialize a widget tree (Splitters and Areas).
        """
        if isinstance(widget, RZAreaWidget):
            return {
                "type": "AREA",
                "panel_id": widget.get_current_panel_id()
            }
        
        elif isinstance(widget, QtWidgets.QSplitter):
            # Collect children
            children_data = []
            for i in range(widget.count()):
                child = widget.widget(i)
                if child:
                    children_data.append(self.get_layout_state(child))
            
            return {
                "type": "SPLITTER",
                "orientation": int(widget.orientation().value),
                "sizes": widget.sizes(),
                "children": children_data
            }
        
        return None

    def save_layout(self, name, root_widget):
        """Save current widget tree as a named layout."""
        if not root_widget:
            return
            
        layout_data = self.get_layout_state(root_widget)
        if layout_data:
            self.user_layouts[name] = layout_data
            self._save_to_disk()

    # -------------------------------------------------------------------------
    # DESERIALIZATION (Load)
    # -------------------------------------------------------------------------
    def build_layout(self, data):
        """
        Recursively reconstruct QSplitter/RZAreaWidget tree from dict.
        """
        if not data:
            return RZAreaWidget(initial_panel_id="OUTLINER")

        w_type = data.get("type")

        if w_type == "AREA":
            panel_id = data.get("panel_id", "OUTLINER")
            return RZAreaWidget(initial_panel_id=panel_id)

        elif w_type == "SPLITTER":
            orientation = QtCore.Qt.Orientation(data.get("orientation", 1))
            splitter = QtWidgets.QSplitter(orientation)
            
            children = data.get("children", [])
            for child_data in children:
                child_widget = self.build_layout(child_data)
                if child_widget:
                    splitter.addWidget(child_widget)
            
            # Restore sizes
            sizes = data.get("sizes", [])
            if sizes and len(sizes) == len(children):
                splitter.setSizes(sizes)
                
            return splitter
            
        # Fallback
        return RZAreaWidget(initial_panel_id="OUTLINER")

    # -------------------------------------------------------------------------
    # FILE I/O
    # -------------------------------------------------------------------------
    def _get_file_path(self):
        user_dir = ConfigManager.get_user_dir()
        if user_dir:
            return os.path.join(user_dir, self.FILENAME)
        return None

    def load_user_layouts(self):
        """Load layouts from JSON file."""
        path = self._get_file_path()
        if path and os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.user_layouts = json.load(f)
            except Exception as e:
                print(f"Error loading layouts: {e}")
                self.user_layouts = {}

    def _save_to_disk(self):
        """Write layouts to JSON file."""
        path = self._get_file_path()
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(self.user_layouts, f, indent=4)
            except Exception as e:
                print(f"Error saving layouts: {e}")