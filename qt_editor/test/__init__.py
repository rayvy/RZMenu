# RZMenu/qt_editor/test/__init__.py
import sys

# Global reference to prevent garbage collection
_apple_demo_window = None

def run_apple_demo():
    global _apple_demo_window
    from PySide6 import QtWidgets
    from .apple_viewport import AppleMagicWindow
    
    print("\n[RZM] Launching Apple UX Demo...")
    
    # Check if app exists
    app = QtWidgets.QApplication.instance()
    if not app:
        print("[RZM] Creating new QApplication instance.")
        app = QtWidgets.QApplication(sys.argv)
    else:
        print("[RZM] Using existing QApplication instance.")
        
    _apple_demo_window = AppleMagicWindow()
    _apple_demo_window.show()
    _apple_demo_window.raise_() # Bring to front
    _apple_demo_window.activateWindow()
    
    print("[RZM] Demo window is now open.")
    return _apple_demo_window
