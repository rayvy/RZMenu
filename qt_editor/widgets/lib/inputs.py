# RZMenu/qt_editor/widgets/lib/inputs.py
import re
from PySide6 import QtWidgets, QtCore, QtGui
from .theme import get_current_theme
from .base import RZVisualInputMixin
from ...utils.image_cache import ImageCache
from ...core import read as core_read # For suggestions
from ...core import blender_bridge
from ...utils.debounce import RZDebouncer
from ...utils.evaluation import get_formula_preview

class RZImageComboBox(QtWidgets.QComboBox):
    """
    ComboBox for image selection with drag-and-drop support.
    """
    value_changed = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.apply_theme()
        
        from .widgets import RZStaggeredDelegate # Local import to avoid circular if any
        self._delegate = RZStaggeredDelegate(self)
        self.setItemDelegate(self._delegate)
        
        self._popup_anim = QtCore.QPropertyAnimation(self, b"popup_progress")
        self._popup_anim.setDuration(400)
        self._popup_anim.setEasingCurve(QtCore.QEasingCurve.Linear)

        self.currentIndexChanged.connect(self._on_index_changed)
        self.setIconSize(QtCore.QSize(20, 20))
        self.setMinimumHeight(24)

    @QtCore.Property(float)
    def popup_progress(self):
        return self._delegate.progress
        
    @popup_progress.setter
    def popup_progress(self, val):
        self._progress = val
        self._delegate.progress = val
        self.update()
        win = self.view().window()
        if win and win.isVisible():
            win.setWindowOpacity(min(1.0, val * 3))
            if val > 0.9:
                 win.setWindowOpacity(1.0)

    def showPopup(self):
        count = self.count()
        total_duration = 200
        if count > 0:
            self._delegate.stagger_delay = 5.0 / max(1, count + 2)
            self._delegate.item_fade_speed = 0.5

        self._popup_anim.stop()
        self._popup_anim.setDuration(total_duration)
        self._popup_anim.setStartValue(0.0)
        self._popup_anim.setEndValue(1.0)
        
        super().showPopup()
        
        popup = self.view().window()
        if popup:
            popup.setWindowOpacity(0.01) 
            popup.show()
            
        self._popup_anim.start()

    def wheelEvent(self, event):
        event.ignore()

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
        self.blockSignals(True)
        current_id = self.currentData()
        self.clear()
        
        self.addItem("None", -1)
        
        cache = ImageCache.instance()
        for img in images_list:
            img_id = img['id']
            name = img['name']
            pixmap = cache.get_pixmap(img_id)
            icon = QtGui.QIcon(pixmap) if pixmap else QtGui.QIcon()
            self.addItem(icon, name, img_id)
            
        if current_id is not None:
            self.set_value(current_id)
            
        self.blockSignals(False)

    def set_value(self, image_id):
        index = self.findData(image_id)
        if index != -1:
            self.setCurrentIndex(index)
        else:
            self.setCurrentIndex(0)

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
            if mime.hasFormat("application/x-rzmenu-image-id"):
                data = mime.data("application/x-rzmenu-image-id")
                image_id = int(data.data().decode('utf-8'))
                self.value_changed.emit(image_id)
                event.acceptProposedAction()
                
            elif mime.hasUrls():
                urls = mime.urls()
                for url in urls:
                    path = url.toLocalFile()
                    if path:
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
        expression = r'[\$@#][a-zA-Z0-9_]+'
        for match in re.finditer(expression, text):
            start, end = match.span()
            self.setFormat(start, end - start, self.format_var)


class RZIniHighlighter(QtGui.QSyntaxHighlighter):
    """Highlights INI / 3DMigoto syntax."""
    def __init__(self, document):
        super().__init__(document)
        self.update_theme()
        
    def update_theme(self):
        theme = get_current_theme()
        self.fmt_section = QtGui.QTextCharFormat()
        self.fmt_section.setForeground(QtGui.QColor(theme.get('accent', '#5298D4')))
        self.fmt_section.setFontWeight(QtGui.QFont.Bold)
        
        self.fmt_key = QtGui.QTextCharFormat()
        self.fmt_key.setForeground(QtGui.QColor(theme.get('text_keyword', '#D19A66')))
        
        self.fmt_comment = QtGui.QTextCharFormat()
        self.fmt_comment.setForeground(QtGui.QColor(theme.get('text_dim', '#5C6370')))
        self.fmt_comment.setFontItalic(True)
        
        self.fmt_var = QtGui.QTextCharFormat()
        self.fmt_var.setForeground(QtGui.QColor(theme.get('text_variable', '#E06C75')))

    def highlightBlock(self, text):
        for match in re.finditer(r'^\[.*?\]', text):
            self.setFormat(match.start(), match.end() - match.start(), self.fmt_section)
        for match in re.finditer(r'^[^=;\n]+(?==)', text):
             self.setFormat(match.start(), match.end() - match.start(), self.fmt_key)
        for match in re.finditer(r'[\$@#][a-zA-Z0-9_]+', text):
            self.setFormat(match.start(), match.end() - match.start(), self.fmt_var)
        for match in re.finditer(r';.*', text):
            self.setFormat(match.start(), match.end() - match.start(), self.fmt_comment)


class _RZBaseTextEdit(QtWidgets.QPlainTextEdit, RZVisualInputMixin):
    """
    Hidden base class. Handles standard popup base config, 
    focus management, and core text accessors.
    """
    editingFinished = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_visuals()
        self._is_multiline = False
        
        self.popup = QtWidgets.QListWidget()
        self.popup.setWindowFlags(QtCore.Qt.ToolTip | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.popup.setFocusPolicy(QtCore.Qt.NoFocus)
        self.popup.setMouseTracking(True)
        self.popup.installEventFilter(self)
        self.popup.hide()
        
        self.popup.itemClicked.connect(self._complete_selection)
        self.apply_theme()

    def eventFilter(self, obj, event):
        if obj == self.popup and event.type() == QtCore.QEvent.MouseButtonPress:
            self._complete_selection(self.popup.currentItem())
            return True
        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        self._draw_visual_border(painter)
        self._draw_resizer_dots(painter)
        painter.end()

    def mousePressEvent(self, event):
        if self._handle_visual_mouse_press(event):
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._handle_visual_mouse_move(event):
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._handle_visual_mouse_release(event):
            return
        super().mouseReleaseEvent(event)

    def set_text_silent(self, text):
        if self.hasFocus(): return
        if self.text() == text: return
        self.blockSignals(True)
        self.setText(str(text))
        self.blockSignals(False)

    def text(self): return self.toPlainText()
    
    def setText(self, t): 
        self.setPlainText(str(t))
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
        self.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {theme.get('bg_input', '#252930')};
                border: 1px solid {theme.get('border_input', '#4A505A')};
                border-radius: 6px;
                padding: 4px 8px;
                color: {theme.get('text_main', '#E0E2E4')};
                font-family: Consolas, Monospace;
            }}
            QPlainTextEdit:focus {{ 
                border: 1px solid {theme.get('accent', '#5298D4')};
                background-color: {theme.get('bg_panel', '#2C313A')};
            }}
        """)
        if hasattr(self, 'highlighter') and self.highlighter:
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

    def wheelEvent(self, event):
        if not self._is_multiline:
            event.ignore()
        else:
            super().wheelEvent(event)
            
    def _complete_selection(self, item):
        pass 


class RZFormulaInput(_RZBaseTextEdit):
    """
    Advanced text edit for formulas with Autocomplete and Syntax Highlighting.
    Acts purely as a LineEdit.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_multiline = False 
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setTabChangesFocus(True)
        
        self.highlighter = RZFormulaHighlighter(self.document())
        self.highlighter.update_theme()

        self.debouncer = RZDebouncer(delay_ms=400, parent=self)
        self.debouncer.timeout.connect(self.editingFinished.emit)
        self.textChanged.connect(lambda: self.debouncer.trigger(lambda: None))
        
        self.preview_label = QtWidgets.QLabel(self)
        self.preview_label.setStyleSheet("color: #888; background: transparent; padding: 2px;")
        self.preview_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.preview_label.hide()
        
        self.textChanged.connect(self._on_formula_changed)

    def apply_theme(self):
        super().apply_theme()
        self._pattern = ""
        self._originals =[]

    def set_pattern(self, pattern, originals=None):
        self._pattern = pattern
        self._originals = originals or[]
        self.setText(pattern)
        font = self.font()
        font.setItalic(bool(pattern))
        self.setFont(font)

    def get_pattern(self): return self._pattern
    def get_originals(self): return self._originals

    def clear_pattern(self):
        self._pattern = ""
        self._originals =[]
        font = self.font()
        font.setItalic(False)
        self.setFont(font)

    def _on_formula_changed(self):
        self.debouncer.trigger(self._update_preview)

    def _update_preview(self):
        text = self.toPlainText().strip()
        if not text:
            self.preview_label.hide()
            return
            
        res = get_formula_preview(text)
        if res and res != text:
             self.preview_label.setText(f"= {res}")
             self.preview_label.show()
             self._reposition_preview()
        else:
             self.preview_label.hide()

    def _reposition_preview(self):
        self.preview_label.adjustSize()
        self.preview_label.move(self.width() - self.preview_label.width() - 5, 2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_preview()

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            if not self.popup.isVisible():
                if not self._is_multiline:
                    self.editingFinished.emit()
                    event.accept()
                    return

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
        
        match = re.search(r'[\$@#]([a-zA-Z0-9_]*)$', left_text)
        if match:
            token = match.group(0) 
            self._show_suggestions(token)
        else:
            self.popup.hide()

    def _show_suggestions(self, token):
        all_vars = core_read.get_variable_suggestions()
        filtered =[v for v in all_vars if v.lower().startswith(token.lower())]
        if not filtered:
            self.popup.hide()
            return

        self.popup.clear()
        self.popup.addItems(filtered)
        self.popup.setCurrentRow(0)
        
        rect = self.cursorRect()
        global_pos = self.mapToGlobal(rect.bottomLeft())
        self.popup.move(global_pos.x(), global_pos.y() + 5)
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


class RZCodeTextEdit(RZFormulaInput):
    """
    Multi-line text edit for code/formulas.
    Inherits from RZFormulaInput but unlocks standard multiline features.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_multiline = True 
        self._is_resizable = True
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setMinimumHeight(60)
        self.setMouseTracking(True)

    def set_highlighter(self, highlighter_class):
        if highlighter_class:
            self.highlighter = highlighter_class(self.document())
            self.highlighter.update_theme()
            self.highlighter.rehighlight()
        else:
            self.highlighter = None


class RZModInfoHighlighter(QtGui.QSyntaxHighlighter):
    """
    Highlighter for Mod Info. 
    Tags like {{character_name}} are highlighted.
    """
    def __init__(self, document):
        super().__init__(document)
        self.update_theme()
        
    def update_theme(self):
        theme = get_current_theme()
        self.fmt_tag = QtGui.QTextCharFormat()
        self.fmt_tag.setForeground(QtGui.QColor(theme.get('accent', '#5298D4')))
        self.fmt_tag.setFontWeight(QtGui.QFont.Bold)

        self.fmt_replaced = QtGui.QTextCharFormat()
        accent = QtGui.QColor(theme.get('accent', '#5298D4'))
        self.fmt_replaced.setForeground(accent)
        self.fmt_replaced.setFontWeight(QtGui.QFont.Bold)

    def highlightBlock(self, text):
        for match in re.finditer(r'\x01(.*?)\x02', text):
            self.setFormat(match.start(), match.end() - match.start(), self.fmt_replaced)
        for match in re.finditer(r'\{\{.*?\}\}', text):
            self.setFormat(match.start(), match.end() - match.start(), self.fmt_tag)


class RZModInfoTextEdit(RZCodeTextEdit):
    """
    Specialized editor for Mod Info with {{ }} autocomplete 
    and Live Preview on unfocus.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._raw_text = ""
        self._is_preview = False
        
        self._is_resizable = True
        self._min_res_h = 120
        self._max_res_h = 680
        self.setMinimumHeight(120)
        self.setMaximumHeight(680)

        self.highlighter = RZModInfoHighlighter(self.document())
        self.textChanged.connect(self._on_text_changed_internal)

    def _on_text_changed_internal(self):
        if not self._is_preview:
            self._raw_text = self.toPlainText()

    def focusInEvent(self, event):
        if self._is_preview:
            self.blockSignals(True)
            self.setPlainText(self._raw_text)
            self.blockSignals(False)
            
            self._is_preview = False
            self.highlighter.rehighlight()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        if self._is_preview: 
            super().focusOutEvent(event)
            return 
        
        self._raw_text = self.toPlainText()
        preview_text = core_read.evaluate_mod_info(self._raw_text, highlight=True)
        self._is_preview = True
        
        self.blockSignals(True)
        self.setPlainText(preview_text)
        self.blockSignals(False)
        
        # Safely calls editingFinished logic hiding the popup through the parent
        super().focusOutEvent(event)

    def text(self):
        # Always safe, preventing debouncer desync
        return self._raw_text if self._is_preview else self.toPlainText()

    def set_text_safe(self, t):
        if self.hasFocus(): 
            return 
            
        self._raw_text = str(t)
        self.blockSignals(True)
        if not self.hasFocus():
            preview_text = core_read.evaluate_mod_info(self._raw_text, highlight=True)
            self._is_preview = True
            self.setPlainText(preview_text)
        else:
            self.setPlainText(self._raw_text)
        self.blockSignals(False)

    def _check_autocomplete(self):
        if self._is_preview: return
        
        text = self.toPlainText()
        cursor_pos = self.cursorPosition()
        left_text = text[:cursor_pos]
        
        match = re.search(r'\{\{([a-zA-Z0-9_]*)$', left_text)
        
        if match:
            token = match.group(0) 
            self._show_suggestions(token)
        else:
            self.popup.hide()

    def _show_suggestions(self, token):
        all_tags = core_read.get_metadata_suggestions()
        filtered =[v for v in all_tags if v.lower().startswith(token.lower())]
        
        if not filtered:
            self.popup.hide()
            return

        self.popup.clear()
        self.popup.addItems(filtered)
        self.popup.setCurrentRow(0)
        
        rect = self.cursorRect()
        global_pos = self.mapToGlobal(rect.bottomLeft())
        self.popup.move(global_pos.x(), global_pos.y() + 5)
        self.popup.setFixedSize(250, min(150, len(filtered) * 25 + 5))
        self.popup.show()

    def _complete_selection(self, item):
        if not item: return
        completion = item.text() + "}}" 
        
        text = self.toPlainText()
        cursor_pos = self.cursorPosition()
        left_text = text[:cursor_pos]
        
        match = re.search(r'\{\{([a-zA-Z0-9_]*)$', left_text)
        if match:
            start, end = match.span()
            prefix = left_text[:start]
            suffix = text[cursor_pos:]
            
            new_text = prefix + completion + suffix
            self.setPlainText(new_text)
            self.setCursorPosition(len(prefix) + len(completion))
            
        self.popup.hide()