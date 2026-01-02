# RZMenu/qt_editor/widgets/lib/theming/generator.py

def generate_qss(t: dict) -> str:
    """
    Generates a full QSS string based on the provided theme dictionary.
    """
    return f"""
    /* --- Root & Panels --- */
    QWidget, QDialog {{
        background-color: {t['bg_root']};
        color: {t['text_main']};
        font-family: sans-serif; 
        font-size: 10pt;
    }}
    
    #RZMEditorWindow {{
        background-color: {t['bg_root']};
    }}
    
    RZMInspectorPanel, RZMOutlinerPanel, RZViewportPanel {{
        background-color: {t['bg_panel']};
        border: 1px solid {t['border_main']};
        border-radius: 4px;
    }}

    /* --- Groups & Tabs --- */
    QGroupBox {{
        background-color: {t['bg_panel']};
        border: 1px solid {t['border_main']};
        border-radius: 4px;
        margin-top: 6px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 4px;
        left: 10px;
        background-color: {t['bg_panel']};
        color: {t['text_dark']};
    }}
    
    QTabWidget::pane {{
        border: 1px solid {t['border_main']};
        background: {t['bg_panel']};
    }}
    QTabBar::tab {{
        background: {t['bg_root']};
        color: {t['text_dark']};
        padding: 5px 10px;
        border: 1px solid {t['border_main']};
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }}
    QTabBar::tab:selected, QTabBar::tab:hover {{
        background: {t['bg_panel']};
        color: {t['text_main']};
    }}

    /* --- Inputs & Controls --- */
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {t['bg_input']};
        border: 1px solid {t['border_input']};
        border-radius: 3px;
        padding: 3px;
        color: {t['text_main']};
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border: 1px solid {t['accent']};
    }}
    QComboBox::drop-down {{
        border-left: 1px solid {t['border_input']};
    }}
    
    /* --- Buttons --- */
    QPushButton {{
        background-color: {t['bg_header']};
        color: {t['text_main']};
        border: 1px solid {t['border_input']};
        border-radius: 3px;
        padding: 4px 10px;
    }}
    QPushButton:hover {{
        background-color: {t['accent_hover']};
        color: {t['accent_text']};
    }}
    QPushButton:pressed {{
        background-color: {t['accent']};
    }}
    QPushButton:disabled {{
        color: {t['text_disabled']};
        background-color: {t['bg_input']};
    }}
    
    #BtnSpecial {{ /* Example for specific buttons */
        border: none;
        color: {t['text_dark']};
    }}
    
    /* --- Sliders --- */
    RZSmartSlider QPushButton {{
         background: {t['bg_header']};
         border: none;
         padding: 0px;
    }}
     _RZDragLabel {{
        color: {t['text_dark']};
        padding-right: 4px;
     }}

    /* --- Tables & Trees --- */
    QHeaderView::section {{
        background-color: {t['bg_header']};
        padding: 4px;
        border: 1px solid {t['border_main']};
        color: {t['text_dark']};
    }}
    QTableWidget, QTreeWidget {{
        background-color: {t['bg_input']};
        border: 1px solid {t['border_main']};
    }}
    QTableWidget::item, QTreeWidget::item {{
        color: {t['text_main']};
    }}
    QTableWidget::item:selected, QTreeWidget::item:selected {{
        background-color: {t['selection']};
        color: {t['text_bright']};
    }}
    
    /* --- Splitter --- */
    QSplitter::handle {{
        background-color: {t['bg_root']};
    }}
    QSplitter::handle:hover {{
        background-color: {t['accent']};
    }}

    /* --- Scrollbars --- */
    QScrollBar:vertical {{
        border: none;
        background: {t['bg_root']};
        width: 10px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {t['bg_header']};
        min-height: 20px;
        border-radius: 4px;
    }}
    """

