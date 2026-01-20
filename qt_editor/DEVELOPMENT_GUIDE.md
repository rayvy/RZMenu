# Руководство по разработке RZMenu/qt_editor

## Содержание
1. [Введение](#введение)
2. [Архитектурные принципы](#архитектурные-принципы)
3. [Создание простых операторов](#создание-простых-операторов)
4. [Создание панелей](#создание-панелей)
5. [Добавление новых свойств элементов](#добавление-новых-свойств-элементов)
6. [Создание сложных функций](#создание-сложных-функций)
7. [Работа с системой моста](#работа-с-системой-моста)
8. [Отладка и тестирование](#отладка-и-тестирование)

## Введение

RZMenu/qt_editor - это модульная архитектура для создания редакторов в Blender. Перед началом разработки важно понять ключевые принципы:

- **Автономность компонентов** - каждый компонент работает независимо
- **Система сигналов** - коммуникация через сигналы, не прямые ссылки
- **Безопасность контекста** - все операции через `blender_bridge`
- **Иммутабельность состояния** - контекст неизменяемый

## Архитектурные принципы

### 1. Принцип автономности
```python
# ❌ ПЛОХО: Прямая ссылка на другие компоненты
class MyPanel:
    def __init__(self, other_panel):
        self.other_panel = other_panel

# ✅ ХОРОШО: Автономность через сигналы
class MyPanel(RZEditorPanel):
    def _connect_signals(self):
        SIGNALS.selection_changed.connect(self.refresh_data)
```

### 2. Принцип безопасности контекста
```python
# ❌ ПЛОХО: Прямой доступ к bpy
def my_function():
    bpy.context.scene.rzm.elements.add()

# ✅ ХОРОШО: Через систему моста
def my_function():
    core.create_element("BUTTON", 0, 0)
```

### 3. Принцип неизменяемости
```python
# ❌ ПЛОХО: Изменение контекста напрямую
def modify_context(ctx):
    ctx.selected_ids.add(123)

# ✅ ХОРОШО: Через менеджер контекста
def modify_context():
    manager = RZContextManager.get_instance()
    manager.set_selection({123}, 123)
```

## Создание простых операторов

### Шаг 1: Создание базового оператора

Создайте новый файл `systems/operators/my_operators.py`:

```python
from .. import core
from ..context import RZContextManager, RZContext
from . import RZOperator

class RZ_OT_MySimpleOperator(RZOperator):
    id = "rzm.my_simple_op"
    label = "My Simple Operation"

    def execute(self, context: RZContext, **kwargs):
        # Ваша логика здесь
        print(f"Выполняю операцию с {len(context.selected_ids)} выделенными элементами")
        return {'FINISHED'}
```

### Шаг 2: Регистрация оператора

Добавьте в `systems/operators.py`:

```python
# Импорт вашего оператора
from .my_operators import RZ_OT_MySimpleOperator

# Добавьте в OPERATOR_REGISTRY
OPERATOR_REGISTRY.update({
    "rzm.my_simple_op": RZ_OT_MySimpleOperator,
    # ... другие операторы
})
```

### Шаг 3: Добавление горячих клавиш

Добавьте в `conf/defaults.py`:

```python
DEFAULT_CONFIG = {
    "keymaps": {
        "GLOBAL": {
            # ... существующие привязки
            "Ctrl+Shift+M": "rzm.my_simple_op",
        }
    },
    # ... остальная конфигурация
}
```

### Шаг 4: Добавление кнопки в UI

Добавьте в `window.py`, в метод `setup_toolbar()`:

```python
def setup_toolbar(self):
    # ... существующие кнопки
    add_btn("My Op", "rzm.my_simple_op")
```

## Создание панелей

### Шаг 1: Создание базовой панели

Создайте новый файл `widgets/my_panel.py`:

```python
from PySide6 import QtWidgets
from .panel_base import RZEditorPanel
from .. import core
from ..core.signals import SIGNALS
from ..context import RZContextManager

class RZMyPanel(RZEditorPanel):
    """
    Моя новая панель для специальных функций.
    """

    PANEL_ID = "MY_PANEL"
    PANEL_NAME = "My Panel"
    PANEL_ICON = "star"  # Иконка из системы иконок

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        # Создаем UI
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.label = QtWidgets.QLabel("Привет, мир!")
        layout.addWidget(self.label)

        self.button = QtWidgets.QPushButton("Нажми меня")
        self.button.clicked.connect(self.on_button_click)
        layout.addWidget(self.button)

        layout.addStretch()

    def _connect_signals(self):
        """Подписываемся на сигналы."""
        SIGNALS.selection_changed.connect(self.refresh_data)
        SIGNALS.structure_changed.connect(self.refresh_data)

    def _disconnect_signals(self):
        """Отписываемся от сигналов."""
        try:
            SIGNALS.selection_changed.disconnect(self.refresh_data)
            SIGNALS.structure_changed.disconnect(self.refresh_data)
        except:
            pass  # Безопасность на случай если сигналы уже отключены

    def refresh_data(self):
        """Обновляем данные панели."""
        if not self._is_panel_active:
            return

        ctx = RZContextManager.get_instance().get_snapshot()

        if ctx.selected_ids:
            self.label.setText(f"Выделено элементов: {len(ctx.selected_ids)}")
        else:
            self.label.setText("Ничего не выделено")

    def on_button_click(self):
        """Обработчик нажатия кнопки."""
        # Получаем доступ к action manager для выполнения операций
        action_manager = self.get_action_manager()
        if action_manager:
            action_manager.run("rzm.select_all")

    def on_activate(self):
        """Вызывается при активации панели."""
        super().on_activate()
        # Дополнительная инициализация если нужна
        print(f"Панель {self.PANEL_ID} активирована")

    def on_deactivate(self):
        """Вызывается при деактивации панели."""
        super().on_deactivate()
        # Очистка ресурсов если нужна
        print(f"Панель {self.PANEL_ID} деактивирована")
```

### Шаг 2: Регистрация панели

Добавьте в `window.py`, в метод `_register_panels()`:

```python
def _register_panels(self):
    """Register all panel classes with the PanelFactory."""
    PanelFactory.register(outliner.RZMOutlinerPanel)
    PanelFactory.register(inspector.RZMInspectorPanel)
    PanelFactory.register(viewport.RZViewportPanel)
    PanelFactory.register(asset_browser.RZAssetBrowserPanel)

    # Регистрируем вашу новую панель
    from .widgets import my_panel
    PanelFactory.register(my_panel.RZMyPanel)
```

### Шаг 3: Добавление иконки (опционально)

Если вам нужна специальная иконка, добавьте в `utils/icons.py`:

```python
ICON_MAP.update({
    "star": "★",  # Или путь к файлу иконки
})
```

## Добавление новых свойств элементов

### Шаг 1: Добавление в Blender RNA

Это требует изменений в основном аддоне RZMenu (не в qt_editor). Добавьте в RNA структуру:

```python
# В основном аддоне RZMenu
class RZElement(PropertyGroup):
    # ... существующие свойства

    my_custom_prop: FloatProperty(
        name="My Custom Property",
        default=1.0,
        min=0.0,
        max=10.0
    )
```

### Шаг 2: Обновление обертки контекста

Добавьте в `context/wrappers.py`:

```python
class RZElementWrapper:
    # ... существующие свойства

    @property
    def my_custom_prop(self) -> float:
        el = self._get_bl_element()
        return getattr(el, "my_custom_prop", 1.0) if el else 1.0
```

### Шаг 3: Обновление панели инспектора

Добавьте в `widgets/inspector.py`:

```python
def _init_properties_ui(self):
    # ... существующие группы

    # === GROUP: MY CUSTOM PROPERTIES ===
    grp_custom = RZGroupBox("Custom Properties")
    form_custom = QtWidgets.QFormLayout(grp_custom)

    self.spin_my_prop = RZSpinBox()
    self.spin_my_prop.setRange(0.0, 10.0)
    self.spin_my_prop.setSingleStep(0.1)
    self.spin_my_prop.valueChanged.connect(lambda v: self._emit_change('my_custom_prop', float(v)))
    form_custom.addRow("My Prop:", self.spin_my_prop)

    self.layout_props.addWidget(grp_custom)
```

Добавьте в метод `update_ui()`:

```python
def update_ui(self, details):
    # ... существующий код

    # Обновляем кастомное свойство
    if details:
        self.spin_my_prop.blockSignals(True)
        self.spin_my_prop.setValue(details.get('my_custom_prop', 1.0))
        self.spin_my_prop.blockSignals(False)
    else:
        self.spin_my_prop.setValue(1.0)
```

### Шаг 4: Обновление метода получения деталей

Добавьте в `core/read.py`:

```python
def get_selection_details(selected_ids, active_id):
    # ... существующий код

    if active_element:
        details.update({
            # ... существующие детали
            'my_custom_prop': getattr(active_element, 'my_custom_prop', 1.0),
        })

    return details
```

## Создание сложных функций

### Пример 1: Оператор с UI диалогом

```python
class RZ_OT_CreateElementDialog(RZOperator):
    id = "rzm.create_element_dialog"
    label = "Create Element with Dialog"

    def execute(self, context: RZContext, **kwargs):
        # Импортируем здесь чтобы избежать circular imports
        from PySide6 import QtWidgets

        # Получаем доступ к окну через kwargs
        window = kwargs.get('window')
        if not window:
            return {'CANCELLED'}

        # Создаем диалог
        dialog = QtWidgets.QDialog(window)
        dialog.setWindowTitle("Create New Element")

        layout = QtWidgets.QVBoxLayout(dialog)

        # Тип элемента
        layout.addWidget(QtWidgets.QLabel("Element Type:"))
        cb_type = QtWidgets.QComboBox()
        cb_type.addItems(["BUTTON", "TEXT", "SLIDER", "CONTAINER"])
        layout.addWidget(cb_type)

        # Позиция X
        layout.addWidget(QtWidgets.QLabel("X Position:"))
        spin_x = QtWidgets.QSpinBox()
        spin_x.setRange(-10000, 10000)
        layout.addWidget(spin_x)

        # Позиция Y
        layout.addWidget(QtWidgets.QLabel("Y Position:"))
        spin_y = QtWidgets.QSpinBox()
        spin_y.setRange(-10000, 10000)
        layout.addWidget(spin_y)

        # Кнопки
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        # Показываем диалог
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            element_type = cb_type.currentText()
            x = spin_x.value()
            y = spin_y.value()

            # Создаем элемент
            new_id = core.create_element(element_type, x, y)

            if new_id:
                # Выделяем созданный элемент
                RZContextManager.get_instance().set_selection({new_id}, new_id)

                return {'FINISHED'}

        return {'CANCELLED'}
```

### Пример 2: Панель с кастомным рендерером

```python
class RZCustomRendererPanel(RZEditorPanel):
    PANEL_ID = "CUSTOM_RENDERER"
    PANEL_NAME = "Custom Renderer"
    PANEL_ICON = "palette"

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        layout = QtWidgets.QVBoxLayout(self)

        # Создаем виджет для рендеринга
        self.renderer = QtWidgets.QWidget()
        self.renderer.setMinimumSize(200, 200)
        layout.addWidget(self.renderer)

        # Кнопки управления
        btn_layout = QtWidgets.QHBoxLayout()

        self.btn_render = QtWidgets.QPushButton("Render")
        self.btn_render.clicked.connect(self.render_scene)
        btn_layout.addWidget(self.btn_render)

        self.btn_clear = QtWidgets.QPushButton("Clear")
        self.btn_clear.clicked.connect(self.clear_render)
        btn_layout.addWidget(self.btn_clear)

        layout.addLayout(btn_layout)

    def _connect_signals(self):
        SIGNALS.structure_changed.connect(self.on_structure_changed)
        SIGNALS.transform_changed.connect(self.on_transform_changed)

    def _disconnect_signals(self):
        try:
            SIGNALS.structure_changed.disconnect(self.on_structure_changed)
            SIGNALS.transform_changed.disconnect(self.on_transform_changed)
        except:
            pass

    def render_scene(self):
        """Рендерим текущую сцену."""
        # Получаем данные элементов
        all_data = core.get_all_elements_list()

        # Выполняем кастомный рендеринг
        # (здесь ваша логика рендеринга)

        # Обновляем отображение
        self.renderer.update()

    def clear_render(self):
        """Очищаем рендеринг."""
        # Логика очистки
        self.renderer.update()

    def on_structure_changed(self):
        """Обработчик изменения структуры."""
        # Автоматически обновляем рендеринг при изменениях
        if self.chk_auto_render.isChecked():
            self.render_scene()

    def on_transform_changed(self):
        """Обработчик изменения трансформаций."""
        # Аналогично структуре
        if self.chk_auto_render.isChecked():
            self.render_scene()

    def refresh_data(self):
        """Обновляем данные панели."""
        if not self._is_panel_active:
            return

        # Обновляем информацию о сцене
        scene_info = core.get_scene_info()
        # Обновляем UI на основе scene_info
```

### Пример 3: Система плагинов

Создайте структуру для загрузки плагинов:

```python
# plugins/__init__.py
class PluginManager:
    def __init__(self):
        self.plugins = {}

    def load_plugin(self, plugin_path):
        """Загружаем плагин из файла."""
        import importlib.util

        spec = importlib.util.spec_from_file_location("plugin", plugin_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Регистрируем компоненты плагина
        if hasattr(module, 'register_plugin'):
            module.register_plugin(self)

    def register_operator(self, op_class):
        """Регистрируем оператор плагина."""
        from ..systems.operators import OPERATOR_REGISTRY
        OPERATOR_REGISTRY[op_class.id] = op_class

    def register_panel(self, panel_class):
        """Регистрируем панель плагина."""
        from ..widgets.panel_factory import PanelFactory
        PanelFactory.register(panel_class)
```

Пример плагина:

```python
# my_plugin.py
from PySide6 import QtWidgets
from qt_editor.widgets.panel_base import RZEditorPanel
from qt_editor.systems.operators import RZOperator
from qt_editor import core
from qt_editor.context import RZContext

class MyPluginPanel(RZEditorPanel):
    PANEL_ID = "MY_PLUGIN_PANEL"
    PANEL_NAME = "My Plugin"
    PANEL_ICON = "plugin"

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Plugin Panel!"))

class MyPluginOperator(RZOperator):
    id = "rzm.plugin_op"
    label = "Plugin Operation"

    def execute(self, context: RZContext, **kwargs):
        print("Plugin operation executed!")
        return {'FINISHED'}

def register_plugin(plugin_manager):
    """Регистрируем компоненты плагина."""
    plugin_manager.register_panel(MyPluginPanel)
    plugin_manager.register_operator(MyPluginOperator)
```

## Работа с системой моста

### Основные правила

1. **Всегда используйте bridge для операций с Blender**
2. **Никогда не обращайтесь напрямую к bpy из UI кода**
3. **Используйте контекстную защиту**

### Примеры правильного использования:

```python
# ✅ Правильно: через core функции
def safe_blender_operation():
    # core функции автоматически используют bridge
    new_id = core.create_element("BUTTON", 100, 100)

# ✅ Правильно: явное использование bridge
def explicit_bridge_usage():
    from ..core import blender_bridge

    def blender_code():
        # Ваш код с bpy
        bpy.ops.my_operator()

    blender_bridge.exec_in_context(blender_code)

# ❌ Неправильно: прямой доступ к bpy
def unsafe_operation():
    # Это может сломаться в runtime
    bpy.context.scene.rzm.elements.add()
```

### Создание новых bridge функций

Добавьте в `core/blender_bridge.py`:

```python
def my_custom_bridge_function(param1, param2):
    """Моя кастомная функция моста."""

    def blender_operation():
        # Код выполняемый в контексте Blender
        scene = bpy.context.scene
        # ... ваша логика
        return result

    return exec_in_context(blender_operation)
```

## Отладка и тестирование

### Debug overlay

Включите debug overlay в `window.py`:

```python
def toggle_debug_panel(self):
    """Переключение debug панели."""
    is_visible = not self.debug_label.isVisible()
    self.debug_label.setVisible(is_visible)
    if is_visible:
        self.debug_timer.start(50)  # Обновление каждые 50мс
    else:
        self.debug_timer.stop()
```

### Логирование

Используйте систему логирования:

```python
from ..utils import logger

def my_function():
    logger.info("Начинаем операцию")
    try:
        # ваш код
        logger.debug(f"Обработано {count} элементов")
    except Exception as e:
        logger.error(f"Ошибка в my_function: {e}")
        raise
```

### Тестирование сигналов

```python
def test_signals():
    """Тестируем систему сигналов."""
    from ..core.signals import SIGNALS

    # Создаем mock обработчик
    call_count = [0]
    def mock_handler():
        call_count[0] += 1

    # Подписываемся
    SIGNALS.structure_changed.connect(mock_handler)

    # Генерируем сигнал
    SIGNALS.structure_changed.emit()

    # Проверяем
    assert call_count[0] == 1, "Сигнал не сработал"

    # Отписываемся
    SIGNALS.structure_changed.disconnect(mock_handler)
```

### Тестирование операторов

```python
def test_operator():
    """Тестируем оператор."""
    from ..systems.operators import RZ_OT_SelectAll
    from ..context import RZContextManager

    # Создаем оператор
    op = RZ_OT_SelectAll()

    # Создаем контекст
    ctx = RZContextManager.get_instance().get_snapshot()

    # Проверяем poll (может ли выполниться)
    assert op.poll(ctx), "Оператор должен быть доступен"

    # Выполняем
    result = op.execute(ctx)
    assert result == {'FINISHED'}, "Оператор должен завершиться успешно"
```

## Лучшие практики

### 1. Обработка ошибок
```python
def safe_operation():
    try:
        # ваш код
        return {'FINISHED'}
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        return {'CANCELLED'}
```

### 2. Безопасность сигналов
```python
def _disconnect_signals(self):
    """Безопасная отписка от сигналов."""
    try:
        SIGNALS.some_signal.disconnect(self.handler)
    except (RuntimeError, TypeError):
        # Сигнал уже отключен или объект удален
        pass
```

### 3. Оптимизация производительности
```python
def refresh_data(self):
    """Оптимизированная перерисовка."""
    if not self._is_panel_active:
        return  # Не обновляемся если панель не активна

    # Используем таймер для throttling частых обновлений
    if hasattr(self, '_refresh_timer'):
        self._refresh_timer.stop()

    self._refresh_timer = QtCore.QTimer()
    self._refresh_timer.setSingleShot(True)
    self._refresh_timer.timeout.connect(self._do_refresh)
    self._refresh_timer.start(16)  # ~60 FPS
```

### 4. Управление памятью
```python
def on_deactivate(self):
    """Правильная очистка ресурсов."""
    super().on_deactivate()

    # Останавливаем таймеры
    if hasattr(self, '_refresh_timer'):
        self._refresh_timer.stop()

    # Очищаем кэши
    if hasattr(self, '_image_cache'):
        self._image_cache.clear()

    # Отписываемся от всех сигналов
    self._disconnect_signals()
```

## Заключение

При разработке для RZMenu/qt_editor всегда следуйте принципам:

1. **Автономность** - компоненты работают независимо
2. **Безопасность** - все через систему моста
3. **Сигналы** - коммуникация через сигналы
4. **Обработка ошибок** - graceful degradation
5. **Тестирование** - проверяйте все новые функции

Используйте существующие паттерны и компоненты как основу для новых функций. Это обеспечит совместимость и надежность вашей разработки.</content>
</xai:function_call=""></xai:function_call">  

<xai:function_call name="run_terminal_cmd">
<parameter name="command">echo "Файлы созданы: info.md и DEVELOPMENT_GUIDE.md"
