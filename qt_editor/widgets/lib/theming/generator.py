# RZMenu/qt_editor/widgets/lib/theming/generator.py
import os

def _rgba(hex_color, alpha_override=None):
    """
    Converts HEX to rgba(). 
    """
    if not isinstance(hex_color, str) or not hex_color.startswith("#"):
        return hex_color
    
    color = hex_color.lstrip('#')
    if len(color) == 3:
        color = "".join([c*2 for c in color])
        
    r, g, b, a = 255, 255, 255, 1.0
    
    try:
        if len(color) == 8: # AARRGGBB
            a = int(color[0:2], 16) / 255.0
            r = int(color[2:4], 16)
            g = int(color[4:6], 16)
            b = int(color[6:8], 16)
        elif len(color) == 6: # RRGGBB
            r = int(color[0:2], 16)
            g = int(color[2:4], 16)
            b = int(color[4:6], 16)
            
        if alpha_override is not None:
            a = float(alpha_override)
            
        return f"rgba({r}, {g}, {b}, {a})"
    except:
        return hex_color

def generate_qss(t: dict) -> str:
    # --- 1. SETUP VARS ---
    bg_scope = t.get("bg_scope", "Unified")
    bg_type = t.get("bg_type", "solid")
    bg_root_col = t.get('bg_root', '#20232A')
    
    # Calculate Panel Color with Opacity
    # This acts as the "Tint" or "Glass Color"
    panel_opacity = float(t.get("panel_opacity", 1.0))
    bg_panel_raw = t.get('bg_panel', '#2C313A')
    bg_panel_rgba = _rgba(bg_panel_raw, panel_opacity)
    
    border_main = t.get('border_main', '#3A404A')

    # --- 2. GENERATE BACKGROUND CSS RULES ---
    # This string will be injected either into #RZMEditorWindow (Unified) 
    # OR into #RZMInspectorPanel etc (Individual)
    
    complex_bg_css = ""
    
    if bg_type == "image":
        bg_image = t.get("bg_image", "")
        root_path = t.get("_root_path", "")
        bg_fit = t.get("bg_fit", "Cover") 
        full_bg_path = ""
        
        if bg_image:
            if os.path.isabs(bg_image): clean_path = bg_image
            elif root_path: clean_path = os.path.join(root_path, bg_image)
            else: clean_path = bg_image
            full_bg_path = clean_path.replace("\\", "/")
            
        if full_bg_path:
            if bg_fit in ["Stretch", "Cover"]:
                # Force stretch using border-image
                complex_bg_css = f"""
                    border-image: url("{full_bg_path}") 0 0 0 0 stretch stretch;
                    background-image: none;
                """
            elif bg_fit == "Tile":
                # Strict repeat settings
                complex_bg_css = f"""
                    border-image: none;
                    background-image: url("{full_bg_path}");
                    background-repeat: repeat;
                    background-position: top left;
                    background-origin: content; 
                """
            else: # Contain / Center
                complex_bg_css = f"""
                    border-image: none;
                    background-image: url("{full_bg_path}");
                    background-repeat: no-repeat;
                    background-position: center;
                """

    elif bg_type == "gradient":
        c1 = t.get("bg_grad_1", "#333")
        c2 = t.get("bg_grad_2", "#000")
        direction = t.get("bg_grad_dir", "Vertical")
        
        coords = "x1:0, y1:0, x2:0, y2:1"
        if direction == "Horizontal": coords = "x1:0, y1:0, x2:1, y2:0"
        elif direction == "Diagonal": coords = "x1:0, y1:0, x2:1, y2:1"
        
        complex_bg_css = f"""
            background: qlineargradient(spread:pad, {coords}, stop:0 {c1}, stop:1 {c2}); 
            border-image: none;
        """

    # --- 3. CONSTRUCT SELECTORS ---
    
    # Defaults
    window_bg_rules = f"background-color: {bg_root_col};"
    panel_bg_rules = f"background-color: {bg_panel_rgba};" # Glass by default
    
    if bg_scope == "Unified":
        # Window gets the fancy background
        # Panels get the transparent color
        if bg_type != "solid":
            window_bg_rules = f"""
                background-color: {bg_root_col};
                {complex_bg_css}
            """
            
    else: # Individual Mode
        # Window is solid
        # Panels get the fancy background
        if bg_type != "solid":
            # NOTE: We must ensure children don't inherit this image!
            # We apply it to the ID selector.
            panel_bg_rules = f"""
                background-color: {bg_panel_rgba};
                {complex_bg_css}
            """

    return f"""
    /* --- GLOBAL RESET --- */
    QWidget, QDialog {{
        background-color: {bg_root_col};
        color: {t.get('text_main', '#E0E2E4')};
        font-family: sans-serif; 
        font-size: 10pt;
    }}
    
    /* --- MAIN WINDOW --- */
    #RZMEditorWindow {{
        {window_bg_rules}
    }}

    #RZContextWidget_HEADER {{
        background-color: {t.get('bg_header_main', t.get('bg_header', '#1A1D23'))};
        border-bottom: 1px solid {border_main};
    }}

    #RZContextWidget_FOOTER {{
        background-color: {t.get('bg_footer_main', t.get('bg_header', '#1A1D23'))};
        border-top: 1px solid {border_main};
    }}

    #RZAreaHeader {{
        background-color: {t.get('bg_area_header', t.get('bg_header', '#333842'))};
        border-bottom: 1px solid {border_main};
    }}

    /* --- PANELS --- */
    /* Using specific IDs to prevent leakage */
    #RZMInspectorPanel, #RZMOutlinerPanel, #RZViewportPanel {{
        {panel_bg_rules}
        border: 1px solid {border_main};
        border-radius: 4px;
    }}
    
    /* FIX: Prevent background image inheritance in Individual Mode */
    /* This ensures buttons inside the inspector don't get the background image */
    #RZMInspectorPanel QWidget, #RZMOutlinerPanel QWidget {{
        background-image: none;
        border-image: none;
        background-color: transparent; 
    }}

    /* --- CHILD CONTAINERS (Tabs, Groups) --- */
    /* They need to be transparent to show the panel's background */
    
    QGroupBox {{
        border: 1px solid {border_main};
        border-radius: 4px;
        margin-top: 6px;
        background-color: {_rgba(t.get('bg_panel', '#333'), 0.3)}; /* Slight tint for groups */
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 4px;
        left: 10px;
        background-color: transparent;
        color: {t.get('text_dark', '#999')};
    }}
    
    QTabWidget::pane {{
        border: 1px solid {border_main};
        background-color: transparent; /* Transparent to see panel bg */
    }}
    
    QTabBar::tab {{
        background: {t.get('bg_root', '#222')};
        color: {t.get('text_dark', '#999')};
        padding: 5px 10px;
        border: 1px solid {border_main};
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }}
    QTabBar::tab:selected, QTabBar::tab:hover {{
        background: {bg_panel_rgba};
        color: {t.get('text_main', '#EEE')};
    }}

    /* --- WIDGETS --- */
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {t.get('bg_input', '#252930')};
        border: 1px solid {t.get('border_input', '#444')};
        border-radius: 3px;
        padding: 3px;
        color: {t.get('text_main', '#EEE')};
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border: 1px solid {t.get('accent', '#5298D4')};
    }}
    QComboBox::drop-down {{
        border-left: 1px solid {t.get('border_input', '#444')};
    }}
    
    QPushButton {{
        background-color: {t.get('bg_header', '#3A404A')};
        color: {t.get('text_main', '#EEE')};
        border: 1px solid {t.get('border_input', '#444')};
        border-radius: 3px;
        padding: 4px 10px;
    }}
    QPushButton:hover {{
        background-color: {t.get('accent_hover', '#6AACDE')};
        color: {t.get('accent_text', '#FFF')};
    }}
    QPushButton:pressed {{
        background-color: {t.get('accent', '#5298D4')};
    }}
    QPushButton:disabled {{
        color: {t.get('text_disabled', '#666')};
        background-color: {t.get('bg_input', '#222')};
    }}
    
    #BtnSpecial {{ border: none; color: {t.get('text_dark', '#999')}; }}
    #BtnWarning {{ background-color: {t.get('error', '#FF5555')}; color: {t.get('text_bright', '#FFF')}; }}
    #BtnWarning:hover {{ background-color: {t.get('error', '#FF5555')}; opacity: 0.8; }}
    
    /* Sliders Custom */
    RZSmartSlider QPushButton {{ background: {t.get('bg_header', '#333')}; border: none; padding: 0px; }}
    _RZDragLabel {{ color: {t.get('text_dark', '#999')}; padding-right: 4px; }}

    /* Tables & Trees */
    QHeaderView::section {{
        background-color: {t.get('bg_header', '#333')};
        padding: 4px;
        border: 1px solid {border_main};
        color: {t.get('text_dark', '#999')};
    }}
    QTableWidget, QTreeWidget {{
        background-color: {t.get('bg_input', '#222')}; /* Keep inputs solid usually */
        border: 1px solid {border_main};
    }}
    QTableWidget::item, QTreeWidget::item {{ color: {t.get('text_main', '#EEE')}; }}
    QTableWidget::item:selected, QTreeWidget::item:selected {{
        background-color: {t.get('selection', '#4A6E91')};
        color: {t.get('text_bright', '#FFF')};
    }}
    
    /* Splitter */
    QSplitter::handle {{
        background-color: {t.get('handle_splitter', '#1E2227')};
    }}
    QSplitter::handle:horizontal {{
        width: 4px;
    }}
    QSplitter::handle:vertical {{
        height: 4px;
    }}
    QSplitter::handle:hover {{
        background-color: {t.get('accent', '#5298D4')};
    }}
    
    QScrollBar:vertical {{
        border: none; background: {t.get('bg_root', '#222')}; width: 10px; margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {t.get('bg_header', '#444')}; min-height: 20px; border-radius: 4px;
    }}
    """