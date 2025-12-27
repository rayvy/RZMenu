import bpy
from PySide6 import QtWidgets, QtCore

class InspectorWidget(QtWidgets.QWidget):
    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.current_element_id = None
        
        # Main Layout
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)
        
        # Title
        title = QtWidgets.QLabel("INSPECTOR")
        title.setStyleSheet("font-weight: bold; color: #aaaaaa;")
        title.setAlignment(QtCore.Qt.AlignCenter)
        self.main_layout.addWidget(title)
        
        # Content Area (Stacked allows switching between 'No Selection' and 'Form')
        self.content_stack = QtWidgets.QStackedWidget()
        self.main_layout.addWidget(self.content_stack)
        
        # Page 1: Empty State
        self.page_empty = QtWidgets.QLabel("No Selection")
        self.page_empty.setAlignment(QtCore.Qt.AlignCenter)
        self.page_empty.setStyleSheet("color: #666;")
        self.content_stack.addWidget(self.page_empty)
        
        # Page 2: Properties Form
        self.page_form_widget = QtWidgets.QWidget()
        self.form_layout = QtWidgets.QFormLayout(self.page_form_widget)
        self.form_layout.setLabelAlignment(QtCore.Qt.AlignRight)
        
        # --- Form Fields ---
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Element Name")
        # Connect signal
        self.name_edit.textEdited.connect(self.on_name_changed)
        
        self.form_layout.addRow("Name:", self.name_edit)
        
        self.content_stack.addWidget(self.page_form_widget)
        
        # Spacer at bottom to push content up
        self.main_layout.addStretch()

    def set_selection(self, element_id):
        """
        Called by MainWindow when selection changes in the Viewport.
        """
        self.current_element_id = element_id
        
        if element_id is None:
            self.content_stack.setCurrentWidget(self.page_empty)
            return

        # Fetch current data from Blender (Read-only access)
        # We need to find the element to populate the UI initially
        target = None
        if hasattr(bpy.context.scene, "rzm"):
            for el in bpy.context.scene.rzm.elements:
                if el.id == element_id:
                    target = el
                    break
        
        if target:
            # Block signals to prevent sending updates back to Blender while populating
            self.name_edit.blockSignals(True)
            self.name_edit.setText(target.element_name)
            self.name_edit.blockSignals(False)
            
            self.content_stack.setCurrentWidget(self.page_form_widget)
        else:
            # Element ID was valid but not found in Blender (deleted?)
            self.content_stack.setCurrentWidget(self.page_empty)

    def on_name_changed(self, text):
        """Send update to Blender via Bridge."""
        if self.current_element_id is not None:
            self.bridge.enqueue_update_property(
                self.current_element_id, 
                "element_name", 
                text
            )