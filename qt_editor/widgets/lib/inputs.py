# RZMenu/qt_editor/widgets/lib/inputs.py
import re
from PySide6 import QtWidgets, QtCore, QtGui
from .theme import get_current_theme
from ...utils.image_cache import ImageCache
from ...core import read as core_read # For suggestions

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
        if event.mimeData().hasFormat("application/x-rzmenu-image-id"):
            event.acceptProposedAction()

    def dropEvent(self, event):
        data = event.mimeData().data("application/x-rzmenu-image-id")
        try:
            image_id = int(data.data().decode('utf-8'))
            self.set_value(image_id)
            event.acceptProposedAction()
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
