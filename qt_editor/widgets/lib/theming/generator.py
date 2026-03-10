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
    
    # Premium Design Tokens
    r_sm = t.get("radius_sm", "4px")
    r_md = t.get("radius_md", "8px")
    r_lg = t.get("radius_lg", "12px")
    
    # Calculate Panel Color with Opacity
    # This acts as the "Tint" or "Glass Color"
    panel_opacity = float(t.get("panel_opacity", 1.0))
    bg_panel_raw = t.get('bg_panel', '#2C313A')
    bg_panel_rgba = _rgba(bg_panel_raw, panel_opacity)
    
    border_main = t.get('border_main', '#3A404A')
    accent = t.get('accent', '#5298D4')
    accent_hover = t.get('accent_hover', '#6AACDE')

    # --- 2. GENERATE BACKGROUND CSS RULES ---
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
                complex_bg_css = f'border-image: url("{full_bg_path}") 0 0 0 0 stretch stretch; background-image: none;'
            elif bg_fit == "Tile":
                complex_bg_css = f'border-image: none; background-image: url("{full_bg_path}"); background-repeat: repeat; background-position: top left; background-origin: content;'
            else: # Contain / Center
                complex_bg_css = f'border-image: none; background-image: url("{full_bg_path}"); background-repeat: no-repeat; background-position: center;'

    elif bg_type == "gradient":
        c1, c2 = t.get("bg_grad_1", "#333"), t.get("bg_grad_2", "#000")
        direction = t.get("bg_grad_dir", "Vertical")
        coords = "x1:0, y1:0, x2:0, y2:1"
        if direction == "Horizontal": coords = "x1:0, y1:0, x2:1, y2:0"
        elif direction == "Diagonal": coords = "x1:0, y1:0, x2:1, y2:1"
        complex_bg_css = f"background: qlineargradient(spread:pad, {coords}, stop:0 {c1}, stop:1 {c2}); border-image: none;"

    # --- 3. CONSTRUCT SELECTORS ---
    window_bg_rules = f"background-color: {bg_root_col};"
    panel_bg_rules = f"background-color: {bg_panel_rgba};" # Glass by default
    
    if bg_scope == "Unified" and bg_type != "solid":
        window_bg_rules = f"background-color: {bg_root_col}; {complex_bg_css}"
    elif bg_scope != "Unified" and bg_type != "solid":
        panel_bg_rules = f"background-color: {bg_panel_rgba}; {complex_bg_css}"
            
    return f"""
    /* --- GLOBAL RESET --- */
    QWidget, QDialog {{
        background-color: {bg_root_col};
        color: {t.get('text_main', '#E0E2E4')};
        font-family: 'Segoe UI', system-ui, sans-serif; 
        font-size: 9pt;
    }}
    
    /* --- MAIN WINDOW --- */
    #RZMEditorWindow {{ {window_bg_rules} }}

    #RZContextWidget_HEADER {{
        background-color: {t.get('bg_header_main', '#1A1D23')};
        border-bottom: 1px solid {border_main};
    }}

    #RZContextWidget_FOOTER {{
        background-color: {t.get('bg_footer_main', '#1A1D23')};
        border-top: 1px solid {border_main};
    }}

    #RZAreaHeader {{
        background-color: {t.get('bg_area_header', '#333842')};
        border-bottom: 1px solid {border_main};
        padding: 0px 4px;
    }}

    /* --- PANELS (Apple-Style Glassy Containers) --- */
    #RZMInspectorPanel, #RZMOutlinerPanel, #RZViewportPanel {{
        {panel_bg_rules}
        border: 1px solid {t.get('border_contrast', '#4A505A')};
        border-radius: {r_md};
    }}
    
    #RZMInspectorPanel QWidget, #RZMOutlinerPanel QWidget {{
        background-image: none;
        border-image: none;
        background-color: transparent; 
    }}

    /* --- GROUP BOXES --- */
    QGroupBox {{
        border: 1px solid {border_main};
        border-radius: {r_sm};
        margin-top: 12px;
        background-color: {_rgba(t.get('bg_panel', '#333'), 0.2)};
        padding: 8px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px;
        left: 12px;
        color: {t.get('text_bright', '#FFF')};
        font-weight: bold;
    }}
    
    /* --- TAB OVERHAUL (Premium Minimal) --- */
    QTabWidget::pane {{
        border: 1px solid {border_main};
        border-radius: {r_sm};
        background-color: transparent;
        top: -1px;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {t.get('text_dark', '#999')};
        padding: 4px 12px;
        margin-right: 4px;
        border-bottom: 2px solid transparent;
    }}
    QTabBar::tab:hover {{
        background: rgba(255, 255, 255, 10);
        color: {t.get('text_main', '#EEE')};
    }}
    QTabBar::tab:selected {{
        color: {accent};
        border-bottom: 2px solid {accent};
        font-weight: bold;
    }}

    /* --- INPUTS & CONTROLS --- */
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit,
    RZLineEdit, RZSpinBox, RZDoubleSpinBox, RZComboBox, 
    _RZSmartSpinBox, _RZSmartDoubleSpinBox, _RZBaseTextEdit,
    RZFormulaInput, RZCodeTextEdit, RZModInfoTextEdit {{
        background-color: {t.get('bg_input', '#252930')};
        border: 1px solid {t.get('border_input', '#4A505A')};
        border-radius: 6px;
        padding: 4px 8px;
        color: {t.get('text_main', '#E0E2E4')};
    }}

    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{
        background-color: {t.get('bg_panel', '#2C313A')};
        border: 1px solid {accent};
    }}

    QComboBox::drop-down {{
        border-left: 1px solid {t.get('border_input', '#4A505A')};
        width: 20px;
    }}

    /* --- CHECKBOX --- */
    QCheckBox, RZCheckBox {{
        color: {t.get('text_main', '#E0E2E4')};
        spacing: 5px;
    }}
    QCheckBox::indicator, RZCheckBox::indicator {{
        width: 14px;
        height: 14px;
        border-radius: 2px;
        border: 1px solid {t.get('border_input', '#4A505A')};
        background-color: {t.get('bg_input', '#252930')};
    }}
    QCheckBox::indicator:checked, RZCheckBox::indicator:checked {{
        background-color: {accent};
        border: 1px solid {accent};
    }}
    QCheckBox::indicator:hover, RZCheckBox::indicator:hover {{
        border: 1px solid {accent_hover};
    }}

    /* --- PUSH BUTTONS --- */
    QPushButton, RZPushButton, RZColorButton {{
        background-color: {t.get('bg_header', '#3A404A')};
        color: {t.get('text_main', '#E0E2E4')};
        border: 1px solid {t.get('border_input', '#3A404A')};
        border-radius: 4px;
        padding: 6px 12px;
    }}
    QPushButton:hover, RZPushButton:hover {{
        background-color: {accent_hover};
        color: {t.get('accent_text', '#FFFFFF')};
    }}
    QPushButton:focus, RZPushButton:focus {{
        background-color: {t.get('bg_panel', '#2C313A')};
        border: 1.5px solid {accent};
    }}
    QPushButton:pressed, RZPushButton:pressed {{
        background-color: {accent};
    }}
    QPushButton:disabled, RZPushButton:disabled {{
        color: {t.get('text_disabled', '#6A717C')};
        background-color: {t.get('bg_input', '#252930')};
    }}

    /* --- LABELS --- */
    QLabel, RZLabel {{
        color: {t.get('text_main', '#E0E2E4')};
    }}

    /* --- SCROLL AREAS --- */
    QScrollArea, RZScrollArea {{
        background-color: transparent;
        border: none;
    }}

    /* Tables & Trees (Minimalist) */
    QHeaderView::section {{
        background-color: transparent;
        padding: 8px;
        border: none;
        border-bottom: 1px solid {border_main};
        color: {t.get('text_dark', '#999')};
        font-weight: bold;
        font-size: 8pt;
    }}
    QTableWidget, QTreeWidget {{
        background-color: transparent;
        border: none;
    }}
    QTreeWidget::item {{
        padding: 6px;
        border-radius: {r_sm};
    }}
    QTreeWidget::item:hover {{
        background-color: rgba(255, 255, 255, 10);
    }}
    QTreeWidget::item:selected {{
        background-color: {t.get('selection', '#4A6E91')};
        color: {t.get('text_bright', '#FFF')};
    }}

    /* Scrollbars (Sleek Minimalist) */
    QScrollBar:vertical {{
        border: none; background: transparent; width: 8px; margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {t.get('border_contrast', '#555')}; min-height: 40px; border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {accent}; }}
    QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
        height: 0px; width: 0px; background: none;
    }}
    
    QSplitter::handle {{
        background-color: {t.get('handle_splitter', '#1E2227')};
    }}
    QSplitter::handle:hover {{
        background-color: {accent};
    }}
    """

