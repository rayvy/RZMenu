# Menu-Only Export System (RZMenu Quick Export)

## Обзор

Цель — реализовать **быстрый экспорт только меню**: перегенерировать `рзменю`-секции `.ini` файла без запуска полноценного экспорта геометрии из Blender. Секции «меню» — это всё, что генерируют шаблоны из `rztemplate/modules/` (`data.j2`, `keymap.j2`, `run_links.j2`, `core.j2`, `container.j2` и т.д.). Секции «мяса мода» — это `TextureOverride*`, `Resource*`, шейп-буферы — всё, что требует реального экспорта `.buf`/`.ib` файлов.

---

## Архитектура: Разделение секций через теги в .ini

### Теги-маркеры в генерируемом .ini

Аналогично существующим `;[META-INFO] [START]...[END]` тегам для Mesh-секций, вводим два новых тега-маркера уровня секций:

```ini
;[RZM-MENU] [START]
... сгенерированные секции меню (data, keymap, core, elements, run_links) ...
;[RZM-MENU] [END]

;[RZM-MOD] [START]
... TextureOverride*, Resource*, шейп-буферы, всё "мясо" мода ...
;[RZM-MOD] [END]
```

**Замена при Quick Export:**
Механизм Quick Export открывает существующий `.ini`, находит блок между `[RZM-MENU] [START]` и `[RZM-MENU] [END]`, и заменяет его содержимое на свежесгенерированное — не трогая `[RZM-MOD]` блок.

---

## Что входит в какую зону

| Зона         | Шаблоны                                                           | Содержимое .ini                                                        |
|--------------|-------------------------------------------------------------------|------------------------------------------------------------------------|
| `[RZM-MENU]` | `data.j2`, `keymap.j2`, `run_links.j2`, `core.j2`, `elements.j2`, `container.j2`, `modules.j2` | `[Constants]`, `[KeyXxx]`, `[CommandListXxx]`, `[CustomShaderRCI2D]`, `[CustomShaderDI2D]` |
| `[RZM-MOD]`  | `rz_MERGED_HOYO.j2` → `overridesbuffers`, `overridesibs`, `resourcebuffers`, `resourcetextures` | `[TextureOverride*]`, `[Resource*]` с `.buf`/`.ib` именами файлов |

---

## Компоненты реализации

### 1. Новый шаблон `rz_menu_only.j2`

**Путь:** `rztemplate/rz_menu_only.j2`

Лёгкий standalone шаблон, который рендерит только «меню-секции», оборачивая их в теги:

```jinja2
;[RZM-MENU] [START]
{% import "modules/data.j2" as data with context %}
{% import "modules/core.j2" as core with context %}
{% import "modules/keymap.j2" as keymap with context %}
{% import "modules/run_links.j2" as run_links with context %}
{% import "modules/modules.j2" as modules with context %}

{{ data.config(mod_file, scene) }}
{{ core.entryPoint(mod_file, scene) }}
{{ core.baseCompute(mod_file, scene) }}
{{ core.menuDrawUi(mod_file, scene) }}
{{ keymap.main_button(mod_file, scene) }}
{{ keymap.generate_keybinds(mod_file, scene) }}
{{ run_links.generate_run_links(mod_file, scene) }}
{{ modules.generate_addons(mod_file, scene) }}
;[RZM-MENU] [END]
```

Этот шаблон не трогает `rz_helper.j2` (smart_draw) и не зависит от `mod_file.components`.

---

### 2. Обновление основного шаблона `rz_MERGED_HOYO.j2` (и других)

В итоговом `.ini` весь блок меню должен быть обёрнут тегами. Это означает, что при **полном** экспорте тоже генерируются теги.

**Изменение `rz_MERGED_HOYO.j2`** (или аналогичного файла, где вызываются все макросы):
```diff
+ ;[RZM-MENU] [START]
  {{ data.config(...) }}
  {{ core.entryPoint(...) }}
  ...
+ ;[RZM-MENU] [END]
+ ;[RZM-MOD] [START]
  {{ overridesbuffers(...) }}
  {{ overridesibs(...) }}
  {{ resourcebuffers(...) }}
  {{ resourcetextures(...) }}
+ ;[RZM-MOD] [END]
```

> [!IMPORTANT]
> Это изменение ломает существующие `.ini` файлы у пользователей, у которых нет тегов. Quick Export должен уметь работать и в режиме «перезаписать весь .ini», и в режиме «обновить только [RZM-MENU] блок».

---

### 3. Новый оператор `RZM_OT_QuickExportMenu`

**Путь:** `operators/quick_export_ops.py` (новый файл)

**Логика:**

```python
class RZM_OT_QuickExportMenu(bpy.types.Operator):
    bl_idname = "rzm.quick_export_menu"
    bl_label = "Quick Export Menu"
    bl_description = "Regenerate only the menu sections of the .ini without full export"
    
    def execute(self, context):
        # 1. Определяем путь к .ini
        target = get_target_path(context)
        ini_path = find_ini_in_path(target)
        
        # 2. Рендерим шаблон rz_menu_only.j2
        new_menu_block = render_menu_template(context)
        
        # 3. Если .ini существует - патчим его
        if ini_path and os.path.exists(ini_path):
            if has_rzm_tags(ini_path):
                patch_menu_section(ini_path, new_menu_block)
            else:
                # Нет тегов - предупреждаем пользователя
                # Опция: перезаписать весь .ini или отмена
                ...
        else:
            # .ini нет - создаём только меню-секцию
            write_new_ini(ini_path, new_menu_block)
```

**`render_menu_template(context)`** — использует Jinja2 Environment (как в EFMI `ini_maker.py`) для рендера `rz_menu_only.j2` с теми же переменными контекста, что и полный экспорт, но без реального `mod_file` (или с минимальным заглушечным `mod_file`).

**`patch_menu_section(ini_path, new_block)`** — читает `.ini`, находит строки между маркерами, заменяет их.

---

### 4. Собственный Jinja2 Exporter для RZMenu

> [!NOTE]
> Ты прав — нужен свой J2 экспортер. Он уже фактически распределён по коду (некоторые части существуют в `setup_ops.py` или аналогах), но нужно вынести это в отдельный модуль.

**Путь:** `core/j2_exporter.py` (новый модуль)

```python
class RZMenuJ2Exporter:
    """Standalone Jinja2 рендерер для RZMenu шаблонов."""
    
    def __init__(self, context):
        self.context = context
        self.scene = context.scene
        self.rzm = context.scene.rzm
        
    def build_env(self):
        """Создаёт Jinja2 Environment с правильными путями."""
        template_dir = Path(__file__).parent.parent / "rztemplate"
        env = Environment(
            loader=FileSystemLoader([str(template_dir)]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        return env
        
    def build_context(self, mod_file=None):
        """Собирает контекст для шаблона."""
        return {
            'scene': self.scene,
            'mod_file': mod_file or DummyModFile(),
            'enumerate': enumerate,
            # ... другие глобальные переменные
        }
    
    def render_menu(self) -> str:
        """Рендерит только меню-секцию."""
        env = self.build_env()
        template = env.get_template("rz_menu_only.j2")
        return template.render(self.build_context())
    
    def render_full(self, mod_file) -> str:
        """Полный рендер (для будущей интеграции)."""
        ...
```

**`DummyModFile`** — заглушка-объект с пустыми `components = []` чтобы шаблоны не падали при обращении к `mod_file.components`.

---

### 5. Кнопка в UI

**Место:** N-Panel в разделе экспорта (рядом с обычным Export) или в Qt Editor тулбоксе.

```python
# В panels/ или qt_editor/
row.operator("rzm.quick_export_menu", text="⚡ Quick Export Menu", icon='FILE_REFRESH')
```

---

## Открытые вопросы

> [!IMPORTANT]
> **Вопрос 1: Что такое `mod_file` при Quick Export?**
> При полном экспорте `mod_file` — это объект с данными всех компонентов (VB хэши, стайды и т.д.), который строится в процессе экспорта геометрии.
> При Quick Export нам нужно знать: нужен ли живой `mod_file` для меню-шаблонов?
>
> **Ответ из анализа шаблонов:** `data.j2`, `keymap.j2`, `run_links.j2` используют только `scene.rzm.*`. `customDrawVars` в `data.j2` обращается к `mod_file.components`, но это можно заглушить пустым списком. **Итог: для Quick Export можно использовать `DummyModFile` с пустыми компонентами.**

> [!IMPORTANT]
> **Вопрос 2: Где физически хранится уже готовый .ini?**
> В папке, определяемой `get_target_path(context)`. Там может быть несколько `.ini` файлов. Нужно ли фильтровать по имени, или патчить все найденные? **Предложение: патчить первый найденный, или тот, что соответствует имени проекта.**

> [!WARNING]
> **Вопрос 3: Как быть со старыми .ini без тегов?**
> Если пользователь делает Quick Export на .ini-файл, сгенерированном без тегов — механизм не сможет определить, где заканчивается меню и начинается мод.
> **Варианты:**
> - А) Показать ошибку и потребовать полный ре-экспорт сначала
> - Б) Сделать полный перезаписью через тот же Quick Export (только меню, мод-секция игнорируется — это опасно)
> - **Рекомендация: Вариант А**

---

## Предлагаемые изменения по файлам

### [NEW] `rztemplate/rz_menu_only.j2`
Лёгкий шаблон только для меню-секций с тегами `[RZM-MENU] [START/END]`.

---

### [NEW] `operators/quick_export_ops.py`
Оператор `RZM_OT_QuickExportMenu` — патч существующего `.ini`.

---

### [NEW] `core/j2_exporter.py`
`RZMenuJ2Exporter` — собственный standalone Jinja2 рендерер, не зависящий от EFMI.

---

### [MODIFY] `rztemplate/rz_MERGED_HOYO.j2`
### [MODIFY] `rztemplate/rz_MERGED_NOHOYO.j2`
### [MODIFY] `rztemplate/rz_efm.j2`
Добавить теги `[RZM-MENU] [START/END]` и `[RZM-MOD] [START/END]` в генерируемые секции.

---

### [MODIFY] `operators/__init__.py`
Зарегистрировать новый `quick_export_ops`.

---

## План верификации

1. Полный экспорт → `.ini` содержит оба тега.
2. Quick Export → только `[RZM-MENU]` блок обновляется, `[RZM-MOD]` не тронут.
3. Quick Export на `.ini` без тегов → корректное сообщение об ошибке.
4. Перезапуск игры с обновлённым `.ini` → меню работает корректно.
