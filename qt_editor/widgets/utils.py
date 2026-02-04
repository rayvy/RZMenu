# RZMenu/qt_editor/widgets/utils.py
from PySide6 import QtWidgets

def find_action_manager(widget: QtWidgets.QWidget):
    """
    Find the RZActionManager by traversing up to the main window.
    Returns None if not found.
    """
    # 0. Try explicit parent_window attribute if exists
    if hasattr(widget, "parent_window") and widget.parent_window:
        if hasattr(widget.parent_window, "action_manager"):
            return widget.parent_window.action_manager

    curr = widget
    while curr:
        if hasattr(curr, 'action_manager') and curr.action_manager:
            return curr.action_manager
        
        parent = curr.parent()
        if parent is None:
            # Check if this top-level widget has it
            if hasattr(curr, 'action_manager'):
                return curr.action_manager
            break
        curr = parent
    
    # Fallback: try window() method
    try:
        win = widget.window()
        if win and hasattr(win, 'action_manager'):
            return win.action_manager
    except:
        pass
    
    return None
