# qt_editor/conf/defaults.py

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
            # Умные стрелки (Move Object OR Pan View)
            "Left":  {"op": "rzm.viewport_arrow", "args": {"x": -10, "y": 0}},
            "Right": {"op": "rzm.viewport_arrow", "args": {"x": 10, "y": 0}},
            "Up":    {"op": "rzm.viewport_arrow", "args": {"x": 0, "y": -10}}, # Y вверх в Qt отрицательный (обычно)
            "Down":  {"op": "rzm.viewport_arrow", "args": {"x": 0, "y": 10}}
        },
        # Контекст Аутлайнера
        "OUTLINER": {
            "Delete": "rzm.delete",
            "Ctrl+A": "rzm.select_all"
        },
        # Контекст Инспектора
        "INSPECTOR": {
            # Тут можно добавить copy/paste свойств
        }
    }
}