# RZMenu/qt_editor/conf/defaults.py

DEFAULT_CONFIG = {
    "system": {
        "version": "2.1.0",
        "ui_scale": 1.0,
    },
    "theme_fallback": {
        "bg_dark": "#1d1d1d",
        "bg_panel": "#2b2b2b",
        "text_main": "#e0e0e0",
        "text_dim": "#888888",
        "accent": "#4772b3",
        "accent_hover": "#588cc7",
        "active_border": "#ffae00",
        "danger": "#cc3333",
        "selection": "#405560"
    },
    "keymaps": {
        # Глобальные (работают везде, если не перекрыты)
        "GLOBAL": {
            "Ctrl+Z": "rzm.undo",
            "Ctrl+Shift+Z": "rzm.redo",
            "F5": "rzm.refresh"
        },
        # Контекст Вьюпорта
        "VIEWPORT": {
            "Delete": "rzm.delete",
            "Ctrl+A": "rzm.select_all",
            "Home": "rzm.view_reset",
            "H": "rzm.toggle_hide",
            "Alt+H": "rzm.unhide_all",
            # Пример сложного биндинга (оператор + аргументы)
            "L": {"op": "rzm.toggle_lock", "args": {}}, 
            
            # Навигация стрелками (сдвиг элементов)
            "Left":  {"op": "rzm.nudge", "args": {"x": -10, "y": 0}},
            "Right": {"op": "rzm.nudge", "args": {"x": 10, "y": 0}},
            "Up":    {"op": "rzm.nudge", "args": {"x": 0, "y": -10}}, 
            "Down":  {"op": "rzm.nudge", "args": {"x": 0, "y": 10}},
            
            # Навигация с Shift (сдвиг по 1 пикселю)
            "Shift+Left":  {"op": "rzm.nudge", "args": {"x": -1, "y": 0}},
            "Shift+Right": {"op": "rzm.nudge", "args": {"x": 1, "y": 0}},
            "Shift+Up":    {"op": "rzm.nudge", "args": {"x": 0, "y": -1}}, 
            "Shift+Down":  {"op": "rzm.nudge", "args": {"x": 0, "y": 1}}
        },
        # Контекст Аутлайнера
        "OUTLINER": {
            "Delete": "rzm.delete",
            "Ctrl+A": "rzm.select_all",
            "H": "rzm.toggle_hide",
            "Alt+H": "rzm.unhide_all"
        },
        # Контекст Инспектора
        "INSPECTOR": {
            # Тут можно добавить copy/paste свойств в будущем
        }
    }
}