# RZMenu/qt_editor/widgets/lib/theming/definitions.py

THEME_DARK = {
    "name": "Default Dark",
    
    # Base
    "bg_root": "#20232A",
    "bg_panel": "#2C313A",
    "bg_header": "#3A404A",
    "bg_input": "#252930",
    "bg_scope": "Unified",
    
    # --- Background Settings (Step 5 New) ---
    "bg_type": "solid",       # solid, image
    "bg_image": "",
    "bg_fit": "Cover",        # Cover, Contain, Stretch, Tile
    "panel_opacity": 1.0,     # 0.0 - 1.0 (Glass Effect)
    "overlay_color": "#000000", # Цвет тонировки (пока используется для затемнения панелей)
    "overlay_opacity": 0.0,     # Сила тонировки

    # Text
    "text_main": "#E0E2E4",
    "text_dark": "#9DA5B4",
    "text_disabled": "#6A717C",
    "text_bright": "#FFFFFF",
    
    # Borders
    "border_main": "#3A404A",
    "border_input": "#4A505A",
    "border_contrast": "#5F6672",
    
    # Accents
    "accent": "#5298D4",
    "accent_hover": "#6AACDE",
    "accent_text": "#FFFFFF",
    
    # Special
    "selection": "#4A6E91",
    "warning": "#FFB86C",
    "error": "#FF5555",
    "success": "#50FA7B",
    
    # --- Viewport Specific ---
    "vp_bg": "#1E1E1E",
    "vp_selection": "#FFFFFF",
    "vp_active": "#FF8C00",
    "vp_locked": "#FF3232",
    "vp_handle": "#FFFFFF",
    "vp_handle_border": "#000000",
    "vp_type_container": "rgba(60, 60, 60, 200)",
    "vp_type_grid_container": "rgba(50, 50, 55, 200)",
    "vp_type_button": "rgba(70, 90, 110, 255)",
    "vp_type_slider": "rgba(70, 110, 90, 255)",
    "vp_type_anchor": "rgba(255, 0, 0, 100)",
    "vp_type_text": "rgba(0, 0, 0, 0)",

    # Context Colors
    "ctx_viewport": "#4772b3",
    "ctx_outliner": "#ffae00",
    "ctx_inspector": "#44aa44",
    "ctx_header": "#cc88cc",
    "ctx_footer": "#88cccc",
    
    # Debug
    "debug_bg": "rgba(0, 0, 0, 200)",
    "debug_border": "#00ff00",
    "debug_text": "#00ff00",
}

# (Остальные темы LIGHT и BLUE можно оставить как есть, они унаследуют новые ключи через логику менеджера, или можно добавить их туда тоже для чистоты, но для теста достаточно DARK)
THEME_LIGHT = {
    "name": "Default Light",
    "bg_root": "#F0F4F8",
    "bg_panel": "#FFFFFF",
    "bg_header": "#E1E8EE",
    "bg_input": "#F7F9FB",
    "bg_scope": "Unified",
    "bg_fit": "Cover",
    "panel_opacity": 1.0,
    # ... (копируйте остальное из предыдущего файла definitions.py, если нужно, или оставьте как было)
    # Text
    "text_main": "#2C3E50",     
    "text_dark": "#546E7A",     
    "text_disabled": "#B0BEC5",
    "text_bright": "#2C3E50",

    # Borders
    "border_main": "#CFD8DC",
    "border_input": "#DDE3EA",
    "border_contrast": "#B0BEC5",

    # Accents
    "accent": "#29B6F6",        
    "accent_hover": "#4FC3F7",
    "accent_text": "#FFFFFF",

    # Special
    "selection": "#B3E5FC",
    "warning": "#FFB74D",
    "error": "#E57373",
    "success": "#81C784",

    # --- Viewport Specific ---
    "vp_bg": "#CFD8DC",         
    "vp_selection": "#0288D1",
    "vp_active": "#29B6F6",
    "vp_locked": "#D32F2F",
    "vp_handle": "#FFFFFF",
    "vp_handle_border": "#0288D1",

    "vp_type_container": "rgba(255, 255, 255, 200)",
    "vp_type_grid_container": "rgba(245, 245, 250, 200)",
    "vp_type_button": "rgba(225, 245, 254, 255)",
    "vp_type_slider": "rgba(224, 242, 241, 255)",
    "vp_type_anchor": "rgba(239, 83, 80, 100)",
    "vp_type_text": "rgba(0, 0, 0, 0)",

    "ctx_viewport": "#29B6F6",
    "ctx_outliner": "#FFA726",
    "ctx_inspector": "#66BB6A",
    "ctx_header": "#AB47BC",
    "ctx_footer": "#26C6DA",

    "debug_bg": "rgba(255, 255, 255, 220)",
    "debug_border": "#29B6F6",
    "debug_text": "#01579B",
}

THEME_BLUE = {
    "name": "Blue Theme",
    "bg_root": "#1A1F2E",
    "bg_panel": "#2A3441",
    "bg_header": "#3A4551",
    "bg_input": "#1E2530",
    "bg_scope": "Unified",
    "bg_fit": "Cover",
    "panel_opacity": 1.0,
    # ... (аналогично)
    # Text
    "text_main": "#E8ECF0",
    "text_dark": "#A8B3C1",
    "text_disabled": "#647085",
    "text_bright": "#FFFFFF",

    # Borders
    "border_main": "#4A5561",
    "border_input": "#5A6571",
    "border_contrast": "#6A7581",

    # Accents
    "accent": "#4FC3F7",
    "accent_hover": "#81D4FA",
    "accent_text": "#FFFFFF",

    # Special
    "selection": "#4A6FA5",
    "warning": "#FFD54F",
    "error": "#E57373",
    "success": "#81C784",

    # --- Viewport Specific ---
    "vp_bg": "#0F1419",
    "vp_selection": "#FFFFFF",
    "vp_active": "#4FC3F7",
    "vp_locked": "#E57373",
    "vp_handle": "#FFFFFF",
    "vp_handle_border": "#000000",
    "vp_type_container": "rgba(40, 50, 70, 200)",
    "vp_type_grid_container": "rgba(30, 40, 55, 200)",
    "vp_type_button": "rgba(50, 70, 90, 255)",
    "vp_type_slider": "rgba(50, 90, 70, 255)",
    "vp_type_anchor": "rgba(255, 0, 0, 100)",
    "vp_type_text": "rgba(0, 0, 0, 0)",

    "ctx_viewport": "#4FC3F7",
    "ctx_outliner": "#FFD54F",
    "ctx_inspector": "#81C784",
    "ctx_header": "#BA68C8",
    "ctx_footer": "#4DD0E1",

    "debug_bg": "rgba(0, 0, 0, 200)",
    "debug_border": "#4FC3F7",
    "debug_text": "#4FC3F7",
}