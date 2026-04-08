# Menu-Only Export System (RZMenu Quick Export)

## Обзор

Цель — реализовать **быстрый экспорт только меню**: перегенерировать «графическую оболочку» (логику RZMenu) без повторного экспорта геометрии (mesh/buffers). 
Это позволит быстро тестировать изменения в UI, анимациях и логике, не тратя время на тяжелый процесс экспорта .buf/.ib файлов.

## User Review Required

> [!IMPORTANT]
> **Принцип патчинга "наизнанку"**: Вместо того чтобы вставлять меню в мод, мы генерируем весь .ini заново (с заглушкой вместо мешей), но **подставляем** в него сохраненный блок мешей из старого файла. 
> Это гарантирует, что структура .ini останется актуальной для RZMenu, но тяжелые данные мешей не потеряются.

> [!WARNING]
> **Теги-маркеры**: Система опирается на наличие тегов `;[META-INFO] [START] [MOD-BLOCK]` и `;[META-INFO] [END] [MOD-BLOCK]`. Если их нет (старый мод), Quick Export предложит сделать полный экспорт один раз.

---

## Предложенные изменения

### 1. Standalone Jinja2 Интеграция
Используем библиотеку Jinja2, находящуюся в `libs/jinja2`.

#### [NEW] [j2_exporter.py](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/core/j2_exporter.py)
Создадим класс `RZMenuJ2Exporter`, который:
- Инициализирует Environment из `libs/jinja2`.
- Собирает контекст (scene, rzm, и т.д.).
- Предоставляет метод `render(template_name, menu_only=False)`.
- Для `mod_file` возвращает `StubModFile`, который не падает при обращении к `.components`.

---

### 2. Обновление шаблона

#### [MODIFY] [rz_uni.j2](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/rztemplate/rz_uni.j2)
Добавим поддержку флага `menu_only`:
```jinja2
{% if not menu_only %}
;[META-INFO] [START] [MOD-BLOCK]
... (весь блок с hoyo.overridesbuffers и т.д.) ...
;[META-INFO] [END] [MOD-BLOCK]
{% else %}
;[META-INFO] [START] [MOD-BLOCK]
;[RZM-QUICK-UPDATE-PLACEHOLDER]
;[META-INFO] [END] [MOD-BLOCK]
{% endif %}
```

---

### 3. Оператор быстрого экспорта

#### [NEW] [quick_export_ops.py](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/operators/quick_export_ops.py)
Реализует `RZM_OT_QuickExportMenu`:
1. **Поиск .ini**: 
   - Сканирует все `.ini` в папке экспорта.
   - Игнорирует те, чьи имена начинаются на `DISABLED` или `ARCHIVED` (регистр не важен).
   - Выбирает **самый большой** по размеру файл (эвристика на основной мод).
2. **Патчинг**:
   - Читает старый `.ini`, извлекает контент между `;[META-INFO] [START] [MOD-BLOCK]` и `;[META-INFO] [END] [MOD-BLOCK]`.
   - Рендерит новый `.ini` через `RZMenuJ2Exporter` с флагом `menu_only=True`.
   - Заменяет `;[RZM-QUICK-UPDATE-PLACEHOLDER]` на извлеченный ранее контент мешей.
   - Перезаписывает файл.

---

### 4. Интерфейс

#### [MODIFY] [main_ui.py](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/panels/main_ui.py)
Добавим кнопку:
- `⚡ Quick Update (UI Only)` рядом с основным экспортом.

---

## Открытые вопросы (из ответов пользователя)

- **mod_file**: Решено через заглушку в J2 экспортере и флаг `menu_only` в шаблоне.
- **Поиск файла**: Используем эвристику "самый большой не-архивный".
- **Теги**: Если теги не найдены, Quick Export не сработает (безопасность).

## Verification Plan

### Manual Verification
1. Сделать полный экспорт мода.
2. Изменить какой-нибудь параметр в RZMenu (например, цвет кнопки или текст).
3. Нажать `Quick Update (UI Only)`.
4. Проверить `.ini` файл:
   - Секции UI должны обновиться.
   - Секции `TextureOverride` и `Resource` (между тегами MOD-BLOCK) должны остаться нетронутыми.
5. Запустить игру и убедиться, что мод работает и изменения UI применились.

### Automated Tests (Scripts)
- Тест эвристики поиска .ini: создать несколько файлов (small.ini, big.ini, DISABLED_big.ini) и убедиться, что выбирается `big.ini`.
- Тест патчинга: подать на вход строку с тегами и убедиться, что содержимое между ними сохраняется.
