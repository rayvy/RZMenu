# RZMenu/qt_editor/widgets/lib/theming/generator.py
import os

def _rgba(hex_color, alpha_override=None):
    """
    Converts a HEX color to an rgba(r, g, b, a) string.
    Supports #RGB, #RRGGBB, #AARRGGBB.
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
    """
    Generates a full QSS string with absolute asset path resolution and glass-effect panels.
    """
    print(f"[DEBUG-THEME] Generating QSS for theme... {t.get('name')}") # [DEBUG-THEME]
    
    # --- ASSET RESOLUTION ---
    bg_image = t.get("bg_image", "")
    root_path = t.get("_root_path", "")
    bg_type = t.get("bg_type", "solid")
    
    print(f"[DEBUG-THEME] Raw values: bg_image={bg_image}, bg_type={bg_type}, root_path={root_path}") # [DEBUG-THEME]
    
    full_bg_path = ""
    
    if bg_image:
        if os.path.isabs(bg_image):
            clean_path = bg_image
        elif root_path:
            clean_path = os.path.join(root_path, bg_image)
        else:
            clean_path = bg_image
            
        # Normalize for Qt Style Sheet (always forward slashes)
        full_bg_path = clean_path.replace("\\", "/")
            
    print(f"[DEBUG-THEME] Final full_bg_path: {full_bg_path}") # [DEBUG-THEME]

    # --- STYLE CONFIGS ---
    panel_opacity = float(t.get("panel_opacity", 0.9))
    overlay_color = t.get("overlay_color", "#000000")
    overlay_opacity = float(t.get("overlay_opacity", 0.0))
    
    # Root Background Logic
    root_bg_css = f"background-color: {t.get('bg_root', '#20232A')};"
    
    if bg_type == "image" and full_bg_path:
        print("[DEBUG-THEME] IMAGE MODE ACTIVE") # [DEBUG-THEME]
        root_bg_css = f"""
            background-color: {t.get('bg_root', '#000000')};
            background-image: url("{full_bg_path}");
            background-position: center;
            background-repeat: no-repeat;
        """
    
    print(f"[DEBUG-THEME] Final root_bg_css: {root_bg_css}") # [DEBUG-THEME]

    panel_bg = _rgba(t.get('bg_panel', '#2C313A'), panel_opacity)
    border_main = t.get('border_main', '#3A404A')
    
    return f"""
    /* --- Root & Panels --- */
    QWidget, QDialog {{
        background-color: {t.get('bg_root', '#20232A')};
        color: {t.get('text_main', '#E0E2E4')};
        font-family: sans-serif; 
        font-size: 10pt;
    }}
    
    #RZMEditorWindow {{
        {root_bg_css}
    }}
    
    RZMInspectorPanel, RZMOutlinerPanel, RZViewportPanel {{
        background-color: {panel_bg};
        border: 1px solid {border_main};
        border-radius: 4px;
    }}

    /* --- Groups & Tabs --- */
    QGroupBox {{
        background-color: {panel_bg};
        border: 1px solid {border_main};
        border-radius: 4px;
        margin-top: 6px;
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
        background: {panel_bg};
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
        background: {panel_bg};
        color: {t.get('text_main', '#EEE')};
    }}

    /* --- Inputs & Controls --- */
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
    
    /* --- Buttons --- */
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
    
    #BtnSpecial {{
        border: none;
        color: {t.get('text_dark', '#999')};
    }}
    
    /* --- Sliders --- */
    RZSmartSlider QPushButton {{
         background: {t.get('bg_header', '#333')};
         border: none;
         padding: 0px;
    }}
     _RZDragLabel {{
        color: {t.get('text_dark', '#999')};
        padding-right: 4px;
     }}

    /* --- Tables & Trees --- */
    QHeaderView::section {{
        background-color: {t.get('bg_header', '#333')};
        padding: 4px;
        border: 1px solid {border_main};
        color: {t.get('text_dark', '#999')};
    }}
    QTableWidget, QTreeWidget {{
        background-color: {t.get('bg_input', '#222')};
        border: 1px solid {border_main};
    }}
    QTableWidget::item, QTreeWidget::item {{
        color: {t.get('text_main', '#EEE')};
    }}
    QTableWidget::item:selected, QTreeWidget::item:selected {{
        background-color: {t.get('selection', '#4A6E91')};
        color: {t.get('text_bright', '#FFF')};
    }}
    
    /* --- Splitter --- */
    QSplitter::handle {{
        background-color: {t.get('bg_root', '#222')};
    }}
    QSplitter::handle:hover {{
        background-color: {t.get('accent', '#529')};
    }}

    /* --- Scrollbars --- */
    QScrollBar:vertical {{
        border: none;
        background: {t.get('bg_root', '#222')};
        width: 10px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {t.get('bg_header', '#444')};
        min-height: 20px;
        border-radius: 4px;
    }}
    """
