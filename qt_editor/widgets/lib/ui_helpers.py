from PySide6 import QtWidgets, QtCore

class ListItemManager:
    """
    Helper class to manage a list of widgets in a layout,
    ensuring non-destructive updates (syncing logic).
    """
    def __init__(self, layout, create_func, update_func, context_provider=None):
        """
        Args:
            layout (QLayout): The layout to manage.
            create_func (callable): Function(index, parent=None) -> QWidget
            update_func (callable): Function(widget, data_item, index)
            context_provider (callable): Optional, returns context/parent data if needed.
        """
        self.layout = layout
        self.create_func = create_func
        self.update_func = update_func
        self.context_provider = context_provider
        
        self.widgets = [] # List of managed widgets

    def _clear_excess(self, target_count):
        while len(self.widgets) > target_count:
            w = self.widgets.pop()
            w.setParent(None)
            w.deleteLater()

    def sync(self, data_list, parent_index=-1):
        """
        Synchronizes the widgets with the data_list.
        
        Args:
            data_list (list): The list of data objects (e.g., from Blender).
            parent_index (int): Optional index of the parent item (for nested lists).
        """
        target_count = len(data_list)
        
        # 1. Clear excess widgets
        self._clear_excess(target_count)
        
        # 2. Add missing widgets
        while len(self.widgets) < target_count:
            idx = len(self.widgets)
            w = self.create_func(idx) # Pass index to creator
            self.layout.addWidget(w)
            self.widgets.append(w)
            
        # 3. Update all widgets
        for i, item in enumerate(data_list):
            widget = self.widgets[i]
            
            # If update_func accepts 4 args, pass parent_index
            # Check signature or just use kwargs? 
            # Let's simplify: pass parent_index if it's not -1, or rely on update_func using a closure/wrapper if needed?
            # Better: Make update_func signature flexible or fixed.
            # Fixed: update_func(widget, item, index, parent_index)
            # But earlier I defined it as 3 args.
            # Let's check signature using inspection or just try/except? No, explicit is better.
            
            # We will use keyword args for flexibility if needed, 
            # but standardization is better.
            # Let's standard on: update_func(widget, item, index, **kwargs)
            self.update_func(widget, item, i, parent_index=parent_index)

class KeyedItemManager:
    """
    Experimental: For when items need to be tracked by a unique ID 
    to preserve state even if reordered.
    """
    pass # TODO if needed
