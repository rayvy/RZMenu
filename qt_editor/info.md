# RZMenu/qt_editor - Информация для AI агентов

## Обзор проекта

**RZMenu/qt_editor** - это Blender аддон с Qt-интерфейсом для визуального редактирования меню и UI элементов. Проект представляет собой полнофункциональный редактор с разделенными областями (areas), каждая из которых может содержать разные панели (panels).

**Технологии:** Python 3.7+, PySide6 (Qt6), Blender API

## Архитектура

### Основные компоненты

#### 1. Корневая структура
- `__init__.py` - Регистрация аддона в Blender
- `window.py` - Главное окно приложения (RZMEditorWindow)
- `actions.py` - Система действий/операторов (RZActionManager)

#### 2. Ядро системы (core/)
```
core/
├── signals.py           # Система сигналов для коммуникации
├── launcher.py          # Управление жизненным циклом Qt-приложения
├── blender_bridge.py    # Связь с Blender API (МОСТ)
├── logic.py             # Бизнес-логика элементов меню (FormulaEvaluator)
├── structure.py         # Операции со структурой элементов
├── transform.py         # Трансформации элементов
├── props.py             # Управление свойствами
├── clipboard.py         # Буфер обмена
├── maths.py             # Математические утилиты
└── read.py              # Чтение данных из Blender
```

#### 3. Система контекста (context/)
```
context/
├── manager.py           # Центральный менеджер состояния (RZContextManager - СИНГЛТОН)
├── snapshot.py          # Снимки состояния (RZContext - immutable)
├── states.py            # Состояния взаимодействия (RZInteractionState)
└── wrappers.py          # Обертки для безопасного доступа (RZElementWrapper)
```

#### 4. Системные компоненты (systems/)
```
systems/
├── operators.py         # Операторы действий (реестр OPERATOR_REGISTRY)
├── input_manager.py     # Управление вводом
├── layout_manager.py    # Управление layout'ами
└── layout.py            # Логика раскладки элементов
```

#### 5. Виджеты интерфейса (widgets/)
```
widgets/
├── area.py              # Контейнеры областей (RZAreaWidget)
├── panel_base.py        # Базовый класс панелей (RZEditorPanel)
├── outliner.py          # Панель иерархии (RZMOutlinerPanel)
├── inspector.py         # Панель свойств (RZMInspectorPanel)
├── viewport.py          # Визуальный редактор (RZViewportPanel)
├── asset_browser.py     # Браузер ассетов (RZAssetBrowserPanel)
├── preferences.py       # Настройки (RZPreferencesDialog)
└── panel_factory.py     # Фабрика панелей (PanelFactory)
```

#### 6. Конфигурация (conf/)
```
conf/
├── manager.py           # Менеджер конфигурации (ConfigManager - СИНГЛТОН)
└── defaults.py          # Дефолтные настройки (DEFAULT_CONFIG)
```

#### 7. Утилиты (utils/)
```
utils/
├── logger.py            # Логирование
├── icons.py             # Управление иконками
├── image_cache.py       # Кэширование изображений
```

## Архитектурные паттерны

### 1. Синглтон (Singleton)
- `RZContextManager` - центральный менеджер состояния
- `ConfigManager` - менеджер конфигурации
- `IntegrationManager` - управление Qt-приложением

### 2. Фабрика (Factory)
- `PanelFactory` - создание панелей разных типов
- `RZActionManager` - создание и управление действиями

### 3. Наблюдатель (Observer)
- Система сигналов через `SIGNALS` для коммуникации между компонентами
- Автономные панели подписываются на сигналы самостоятельно

### 4. Композит (Composite)
- `RZAreaWidget` может содержать другие виджеты или панели
- Динамическое построение layout'ов через `LayoutManager`

### 5. Команда (Command)
- `RZOperator` - базовый класс для всех операций
- Каждая операция имеет `poll()` для проверки возможности выполнения и `execute()` для выполнения

## Поток данных и взаимодействия

### Запуск приложения:
1. `__init__.py` регистрирует оператор `RZM_OT_LaunchQTEditor`
2. `IntegrationManager.launch()` создает Qt-приложение и главное окно
3. `RZMEditorWindow.__init__()` инициализирует все системы и UI

### Обновление данных:
1. **От Blender к Qt:** `IntegrationManager.on_depsgraph_update()` → `window.sync_from_blender()`
2. **Внутри Qt:** Компоненты испускают сигналы (`SIGNALS.structure_changed`, etc.)
3. **Панели обновляются автономно** через подписки на сигналы

### Пользовательский ввод:
1. `RZInputController` обрабатывает события клавиатуры/мыши
2. `RZActionManager` маршрутизирует действия к операторам
3. Операторы выполняют логику через `core` модули
4. Результаты транслируются через сигналы

### Контекстная система:
- `RZContextManager` поддерживает глобальное состояние (выделение, ховер, позиция курсора)
- Все операции получают `RZContext` - immutable снимок состояния
- Панели обновляют UI на основе изменений контекста

## Система моста (Blender Bridge)

### Назначение
`blender_bridge.py` обеспечивает безопасное взаимодействие между Qt-интерфейсом и Blender API, предотвращая конфликты и обеспечивая правильный контекст выполнения.

### Ключевые функции:

#### `get_stable_context()`
- Получает стабильный контекст Blender для выполнения операций
- Ищет VIEW_3D область для выполнения операций
- Возвращает словарь с `window`, `screen`, `area`, `region`, `scene`

#### `exec_in_context(op_func, **kwargs)`
- Выполняет функцию в правильном контексте Blender
- Использует `bpy.context.temp_override()` для новых версий Blender
- Обрабатывает исключения и возвращает статус

#### `safe_undo_push(message)`
- Безопасно добавляет операцию в историю отмен
- Вызывает `bpy.ops.ed.undo_push()` в правильном контексте
- Обновляет viewport'ы

### Принципы работы:
1. **Контекстная безопасность** - все операции выполняются в правильном контексте
2. **Обработка ошибок** - graceful degradation при неудачах
3. **Undo/Redo поддержка** - автоматическое управление историей операций

## Система ядра (Core)

### Компоненты ядра:

#### 1. Сигналы (signals.py)
```python
class RZSignalManager(QObject):
    structure_changed = Signal()  # Изменение структуры элементов
    transform_changed = Signal()  # Изменение трансформаций
    data_changed = Signal()       # Изменение свойств
    selection_changed = Signal()  # Изменение выделения
    context_updated = Signal()    # Изменение контекста
    config_changed = Signal(str)  # Изменение конфигурации
```

#### 2. Логика формул (logic.py - FormulaEvaluator)
- **Итеративное разрешение зависимостей** - многопроходное вычисление формул
- **Иерархические координаты** - поддержка вложенных элементов
- **Безопасное вычисление** - eval() с ограниченным контекстом

#### 3. Операции структуры (structure.py)
- `create_element()` - создание новых элементов
- `delete_elements()` - удаление элементов
- `reorder_elements()` - изменение порядка
- `reparent_element()` - изменение родителя

#### 4. Трансформации (transform.py)
- `move_elements_delta()` - перемещение элементов
- `resize_element()` - изменение размера
- `align_elements()` - выравнивание элементов

### Принципы работы ядра:
1. **Гарантия сигналов** - каждая операция испускает соответствующие сигналы
2. **Защита от конфликтов** - `IS_UPDATING_FROM_QT` предотвращает рекурсию
3. **Безопасность контекста** - все операции через `blender_bridge`

## Система контекста

### RZContextManager (Синглтон)
Центральный менеджер состояния приложения. Управляет:
- `_selected_ids: Set[int]` - выделенные элементы
- `_active_id: int` - активный элемент
- `_hover_id: int` - элемент под курсором
- `_current_state: RZInteractionState` - состояние взаимодействия
- `_hover_area: str` - область под курсором

### RZContext (Immutable снимок)
```python
class RZContext:
    def __init__(self, manager: RZContextManager):
        self.selected_ids = frozenset(manager._selected_ids)
        self.active_id = manager._active_id
        self.hover_id = manager._hover_id
        # ... другие свойства
```

### RZElementWrapper (Обертка)
Безопасный доступ к данным Blender элементов:
```python
@property
def name(self) -> str:
    el = self._get_bl_element()
    return el.element_name if el else ""
```

### Принципы работы:
1. **Иммутабельность** - контекст неизменяемый после создания
2. **Безопасность** - обертки возвращают безопасные значения при отсутствии данных
3. **Производительность** - ленивая загрузка данных

## Система операторов

### Базовый класс RZOperator
```python
class RZOperator:
    id = ""          # Уникальный идентификатор
    label = ""       # Человеко-читаемое название
    requires_selection = False  # Требует выделения

    def poll(self, context: RZContext) -> bool:
        # Проверка возможности выполнения

    def execute(self, context: RZContext, **kwargs):
        # Выполнение операции
```

### Регистр операторов
```python
OPERATOR_REGISTRY = {
    "rzm.undo": RZ_OT_Undo,
    "rzm.redo": RZ_OT_Redo,
    "rzm.delete": RZ_OT_Delete,
    # ...
}
```

### RZActionManager
- Создает экземпляры операторов из реестра
- Подключает действия к UI элементам
- Управляет состоянием кнопок (enabled/disabled)

## Система панелей

### Базовый класс RZEditorPanel
```python
class RZEditorPanel(RZPanelWidget):
    PANEL_ID = "UNDEFINED"      # Уникальный ID панели
    PANEL_NAME = "Undefined"    # Название для UI
    PANEL_ICON = "file"         # Иконка

    def on_activate(self):      # При активации панели
    def on_deactivate(self):    # При деактивации панели
    def refresh_data(self):     # Обновление данных
```

### Автономность панелей
- Каждая панель самостоятельно подписывается на сигналы
- Предотвращает RuntimeError при динамическом переключении
- Жизненный цикл: `on_activate()` → `refresh_data()` → `on_deactivate()`

### PanelFactory
```python
class PanelFactory:
    _registry = {}

    @classmethod
    def register(cls, panel_class):
        cls._registry[panel_class.PANEL_ID] = panel_class

    @classmethod
    def create_panel(cls, panel_id, parent=None):
        panel_class = cls._registry.get(panel_id)
        if panel_class:
            return panel_class(parent)
```

## Система областей (Areas)

### RZAreaWidget
Контейнер, который может содержать любую панель:
- **Динамическое переключение** - смена типа панели на лету
- **Разделение** - вертикальное/горизонтальное разделение областей
- **Закрытие** - удаление областей с автоматическим объединением

### RZAreaHeader
Заголовок области с:
- **Селектором типа панели** - выпадающий список доступных панелей
- **Кнопкой меню** - разделение, закрытие области

## Система конфигурации

### ConfigManager (Синглтон)
- Загружает/сохраняет JSON конфигурацию
- Сливает пользовательские настройки с дефолтными
- Управляет ключевыми привязками и темами

### Структура конфигурации
```json
{
  "appearance": {
    "theme": "dark",
    "font_size": 11
  },
  "keymaps": {
    "GLOBAL": {
      "Ctrl+Z": "rzm.undo",
      "Ctrl+Y": "rzm.redo"
    }
  }
}
```

## Система тем

### Централизованная система стилей
- Все стили определяются в `theme.py`
- Динамическое применение без перезапуска
- Поддержка пользовательских тем

### Структура темы
```python
DEFAULT_THEME = {
    'bg_main': '#2C313A',      # Основной фон
    'bg_panel': '#2C313A',     # Фон панелей
    'text_main': '#E0E2E4',    # Основной текст
    'accent': '#5298D4',       # Акцентный цвет
    # ...
}
```

## Система сигналов

### Глобальная система коммуникации
```python
SIGNALS = RZSignalManager()

# В ядре:
SIGNALS.structure_changed.emit()

# В панелях:
SIGNALS.structure_changed.connect(self.refresh_data)
```

### Защита от конфликтов
```python
@contextmanager
def qt_update_guard():
    global IS_UPDATING_FROM_QT
    IS_UPDATING_FROM_QT = True
    try:
        yield
    finally:
        IS_UPDATING_FROM_QT = False
```

## Система layout'ов

### LayoutManager
- Сохраняет/загружает раскладки областей
- Сериализует/десериализует дерево виджетов
- Поддерживает пользовательские layout'ы

### Структура layout'а
```json
{
  "type": "SPLITTER",
  "orientation": 1,
  "sizes": [200, 600, 300],
  "children": [
    {"type": "AREA", "panel_id": "OUTLINER"},
    {"type": "AREA", "panel_id": "VIEWPORT"},
    {"type": "AREA", "panel_id": "INSPECTOR"}
  ]
}
```

## Система ввода

### RZInputController
- Обрабатывает события клавиатуры и мыши
- Преобразует события в действия операторов
- Управляет режимами взаимодействия (alt_mode)

## Система утилит

### Логирование (logger.py)
- Централизованное логирование с уровнями
- Безопасная запись в файлы

### Кэширование изображений (image_cache.py)
- LRU кэш для изображений
- Автоматическая загрузка/выгрузка

### Управление иконками (icons.py)
- Загрузка иконок из различных источников
- Кэширование иконок

## Ключевые принципы архитектуры

### 1. Автономность компонентов
- Панели не хранят прямых ссылок друг на друга
- Все коммуникации через сигналы
- Предотвращение memory leaks

### 2. Безопасность контекста
- Все операции с Blender через `blender_bridge`
- Правильное управление undo/redo
- Защита от конфликтов Qt/Blender

### 3. Иммутабельность состояния
- Контекст неизменяемый после создания
- Предотвращение race conditions

### 4. Расширяемость
- Фабрики для создания новых компонентов
- Плагинообразная архитектура панелей
- Конфигурируемые операторы

### 5. Производительность
- Lazy loading данных
- Кэширование изображений и иконок
- Эффективные структуры данных

## Рабочий процесс разработки

### Добавление новой панели:
1. Создать класс наследующий `RZEditorPanel`
2. Определить `PANEL_ID`, `PANEL_NAME`, `PANEL_ICON`
3. Реализовать `refresh_data()`, `_connect_signals()`
4. Зарегистрировать в `PanelFactory`
5. Добавить в `window.py`

### Добавление нового оператора:
1. Создать класс наследующий `RZOperator`
2. Определить `id`, `label`, `requires_selection`
3. Реализовать `poll()`, `execute()`
4. Добавить в `OPERATOR_REGISTRY`
5. Добавить привязки клавиш в `DEFAULT_CONFIG`

### Добавление новых свойств элементов:
1. Добавить в Blender RNA структуру
2. Обновить `RZElementWrapper` свойства
3. Обновить панели (inspector, viewport)
4. Обновить операторы если нужно

## API Blender интеграции

### Основные структуры данных:
- `bpy.context.scene.rzm.elements` - коллекция элементов меню
- Каждый элемент имеет свойства: `id`, `elem_class`, `element_name`, `position`, `size`, etc.

### Операторы Blender:
- `rzm.add_image` - добавление изображений
- `rzm.load_base_icons` - загрузка базовых иконок
- `rzm.*` - другие операторы аддона

### Свойства сцены:
- `bpy.context.scene.rzm` - корневой объект аддона
- Содержит коллекции элементов, настройки, etc.

## Отладка и разработка

### Debug overlay
- `window.py` содержит `debug_label` с информацией о контексте
- Включается через `toggle_debug_panel()`

### Логирование
- `utils/logger.py` предоставляет уровни логирования
- Автоматическая запись в файлы логов

### Точки расширения
- `core/__init__.py` - фасад для core модуля
- `widgets/lib/` - базовые виджеты для переиспользования
- `systems/` - расширяемые системы

## Производительность

### Оптимизации:
- **Кэширование** - изображения, иконки, конфигурация
- **Lazy loading** - данные загружаются по требованию
- **Эффективные структуры** - frozenset для неизменяемых множеств
- **Сигналы вместо polling** - реактивные обновления

### Потенциальные узкие места:
- Поиск элементов в `RZElementWrapper._get_bl_element()` (линейный поиск)
- Перерисовка viewport при частых изменениях
- Загрузка больших изображений

## Безопасность и надежность

### Механизмы защиты:
- **Контекстная безопасность** - все операции через bridge
- **Обработка исключений** - graceful degradation
- **Валидация данных** - проверки перед операциями
- **Защита от рекурсии** - `qt_update_guard()`

### Обработка ошибок:
- Все операции возвращают статус (`{'FINISHED'}`, `{'CANCELLED'}`)
- Исключения логируются, но не ломают интерфейс
- Fallback значения для отсутствующих данных

## Заключение

RZMenu/qt_editor представляет собой хорошо структурированную, модульную архитектуру для создания сложных редакторов в экосистеме Blender. Архитектура обеспечивает:

- **Гибкость** - легкое добавление новых функций
- **Надежность** - защита от конфликтов и ошибок
- **Производительность** - оптимизированные структуры данных
- **Расширяемость** - плагинообразная архитектура

Для разработки новых функций следуйте принципам автономности компонентов, используйте существующие паттерны и всегда работайте через систему моста для безопасного взаимодействия с Blender.</content>
</xai:function_call"></xai:function_call">             
<xai:function_call name="read_file">
<parameter name="target_file">widgets/panel_factory.py
