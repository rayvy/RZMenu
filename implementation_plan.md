# Menu-Only Export System (RZMenu Quick Export)

## Обзор

Цель — реализовать **быстрый экспорт только меню**: перегенерировать «графическую оболочку» (логику RZMenu) без повторного экспорта геометрии# Simplify Text System Architecture (Revised)

This plan simplifies the text system while maintaining backward compatibility and avoiding radical deletions.

## User Review Required

> [!IMPORTANT]
> This revision avoids Python changes and uses comments (`;`) instead of deletions in templates.

> [!IMPORTANT]
> The `run = CommandListGetTextElement...` calls are being replaced by inline variable assignments within the element's existing command list.
 
> Это гарантирует, что структура .ini останется актуальной для RZMenu, но тяжелые данные мешей не потеряются.

> [!WARNING]
> **Теги-маркеры**: Система опирается на наличие тегов `;[META-INFO] [START] [MOD-BLOCK]` и `;[META-INFO] [END] [MOD-BLOCK]`. Если их нет (старый мод), Quick Export предложит сделать полный экспорт один раз.

---

## Предложенные изменения

### [Component] Template Logic

#### [MODIFY] [elements_helpers.j2](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/rztemplate/modules/elements_helpers.j2)
- Comment out `[CommandList...]` headers in `generate_text_resource_block` and `generate_hover_text_resource_block`.
- In those macros, set `$TextID = {{ text_id }}` (from `text_info[0]`).
- Ensure `$TextIsData` logic sets `$TextID`.

#### [MODIFY] [core.j2](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/rztemplate/modules/core.j2)
- **Comment out** (do not delete) all `[CustomShaderRCI2D_TEXT_...]` blocks.
- Update `[CustomShaderRCI2D_TEXT]` to use `x102 = $TextID`.
- Update `[CustomShaderRCI2D_HOVERTEXT]` to use `x102 = $TextID`.

#### [MODIFY] [container.j2](file:///c:/Users/Rayvy/AppData/Roaming/Blender%20Foundation/Blender/5.0/scripts/addons/RZMenu/rztemplate/modules/container.j2)
- Update `generate_text`:
    - Replace `run = CommandListGetTextElement...` with a direct call to `generate_text_resource_block`.
    - Change any alignment-specific `CustomShader` runs to `run = CustomShaderRCI2D_TEXT`.
- Update `generate_hovertext`:
    - Replace `run = CommandListGetTextHoverElement...` with a direct call to `generate_hover_text_resource_block`.
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
