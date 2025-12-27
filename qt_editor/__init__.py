#RZMenu/qt_editor/__init__.py
import sys
import os
from PySide6 import QtWidgets, QtGui

# Ссылки, чтобы GC не убил окно
_app = None
_window = None

# --- STYLESHEET (Оформление) ---
DARK_THEME_QSS = """
QMainWindow { background-color: #1d1d1d; }
QWidget { color: #eeeeee; font-family: sans-serif; font-size: 13px; }

/* HEADER & FOOTER */
QFrame#TopBar, QFrame#BottomBar { 
    background-color: #2d2d2d; 
    border-top: 1px solid #3d3d3d;
    border-bottom: 1px solid #3d3d3d;
}

/* BUTTONS */
QPushButton {
    background-color: #3d3d3d;
    border: 1px solid #4d4d4d;
    border-radius: 4px;
    padding: 5px 15px;
    margin: 2px;
    color: #cccccc;
}
QPushButton:hover {
    background-color: #4772b3; /* Blender Blue */
    color: white;
    border-color: #5885c9;
}
QPushButton:pressed {
    background-color: #2e4e7e;
}
QPushButton:checked {
    background-color: #4772b3;
    color: white;
}

/* TAB BAR (Bottom) */
QPushButton#ModeTab {
    background-color: transparent;
    border: none;
    border-radius: 0px;
    margin: 0px;
    padding: 8px 20px;
    font-weight: bold;
    color: #888888;
}
QPushButton#ModeTab:hover {
    background-color: #353535;
    color: #eeeeee;
}
QPushButton#ModeTab:checked {
    border-top: 2px solid #4772b3;
    color: #ffffff;
    background-color: #262626;
}
"""

def launch_editor(context):
    global _app, _window
    
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
    
    if not QtWidgets.QApplication.instance():
        _app = QtWidgets.QApplication(sys.argv)
    else:
        _app = QtWidgets.QApplication.instance()
        
    _app.setStyleSheet(DARK_THEME_QSS)
        
    if _window:
        try:
            _window.close()
        except: pass
        
    from .rz_main_window import RZMainWindow
    _window = RZMainWindow(context)
    _window.show()
    
    return _window