# Phase 0.5.5 (v2) — Groundwork: ID Clarity, Color Bake, BlackList Buffer
## Статус: REVISED | Предшествует: Phase 0.6 (Default Props)

---

## Ответ на вопрос 4.3 — Существующий зачаток механизма

**Да, зачаток существует — это `$rayvich_back_values_*` в `data.j2`.**

В `[Constants]` (data.j2, строки 253-352) объявлены десятки глобальных
переменных вида:
```ini
global $rayvich_back_values_x23
global $rayvich_back_values_y101
global $rayvich_back_values_x102
...
```

А в `functions.j2` строки 412-454 (`CommandListCoreFXRenderSliderText`)
виден паттерн использования:
```ini
local $BackColorR
local $BackColorG
...
$BackColorR = $colorR   ← сохраняем
; ... делаем что-то с цветом ...
$colorR = $BackColorR   ← восстанавливаем
```

**Вывод:** `$rayvich_back_values_*` — это твой первый подход к системе
сохранения/восстановления состояния IniParams регистров между вызовами.
Он же применялся в `CommandListCoreFXRenderSliderNumbers` / `ButtonNumbers`
чтобы не испортить `$colorR/G/B/A` хоста после рендера вспомогательных
примитивов. Сейчас реализован через local-переменные внутри конкретных
блоков, а `$rayvich_back_values_*` объявлены глобально но фактически
не используются в шейдерах (остаток от более ранней концепции).

**BlackList Buffer — это эволюция этой же идеи, только реализованная на
стороне GPU через CS вместо INI-переменных.**

---

## 1. ID-система: исправленная концепция

### 1.1 Пресеты — $preset_id вместо $preset_parent_id

**Решение (принято):** Пресет получает **свой истинный Blender-side ID**:

```jinja2
{# container.j2 — base macro, ветка is_preset #}
{% else %}
$preset_id = {{ element.id }}   ← истинный id пресета (не хоста!)
$isPreset = 1
$isElement = 0
{# $id хоста НЕ переопределяется — лежит в глобале для InputManager #}
{% endif %}
```

**Как это работает с RCI2D:**

В момент dispatch `CustomShaderRCI2D` шейдер видит `$isPreset` и выбирает
какой id использовать для маппинга в буфере:

```ini
; INI-side переключатель перед run = CustomShaderRCI2D:
if $isPreset == 1
    w111 = $preset_id       ← берём истинный id пресета для buf lookup
    x111 = {{ preset_flags }}
else
    w111 = $id              ← обычный элемент
    x111 = {{ elem_flags }}
endif
run = CustomShaderRCI2D
```

Преимущества:
- `$id` хоста сохранён → InputManager логика (`$hoveredID == $id`) не ломается
- Пресет имеет стабильный ключ для ElementStaticMap → буфер подставляет
  правильный стиль/цвет/imageID именно от **дизайна пресета**, а не хоста
- Один пресет → одна запись в буфере → нет дублей

### 1.2 Хелперы — $helper_id рядом с синтетическим $id

Хелпер получает оба:

```jinja2
{# generate_helper_definition #}
{%- set h_id = helper_item.id + host_item.id * 2 + 6969 -%}

[CommandListElement{{h_name}}]
$id = {{h_id}}                           ← per-host синтетический (для hover/click)
$helper_id = {{ helper_item.id }}        ← NEW: истинный Blender id хелпера
$helper_host_id = {{ host_item.id }}     ← NEW: id хоста
```

**Как это работает с буфером:**
- Для hover/click логики → используем синтетический `$id` (per-host, уникален)
- Для buf lookup визуального стиля → `w111 = $helper_id` (истинный id)

```ini
; перед dispatch:
if $isHelper == 1
    w111 = $helper_id
    x111 = {{ helper_flags }}
else ...
endif
run = CustomShaderRCI2D
```

Это даёт: один `_helper_arrow` хелпер → одна запись в буфере.
Все хосты использующие этот хелпер берут один и тот же визуальный дефолт.

### 1.3 Новые глобальные переменные для [Constants]

```ini
global $preset_id = -1
global $helper_id = -1
global $helper_host_id = -1
global $isHelper = 0          ; аналог $isPreset для хелперов
```

---

## 2. CommandListRestoreElement — обновлённая логика

### Текущая реализация (functions.j2 строки 2-16)

```ini
[CommandListRestoreElement]
$imageID = 0
$rotation = 0.0
if $isPreset != 1
    $scissorX = 0
    $scissorY = 0
    $scissorZ = 0
    $scissorW = 0
    $fontSlot = 0
    w33 = 0
    x110 = 0
    y110 = 0
endif
```

### Проблема с Color Bake

Сейчас `CommandListRestoreElement` **не сбрасывает `$colorR/G/B/A`**.
После того как мы перестанем писать цвет в INI для статичных элементов,
глобальные `$colorR/G/B/A` останутся с прошлого элемента и **перетекут**
в следующий вызов если тот тоже не пишет цвет.

Это и есть хаотичная передача данных между элементами которую нужно исправить.

### Исправление RestoreElement

```ini
[CommandListRestoreElement]
$imageID = 0
$rotation = 0.0
; Phase 0.5.5: сброс цвета — предотвращает перетекание между элементами
$colorR = 0.0
$colorG = 0.0
$colorB = 0.0
$colorA = 0.0
; Phase 0.5.5: сброс ID маркеров
$preset_id = -1
$helper_id = -1
$isHelper = 0
if $isPreset != 1
    $scissorX = 0
    $scissorY = 0
    $scissorZ = 0
    $scissorW = 0
    $fontSlot = 0
    w33 = 0
    x110 = 0
    y110 = 0
    $isPreset = 0
endif
```

> Сброс `$colorR/G/B/A` в ноль — это безопасно, потому что:
> - Статичные элементы: CS сразу перепишет из буфера (BlackList = 1)
> - Динамические элементы (formula): INI сам пишет цвет после RestoreElement
> - Пресеты: пишут цвет явно (не используют color bake)

---

## 3. BlackList Buffer (новый механизм)

### 3.1 Концепция

BlackList Buffer — per-element битовая маска параметров, которые CS должен
**принудительно взять из статического буфера**, игнорируя любые значения
пришедшие из IniParams.

```
Если BlackList[elem_buf_idx].bit_N == 0 → параметр разрешён к перезаписи из INI
Если BlackList[elem_buf_idx].bit_N == 1 → ВСЕГДА берём из статического буфера
```

Это отличается от текущего Phase 0.5 подхода (INI-override wins):
- Phase 0.5: CS применяет буфер ТОЛЬКО если INI не написал значение (0 → use buf)
- BlackList: CS применяет буфер ВСЕГДА, даже если INI что-то написал

**Когда нужен BlackList = 1:**
- Статичный цвет и вышестоящий элемент в цепочке не сбросил $colorR → нужно защититься
- Статичный style_id когда CommandListButton перезаписывает y110 → нужно восстановить
- Любой параметр где гарантированно нет нужды в INI-override

### 3.2 Формат буфера `res/element_blacklist.buf`

```
Buffer<uint>  (формат R32_UINT)
Один uint на элемент, compact sorted array по id.

Структура: 2x uint32 на запись = float4 (через reinterpret)
Entry: { uint(id), uint(blacklist_mask), uint(reserved), uint(reserved) }
```

**Биты blacklist_mask:**
```
bit 0  = 0x01  → COLOR (Slot 2: RGBA)
bit 1  = 0x02  → STYLE_ID (Slot 6.y: y110)
bit 2  = 0x04  → FN_TYPE (Slot 6.x: x110)
bit 3  = 0x08  → TEX_ID (Slot 6.z)
bit 4  = 0x10  → DRAW_MODE (Slot 6.w)
bit 5  = 0x20  → MIRROR+FONT (Slot 4.xy)
bit 6  = 0x40  → ROT (Slot 4.w)
bit 7  = 0x80  → IMAGE_ID (Slot 3.x) — если нет conditional
bit 8  = 0x100 → TEXT_ID (Slot 3.x для text mode)
```

### 3.3 Как BlackList интегрируется в draw_controller.hlsl

```hlsl
// Phase 0.5.5: BlackList — compact sorted array {uint(id), uint(mask), 0, 0}
Buffer<uint4> ElementBlackList : register(t108);  // <-- НОВЫЙ

// В теле main(), после всех write:

    [branch]
    if (flags & FLAG_IS_ELEMENT)
    {
        // ... (существующий Phase 0.5 lookup) ...

        // BlackList lookup — ищем по target_id
        uint bl_mask = 0u;
        [loop]
        for (int k = 0; k < 2048; k++)
        {
            uint4 bl_entry = ElementBlackList[k];
            if (bl_entry.x == 0u) break;
            if (bl_entry.x == target_id) { bl_mask = bl_entry.y; break; }
        }

        // Apply BlackList overrides — железобетонно берём из статического буфера
        [branch]
        if (bl_mask & 0x01u)  // COLOR blacklisted
        {
            // found_color уже получен из ElementStaticMap lookup выше
            DataBuffer[base_idx + 2] = float4(found_r, found_g, found_b, found_a);
        }
        [branch]
        if (bl_mask & 0x02u)  // STYLE_ID blacklisted
        {
            float4 s6 = DataBuffer[base_idx + 6];
            s6.y = static_style_id;   // из ElementDefaultProps (Phase 0.6)
            DataBuffer[base_idx + 6] = s6;
        }
        // ... etc для остальных битов
    }
```

### 3.4 Python генератор

```python
# core/element_blacklist.py

BL_COLOR     = 0x01
BL_STYLE_ID  = 0x02
BL_FN_TYPE   = 0x04
BL_TEX_ID    = 0x08
BL_DRAW_MODE = 0x10
BL_MIRROR    = 0x20
BL_ROT       = 0x40
BL_IMAGE_ID  = 0x80
BL_TEXT_ID   = 0x100

def build_element_blacklist(elements: list) -> bytes:
    entries = []
    for elem in elements:
        eid  = int(elem.get('id', 0))
        mask = 0

        # COLOR: всегда в blacklist если не formula
        if not elem.get('color_is_formula'):
            mask |= BL_COLOR

        # IMAGE_ID: если нет conditional_images
        if elem.get('image_id', -1) > 0 and not elem.get('conditional_images'):
            mask |= BL_IMAGE_ID

        # TEXT_ID: если нет conditional_texts
        if elem.get('text_id', -1) > 0 and not elem.get('conditional_texts'):
            mask |= BL_TEXT_ID

        # STYLE_ID: всегда статичен (Phase 0.6)
        # mask |= BL_STYLE_ID   ← раскомментировать когда Phase 0.6 готова

        entries.append((eid, mask))

    entries.sort(key=lambda e: e[0])

    result = bytearray()
    for eid, mask in entries:
        result += struct.pack('<IIII', eid, mask, 0, 0)  # uint4

    # Sentinel
    result += struct.pack('<IIII', 0, 0, 0, 0)
    return bytes(result)
```

### 3.5 Связь с существующим $rayvich_back_values_*

`$rayvich_back_values_*` — INI-side подход к той же проблеме:
сохранить значение до рискованной операции, восстановить после.

BlackList Buffer — GPU-side подход: вместо восстановления через INI,
CS берёт правильное значение принудительно из статического буфера.

**Оба механизма могут сосуществовать.** `$rayvich_back_values_*` полезен
для локальных операций внутри одного CommandList (как в ButtonNumbers).
BlackList полезен для защиты между вызовами разных CommandList-ов.

---

## 4. Color Bake — обновлённый дизайн

С учётом BlackList Buffer концепция упрощается:

### Приоритет обработки цвета в CS (Phase 0.5.5)

```
1. CS пишет Slot 2 из IniParams (colorR/G/B/A) — обычный write
2. Phase 0.5 lookup: если FLAG_USE_STATIC_COLOR → Slot 2 = StaticMap.color
   НО только если INI написал 0 (старая логика)
3. BlackList: если BL_COLOR → Slot 2 = StaticMap.color ПРИНУДИТЕЛЬНО
   (независимо от того что написал INI)
```

Для элементов с `color_is_formula=False`:
- INI не пишет `$colorR/G/B/A` → они равны 0 после RestoreElement
- `FLAG_USE_STATIC_COLOR` выставлен → CS пишет из буфера (шаг 2)
- `BL_COLOR` выставлен → даже если что-то случайно попало → перезапишем (шаг 3)

**Двойная защита: FlAG + BlackList.**

### ElementStaticMap расширение: 2x float4

```
float4 A: { float(id), float(imageID), float(textID), float(has_color) }
float4 B: { float(R),  float(G),       float(B),      float(A)         }
```

Loop step: `i += 2` (как в предыдущей версии плана).

---

## 5. Итоговые изменения Phase 0.5.5

### Новые файлы

| Файл | Описание |
|------|----------|
| `core/element_blacklist.py` | Генератор BlackList буфера |
| `res/element_blacklist.buf` | Бинарный buфер (uint4 per entry) |

### Изменённые файлы

| Файл | Что меняется | Риск |
|------|-------------|:----:|
| `core/element_static_map.py` | 2x float4, добавить RGBA | 🟡 |
| `draw_controller.hlsl` | loop `i += 2`, FLAG_COLOR, BL lookup, t108 | 🟡 |
| `functions.j2` → RestoreElement | сброс color, preset_id, helper_id, isHelper | 🟡 |
| `container.j2` → base macro | `$preset_id`, `$isHelper`, if/else w111 | 🟢 |
| `container.j2` → helper_definition | `$helper_id`, `$helper_host_id` | 🟢 |
| `data.j2` [Constants] | `$preset_id`, `$helper_id`, `$helper_host_id`, `$isHelper` | 🟢 |
| `core/export_ops.py` | передать blacklist_map в j2 context | 🟢 |

---

## 6. QA Чеклист

### BlackList Buffer
- [ ] `build_element_blacklist(elements)` → bytes (uint4 per entry)
- [ ] BL_COLOR выставлен для всех элементов без `color_is_formula`
- [ ] BL_IMAGE_ID / BL_TEXT_ID выставлены если нет conditional
- [ ] Sentinel {0,0,0,0} в конце
- [ ] t108 зарегистрирован в всех CustomShaderRCI2D*

### draw_controller.hlsl
- [ ] `Buffer<uint4> ElementBlackList : register(t108)` добавлен
- [ ] BL lookup цикл расположен ПОСЛЕ Phase 0.5 lookup
- [ ] BL_COLOR перезаписывает Slot 2 принудительно
- [ ] Loop i += 2 для ElementStaticMap (2x float4)
- [ ] Строки 1-68 (existing writes) не тронуты

### ID система (j2)
- [ ] `$preset_id = {{ element.id }}` в base macro (ветка is_preset)
- [ ] `$isHelper = 1` в generate_helper_definition
- [ ] `$helper_id = {{ helper_item.id }}` в generate_helper_definition
- [ ] Переключатель w111: if isPreset → preset_id, elif isHelper → helper_id, else → id
- [ ] [Constants] объявляет все 4 новые переменные

### RestoreElement
- [ ] Сброс `$colorR/G/B/A = 0.0`
- [ ] Сброс `$preset_id = -1`, `$helper_id = -1`, `$isHelper = 0`
- [ ] Тест: после RestoreElement colorR не перетекает в следующий элемент

---

## 7. Место в плане

```
Phase 0.5   ✅ image_id + text_id → ElementStaticMap (t106)
Phase 0.5.5 ← МЫ ЗДЕСЬ
  ├─ $preset_id / $helper_id / $isHelper — истинные ID для buf lookup
  ├─ ElementStaticMap: 2x float4 (+RGBA), loop i+=2
  ├─ FLAG_USE_STATIC_COLOR 0x08
  ├─ BlackList Buffer (t108) — железобетонная защита статики
  ├─ RestoreElement: сброс colorR/G/B/A + новых переменных
  └─ dynamic_param_count (Python only)
Phase 0.6   Slot 6 + Slot 4x → ElementDefaultProps (t107)
            BL_STYLE_ID / BL_FN_TYPE включаются
Phase 0.7   Formula Analyzer
Phase 1     Slot 7, PropagatePositions
```
