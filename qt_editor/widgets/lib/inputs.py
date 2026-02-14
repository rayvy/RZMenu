# RZMenu/qt_editor/widgets/lib/inputs.py
import re
from PySide6 import QtWidgets, QtCore, QtGui
from .theme import get_current_theme
from ...utils.image_cache import ImageCache
from ...core import read as core_read # For suggestions
from ...core import blender_bridge

class RZImageComboBox(QtWidgets.QComboBox):
    """
    ComboBox for image selection with drag-and-drop support.
    """
    value_changed = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.apply_theme()
        self.currentIndexChanged.connect(self._on_index_changed)

    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"""
            QComboBox {{
                background-color: {theme.get('bg_input', '#252930')};
                border: 1px solid {theme.get('border_input', '#4A505A')};
                border-radius: 3px;
                padding: 3px;
                color: {theme.get('text_main', '#E0E2E4')};
            }}
            QComboBox:focus {{ border: 1px solid {theme.get('accent', '#5298D4')}; }}
            QComboBox::drop-down {{ border-left: 1px solid {theme.get('border_input', '#4A505A')}; }}
        """)

    def update_items(self, images_list):
        """Populate the combo box with images: [{'id': 1, 'name': 'Name'}]"""
        self.blockSignals(True)
        current_id = self.currentData()
        self.clear()
        
        # Add a default "None" option
        self.addItem("None", -1)
        
        cache = ImageCache.instance()
        for img in images_list:
            img_id = img['id']
            name = img['name']
            pixmap = cache.get_pixmap(img_id)
            icon = QtGui.QIcon(pixmap) if pixmap else QtGui.QIcon()
            self.addItem(icon, name, img_id)
            
        # Try to restore selection
        if current_id is not None:
            self.set_value(current_id)
            
        self.blockSignals(False)

    def set_value(self, image_id):
        """Find item with this ID and select it."""
        index = self.findData(image_id)
        if index != -1:
            self.setCurrentIndex(index)
        else:
            self.setCurrentIndex(0) # Default to None

    def _on_index_changed(self, index):
        image_id = self.itemData(index)
        if image_id is not None:
            self.value_changed.emit(image_id)

    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if mime.hasUrls() or mime.hasFormat("application/x-rzmenu-image-id"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        mime = event.mimeData()
        try:
            # 1. Internal Asset Drop
            if mime.hasFormat("application/x-rzmenu-image-id"):
                data = mime.data("application/x-rzmenu-image-id")
                image_id = int(data.data().decode('utf-8'))
                # Emit signal directly to update property. 
                # UI will refresh via structure_changed signal and pick up the new value.
                self.value_changed.emit(image_id)
                event.acceptProposedAction()
                
            # 2. External File Drop
            elif mime.hasUrls():
                urls = mime.urls()
                for url in urls:
                    path = url.toLocalFile()
                    if path:
                        # Only handle the first image for a single combo box
                        img_id, _ = blender_bridge.import_image(path)
                        if img_id is not None:
                            self.value_changed.emit(img_id)
                        event.acceptProposedAction()
                        break
            else:
                super().dropEvent(event)
        except (ValueError, TypeError):
            pass

class RZFormulaHighlighter(QtGui.QSyntaxHighlighter):
    """Highlights variables starting with $ in soft red."""
    def __init__(self, document):
        super().__init__(document)
        self.update_theme()
        
    def update_theme(self):
        theme = get_current_theme()
        self.format_var = QtGui.QTextCharFormat()
        color = QtGui.QColor(theme.get('text_variable', '#E06C75')) 
        self.format_var.setForeground(color)
        self.format_var.setFontWeight(QtGui.QFont.Bold)

    def highlightBlock(self, text):
        # Match variables starting with $, @, or #
        expression = r'[\$@#][a-zA-Z0-9_]+'
        for match in re.finditer(expression, text):
            start, end = match.span()
            self.setFormat(start, end - start, self.format_var)

class RZIniHighlighter(QtGui.QSyntaxHighlighter):
    """
    Highlights INI / 3DMigoto syntax.
    - [Sections]
    - keys = 
    - ; Comments
    - $Variables, @Toggles, #Shapes
    """
    def __init__(self, document):
        super().__init__(document)
        self.update_theme()
        
    def update_theme(self):
        theme = get_current_theme()
        
        # 1. Section: [Abc] -> Blue/Accent
        self.fmt_section = QtGui.QTextCharFormat()
        self.fmt_section.setForeground(QtGui.QColor(theme.get('accent', '#5298D4')))
        self.fmt_section.setFontWeight(QtGui.QFont.Bold)
        
        # 2. Key: something = -> Orange
        self.fmt_key = QtGui.QTextCharFormat()
        self.fmt_key.setForeground(QtGui.QColor(theme.get('text_keyword', '#D19A66')))
        
        # 3. Comment: ; ... -> Grey
        self.fmt_comment = QtGui.QTextCharFormat()
        self.fmt_comment.setForeground(QtGui.QColor(theme.get('text_dim', '#5C6370')))
        self.fmt_comment.setFontItalic(True)
        
        # 4. Variable: $var -> Red
        self.fmt_var = QtGui.QTextCharFormat()
        self.fmt_var.setForeground(QtGui.QColor(theme.get('text_variable', '#E06C75')))
        # self.fmt_var.setFontWeight(QtGui.QFont.Bold)

    def highlightBlock(self, text):
        # 1. Comments (take precedence over everything else usually, or last?)
        # If we match comment first, we can fill it. But regex order matters.
        
        # Let's iterate matches.
        
        # Section [...]
        for match in re.finditer(r'^\[.*?\]', text):
            self.setFormat(match.start(), match.end() - match.start(), self.fmt_section)
            
        # Key (start of line, before =)
        # matches "key =" or "key="
        for match in re.finditer(r'^[^=;\n]+(?==)', text):
             self.setFormat(match.start(), match.end() - match.start(), self.fmt_key)
             
        # Variables (anywhere)
        for match in re.finditer(r'[\$@#][a-zA-Z0-9_]+', text):
            self.setFormat(match.start(), match.end() - match.start(), self.fmt_var)

        # Comments (semicolon to end)
        for match in re.finditer(r';.*', text):
            self.setFormat(match.start(), match.end() - match.start(), self.fmt_comment)

class RZFormulaInput(QtWidgets.QPlainTextEdit):
    """
    Advanced text edit for formulas with Autocomplete and Syntax Highlighting.
    Inherits from QPlainTextEdit to support QSyntaxHighlighter, but behaves like a LineEdit.
    """
    editingFinished = QtCore.Signal() # Compatibility with QLineEdit

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Single line behavior
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setTabChangesFocus(True)
        
        # Popup setup
        self.popup = QtWidgets.QListWidget()
        self.popup.setWindowFlags(QtCore.Qt.ToolTip | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.popup.setFocusPolicy(QtCore.Qt.NoFocus)
        self.popup.setMouseTracking(True)
        self.popup.installEventFilter(self)
        self.popup.hide()
        
        self.popup.itemClicked.connect(self._complete_selection)
        
        # Highlighter setup
        self.highlighter = RZFormulaHighlighter(self.document())
        
        self.apply_theme()

    def text(self): return self.toPlainText()
    def setText(self, t): 
        self.setPlainText(str(t))
        # Match QLineEdit behavior of moving cursor to end on setText
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.setTextCursor(cursor)

    def cursorPosition(self): return self.textCursor().position()
    def setCursorPosition(self, pos):
        cursor = self.textCursor()
        cursor.setPosition(pos)
        self.setTextCursor(cursor)

    def apply_theme(self):
        theme = get_current_theme()
        # Note: We must use QPlainTextEdit selector instead of QLineEdit
        self.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {theme.get('bg_input', '#252930')};
                border: 1px solid {theme.get('border_input', '#4A505A')};
                border-radius: 3px;
                padding: 3px;
                color: {theme.get('text_main', '#E0E2E4')};
                font-family: Consolas, Monospace;
            }}
            QPlainTextEdit:focus {{ border: 1px solid {theme.get('accent', '#5298D4')}; }}
        """)
        if hasattr(self, 'highlighter'):
            self.highlighter.update_theme()
            self.highlighter.rehighlight()
            
        self._apply_popup_theme()

    def _apply_popup_theme(self):
        theme = get_current_theme()
        self.popup.setStyleSheet(f"""
            QListWidget {{
                background-color: {theme.get('bg_panel', '#2C313A')};
                border: 1px solid {theme.get('border_main', '#3A404A')};
                color: {theme.get('text_main', '#E0E2E4')};
            }}
            QListWidget::item {{ padding: 4px; }}
            QListWidget::item:selected {{
                background-color: {theme.get('accent', '#5298D4')};
                color: white;
            }}
        """)

    def keyPressEvent(self, event):
        # Prevent newlines
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            if not self.popup.isVisible():
                self.editingFinished.emit()
                event.accept()
                return

        # Navigation inside popup
        if self.popup.isVisible():
            if event.key() == QtCore.Qt.Key_Down:
                idx = self.popup.currentRow()
                if idx < self.popup.count() - 1:
                    self.popup.setCurrentRow(idx + 1)
                return
            elif event.key() == QtCore.Qt.Key_Up:
                idx = self.popup.currentRow()
                if idx > 0:
                    self.popup.setCurrentRow(idx - 1)
                return
            elif event.key() in (QtCore.Qt.Key_Enter, QtCore.Qt.Key_Return, QtCore.Qt.Key_Tab):
                self._complete_selection(self.popup.currentItem())
                event.accept()
                return
            elif event.key() == QtCore.Qt.Key_Escape:
                self.popup.hide()
                return

        super().keyPressEvent(event)
        self._check_autocomplete()

    def focusOutEvent(self, event):
        QtCore.QTimer.singleShot(100, self.popup.hide)
        self.editingFinished.emit()
        super().focusOutEvent(event)

    def _check_autocomplete(self):
        text = self.text()
        cursor_pos = self.cursorPosition()
        left_text = text[:cursor_pos]
        
        # Regex: Find word starting with $, @, or # under cursor
        match = re.search(r'[\$@#]([a-zA-Z0-9_]*)$', left_text)
        
        if match:
            token = match.group(0) # e.g. "$But"
            self._show_suggestions(token)
        else:
            self.popup.hide()

    def _show_suggestions(self, token):
        all_vars = core_read.get_variable_suggestions()
        # Case insensitive filtering
        filtered = [v for v in all_vars if v.lower().startswith(token.lower())]
        
        if not filtered:
            self.popup.hide()
            return

        self.popup.clear()
        self.popup.addItems(filtered)
        self.popup.setCurrentRow(0)
        
        # Position Popup
        rect = self.cursorRect()
        global_pos = self.mapToGlobal(rect.bottomLeft())
        self.popup.move(global_pos.x(), global_pos.y() + 5)
        
        # Limit height
        self.popup.setFixedSize(250, min(150, len(filtered) * 25 + 5))
        self.popup.show()

    def _complete_selection(self, item):
        if not item: return
        completion = item.text()
        
        text = self.text()
        cursor_pos = self.cursorPosition()
        left_text = text[:cursor_pos]
        
        match = re.search(r'[\$@#]([a-zA-Z0-9_]*)$', left_text)
        if match:
            start, end = match.span()
            prefix = left_text[:start]
            suffix = text[cursor_pos:]
            
            new_text = prefix + completion + suffix
            self.setText(new_text)
            self.setCursorPosition(len(prefix) + len(completion))
            
        self.popup.hide()

    def eventFilter(self, obj, event):
        if obj == self.popup and event.type() == QtCore.QEvent.MouseButtonPress:
            self._complete_selection(self.popup.currentItem())
            return True
        return super().eventFilter(obj, event)

class RZCodeTextEdit(RZFormulaInput):
    """
    Multi-line text edit for code/formulas.
    Inherits from RZFormulaInput but allows Enter for newlines.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap) # Keep no wrap for code
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setMinimumHeight(80) 

    def keyPressEvent(self, event):
        # Allow Enter to insert newline, but keep other behavior (popup nav, etc)
        # Note: RZFormulaInput.keyPressEvent consumes Enter if popup is hidden.
        # We need to bypass that specific check.

        if self.popup.isVisible():
            # Standard popup navigation
            if event.key() == QtCore.Qt.Key_Down:
                idx = self.popup.currentRow()
                if idx < self.popup.count() - 1:
                    self.popup.setCurrentRow(idx + 1)
                return
            elif event.key() == QtCore.Qt.Key_Up:
                idx = self.popup.currentRow()
                if idx > 0:
                    self.popup.setCurrentRow(idx - 1)
                return
            elif event.key() in (QtCore.Qt.Key_Enter, QtCore.Qt.Key_Return, QtCore.Qt.Key_Tab):
                self._complete_selection(self.popup.currentItem())
                event.accept()
                return
            elif event.key() == QtCore.Qt.Key_Escape:
                self.popup.hide()
                return

        # If popup is NOT visible, we want standard QPlainTextEdit behavior for Enter
        # But we still want autocomplete triggereing for other keys.
        # So we call QPlainTextEdit.keyPressEvent directly, skipping RZFormulaInput's override?
        # No, RZFormulaInput's override does _check_autocomplete at the end.
        
        # Let's just reimplement the necessary part without the "Consume Enter" block.
        QtWidgets.QPlainTextEdit.keyPressEvent(self, event)
        self._check_autocomplete()

    def set_highlighter(self, highlighter_class):
        """Allows swapping the highlighter (e.g. to INI)."""
        if highlighter_class:
            self.highlighter = highlighter_class(self.document())
            self.highlighter.update_theme()
            self.highlighter.rehighlight()
        else:
            self.highlighter = None
