class ContextManager:
    """Manages the current active tool, selection, and application state."""
    def __init__(self):
        self.active_tool = "Select"
        self.selected_objects = []
        self.active_layer = None
        self.active_document = None

    def set_tool(self, tool_name):
        self.active_tool = tool_name
        print(f"Tool changed to: {tool_name}")

    def select_objects(self, objects):
        self.selected_objects = objects
        # Update inspector etc.
        
    def clear_selection(self):
        self.selected_objects = []
