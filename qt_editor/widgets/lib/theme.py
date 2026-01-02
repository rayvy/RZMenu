# RZMenu/qt_editor/ui/theme.py

import bpy
from ..utils import logger
from ..conf import get_config

def blender_to_hex(color_tuple):
    """Конвертирует (0.1, 0.2, 0.9) -> #1933E5"""
    try:
        # Blender может возвращать 3 (RGB) или 4 (RGBA) канала
        r, g, b = color_tuple[0], color_tuple[1], color_tuple[2]
        return "#{:02x}{:02x}{:02x}".format(
            int(min(1.0, r) * 255),
            int(min(1.0, g) * 255),
            int(min(1.0, b) * 255)
        )
    except Exception:
        return "#ff00ff" # Маджента как индикатор ошибки

def get_current_theme():
    """
    Пытается прочитать активную тему Blender.
    Если не выходит - возвращает fallback из конфига.
    """
    conf = get_config()
    fallback = conf["theme_fallback"]
    
    # Результирующий словарь цветов
    theme = fallback.copy()
    
    try:
        if not bpy.context or not bpy.context.preferences:
            logger.warn("Blender context missing, using fallback theme.")
            return theme

        b_theme = bpy.context.preferences.themes[0]
        ui = b_theme.user_interface

        # --- МАППИНГ ЦВЕТОВ BLENDER -> RZM ---
        
        # Фон редакторов (темно-серый)
        # Обычно wcol_regular.item или outline
        theme["bg_dark"] = blender_to_hex(ui.wcol_regular.outline) # Самый темный
        theme["bg_panel"] = blender_to_hex(ui.wcol_regular.inner)  # Чуть светлее

        # Текст
        theme["text_main"] = blender_to_hex(ui.wcol_text.text)
        theme["text_dim"] = blender_to_hex(ui.wcol_text.text_sel) # Часто серый

        # Акцент (Выделение)
        # Берем из Text Selection Background или Active Item
        theme["accent"] = blender_to_hex(ui.wcol_text.item) 
        theme["accent_hover"] = blender_to_hex(ui.wcol_tool.inner)
        theme["selection"] = blender_to_hex(ui.wcol_list_item.item)

        logger.info("Synced theme with Blender.")

    except Exception as e:
        logger.warn(f"Failed to sync theme: {e}")
    
    return theme

def generate_stylesheet(theme):
    """Генерирует QSS строку для приложения"""
    return f"""
    QWidget {{
        background-color: {theme['bg_dark']};
        color: {theme['text_main']};
        font-family: sans-serif; 
        font-size: 10pt;
    }}
    
    /* Сплиттер (разделитель) */
    QSplitter::handle {{
        background-color: {theme['bg_dark']};
        border: 1px solid {theme['bg_panel']};
    }}
    
    /* Поля ввода */
    QLineEdit {{
        background-color: {theme['bg_panel']};
        border: 1px solid {theme['bg_dark']};
        border-radius: 3px;
        padding: 2px;
        color: {theme['text_main']};
    }}
    QLineEdit:focus {{
        border: 1px solid {theme['accent']};
    }}
    
    /* Кнопки */
    QPushButton {{
        background-color: {theme['bg_panel']};
        border: 1px solid {theme['bg_dark']};
        border-radius: 3px;
        padding: 4px 10px;
    }}
    QPushButton:hover {{
        background-color: {theme['accent']};
        color: white;
    }}
    QPushButton:pressed {{
        background-color: {theme['active_border']};
    }}
    QPushButton:disabled {{
        color: {theme['text_dim']};
        background-color: {theme['bg_dark']};
    }}
    
    /* Скроллбары (попытка стилизовать под Blender) */
    QScrollBar:vertical {{
        border: none;
        background: {theme['bg_dark']};
        width: 10px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {theme['bg_panel']};
        min-height: 20px;
        border-radius: 4px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    """