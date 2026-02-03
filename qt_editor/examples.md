# Examples & Implementation Patterns

Этот документ содержит эталонные примеры реализации функционала разной сложности, с учетом архитектурных требований RZMenu.

## 1. Базовый уровень: Простое свойство
**Задача:** Добавить текстовое поле для редактирования свойства `my_title`.

### Архитектура:
1.  **Backend:** Blender Property (`bpy.types`).
2.  **Mapping:** `qt_editor/core/props.py`.
3.  **UI:** Виджет, который обновляется без пересоздания.

```python
# --- 1. Blender (где-то в properties.py) ---
class MyData(bpy.types.PropertyGroup):
    my_title: bpy.props.StringProperty(name="Title", default="New Item")

# --- 2. QT Prop Mapping (core/props.py) ---
PROP_MAP.update({
    "my_title": ("my_title", None, 'D'), # 'D' = Data Changed signal
})

# --- 3. UI Widget (widgets/my_panel.py) ---
class TitleWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        
        self.label = QtWidgets.QLabel("Title:")
        self.input = RZLineEdit() # Кастомный виджет с стилями
        self.input.editingFinished.connect(self.on_edit)
        
        layout.addWidget(self.label)
        layout.addWidget(self.input)
        
        # Флаг блокировки для предотвращения циклов (signal -> update -> signal)
        self._is_updating = False

    def on_edit(self):
        if self._is_updating: return
        val = self.input.text()
        # Вызываем универсальный апдейтер
        # target_ids берется из контекста селекции
        core.update_property_multi(current_selection_ids, "my_title", val)

    def update_ui(self, data_obj):
        """
        Stateful Update: Меняем текст ТОЛЬКО если он отличается.
        Не пересоздаем виджеты!
        """
        self._is_updating = True
        
        new_text = getattr(data_obj, "my_title", "")
        if self.input.text() != new_text:
            self.input.setText(new_text)
            
        self._is_updating = False
```

## 2. Средний уровень: Список с Non-Destructive Update
**Задача:** Управление списком тегов (строк). Добавление, удаление, редактирование без потери фокуса.

### Ключевой паттерн:
Вместо `clear_layout()` и `for item in list: add_widget()`, мы итерируемся по **существующим** виджетам и обновляем их. Лишние удаляем, недостающие добавляем.

```python
class TagListWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.rows_layout = QtWidgets.QVBoxLayout()
        self.layout.addLayout(self.rows_layout)
        
        self.btn_add = RZPushButton("+ Add Tag")
        self.btn_add.clicked.connect(lambda: self._call_op("add_tag"))
        self.layout.addWidget(self.btn_add)
        
        self.widgets_cache = [] # Список (Widget, BoundDataIndex)

    def update_ui(self, tag_collection):
        target_count = len(tag_collection)
        current_count = len(self.widgets_cache)
        
        # 1. Если виджетов меньше чем данных -> Создаем новые
        while len(self.widgets_cache) < target_count:
            row_idx = len(self.widgets_cache)
            row_widget = self._create_row_widget(row_idx)
            self.rows_layout.addWidget(row_widget)
            self.widgets_cache.append(row_widget)
            
        # 2. Если виджетов больше чем данных -> Удаляем (с конца)
        while len(self.widgets_cache) > target_count:
            w = self.widgets_cache.pop()
            w.deleteLater() # Безопасное удаление QT
            
        # 3. Обновляем данные во ВСЕХ (и старых и новых)
        for i, tag_item in enumerate(tag_collection):
            widget = self.widgets_cache[i]
            widget.update_state(tag_item, i) # Делегируем обновление внутрь строки

    def _create_row_widget(self, index):
        # Создаем контейнер строки ОДИН РАЗ
        w = TagRow(index)
        w.delete_requested.connect(self._on_delete_row)
        return w

class TagRow(QtWidgets.QWidget):
    delete_requested = QtCore.Signal(int)
    
    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.index = index
        self.layout = QtWidgets.QHBoxLayout(self)
        
        self.inp = RZLineEdit()
        self.inp.textChanged.connect(self._on_text_change) # Live update
        
        self.btn_del = RZPushButton("X")
        self.btn_del.clicked.connect(lambda: self.delete_requested.emit(self.index))
        
        self.layout.addWidget(self.inp)
        self.layout.addWidget(self.btn_del)
        
        self._block = False

    def update_state(self, data, new_index):
        self._block = True
        self.index = new_index # Индекс может сместиться!
        
        cur_val = data.name
        if self.inp.text() != cur_val:
            self.inp.setText(cur_val) # Обновляем только если изменилось
            
        self._block = False

    def _on_text_change(self, text):
        if self._block: return
        # Вызов оператора обновления по индексу
        core.ops.update_tag(index=self.index, value=text)
```

## 3. Сложный уровень: Динамический Grid с вложенностью
**Задача:** Grid из карточек (например, Текстуры), где каждая карточка имеет свое состояние (свернута/развернута) и вложенные списки.

### Решение:
Использование `Keyed Cache`. Мы идентифицируем виджеты не по индексу (который меняется при сортировке), а по `UID` или `Name` (уникальному ключу).

```python
class TextureGridManager(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QtWidgets.QVBoxLayout(self)
        self.items_map = {} # { "unique_resource_name": TextureCardWidget }

    def update_ui(self, textures_data):
        """
        textures_data: list of property groups from Blender
        """
        incoming_keys = set()
        
        # 1. Синхронизация (Create / Update)
        for i, tex in enumerate(textures_data):
            # Используем имя как ключ (если оно уникально) или хеш
            key = tex.name 
            incoming_keys.add(key)
            
            if key not in self.items_map:
                # CREATION
                card = TextureCardWidget()
                self.layout.addWidget(card)
                self.items_map[key] = card
            
            # UPDATE
            # Важно: передаем index, так как он нужен для операторов
            self.items_map[key].update_data(tex, index=i)

        # 2. Очистка (Delete)
        # Удаляем виджеты, ключей которых нет в новых данных
        keys_to_remove = []
        for key, widget in self.items_map.items():
            if key not in incoming_keys:
                widget.deleteLater()
                keys_to_remove.append(key)
        
        for k in keys_to_remove:
            del self.items_map[k]

class TextureCardWidget(RZGroupBox):
    def update_data(self, tex_data, index):
        self.setTitle(tex_data.name)
        
        # --- Nested Optimization ---
        # Если виджет свернут, НЕ ОБНОВЛЯЕМ его содержимое для скорости
        if not tex_data.is_expanded:
            if self.content_area.isVisible():
                self.content_area.setVisible(False)
            return
            
        self.content_area.setVisible(True)
        
        # ... обновление внутренних полей по паттерну #1
        if self.width_spin.value() != tex_data.width:
            self.width_spin.setValue(tex_data.width)
```

## Резюме
1. **Никогда не делайте `layout.clear()`** в `update_ui`, если пользователь может в этот момент взаимодействовать с UI.
2. Используйте **State guarding** (`self._block_signals = True`), чтобы изменения из кода не вызывали обратные сигналы.
3. Для списков используйте **Object Pools** или **Widget Caching** (привязка по индексу или UID).
