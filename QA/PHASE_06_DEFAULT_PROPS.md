# Phase 0.6 — Default Props: запечка неизменяемых параметров в static буфер
## Архитектор: Antigravity | Статус: DRAFT
## Контекст: продолжение PHASE_05 (image_id/text_id) и MIGRATION_PLAN

---

## Достигнутый прогресс (Phase 0.5)

Phase 0.5 доказала концепцию: `$image_id` и `$text_id` успешно перенесены в
`ElementStaticMap` (t106) — это полноценный бинарный `.buf` с линейным
поиском по `$id`. INI-шаблон больше не обязан явно писать эти значения,
если они статичны. Гибкость сохранена: conditional override в INI всегда
побеждает (приоритет INI > буфер).

---

## 1. Анализ параметров draw_controller.hlsl

### 1.1 Все входные каналы (IniParams)

| Define               | Регистр           | Слот DataBuffer | Описание                         |
|----------------------|-------------------|-----------------|----------------------------------|
| `IN_POS`             | IniParams[100].xy | Slot 1 .xy      | Позиция элемента (px)            |
| `IN_SIZE`            | IniParams[100].zw | Slot 1 .zw      | Размер элемента (px)             |
| `IN_COLOR`           | IniParams[101]    | Slot 2          | RGBA цвет                        |
| `IN_TILE_DATA`       | IniParams[102]    | Slot 3          | imageID / textID / tile params   |
| `IN_FX_PARAMS`       | IniParams[104]    | (не пишется)    | Параметры эффектов — читается instancer |
| `IN_MIRROR_MODE`     | IniParams[105].x  | Slot 4 .x       | Режим зеркала                    |
| `IN_FONT_SLOT`       | IniParams[105].y  | Slot 4 .y       | Индекс шрифта                    |
| `IN_ROT`             | IniParams[105].w  | Slot 4 .w       | Угол поворота                    |
| `IN_CLIP_RECT`       | IniParams[109]    | Slot 5          | Прямоугольник клиппинга          |
| `IN_FN_TYPE`         | IniParams[110].x  | Slot 6 .x       | Тип функции (draw mode variant)  |
| `IN_STYLE_ID`        | IniParams[110].y  | Slot 6 .y       | ID стиля из ResourceStyleBuffer  |
| `IN_TEX_ID`          | IniParams[110].z  | Slot 6 .z       | ID текстуры                      |
| `IN_DRAW_MODE`       | IniParams[110].w  | Slot 6 .w       | Режим отрисовки                  |
| `BUFFER_INDEX`       | IniParams[111].y  | —               | Индекс в IndexBuffer             |
| `IN_BUFFER_OFFSET`   | IniParams[111].z  | —               | Смещение в DataBuffer            |
| `IN_FLAGS`           | IniParams[111].x  | Slot 0          | Битовые флаги (Phase 0.5)        |
| `IN_ELEMENT_ID`      | IniParams[111].w  | —               | $id элемента (Phase 0.5)         |
| `SCREEN_RES`         | IniParams[99].zw  | —               | Разрешение экрана                |

> `IniParams[103]` и `IniParams[106-108]` — **не используются** в текущем шейдере. Свободны.

### 1.2 Категории параметров по изменяемости

#### 🔴 НЕ запекаем (динамические — меняются в runtime)
| Параметр         | Причина                                                       |
|------------------|---------------------------------------------------------------|
| `IN_POS`         | Динамический порядок буферов, формулы, parent propagation    |
| `IN_SIZE`        | Может зависеть от формул ($width/$height)                     |
| `IN_COLOR`       | Hover/active/focus состояния, conditional color              |
| `IN_CLIP_RECT`   | Зависит от контейнера, позиции родителя                       |
| `IN_FLAGS`       | slot_mask / IS_ELEMENT — управляющий регистр CS               |
| `BUFFER_INDEX`   | Динамический порядок отрисовки                                |
| `IN_BUFFER_OFFSET` | Зависит от di_count / порядка                               |

#### 🟡 УСЛОВНО запекаем (статичны если нет формул/условий)
| Параметр         | Условие запечки                                               |
|------------------|---------------------------------------------------------------|
| `IN_TILE_DATA`   | ✅ ВЫПОЛНЕНО в Phase 0.5 (imageID / textID)                   |
| `IN_COLOR`       | Только базовый цвет; если нет conditional color               |
| `IN_FX_PARAMS`   | Если эффект статичен (нет формулы анимации)                   |
| `IN_ROT`         | Если нет формулы вращения                                     |

#### 🟢 ЗАПЕКАЕМ (всегда статичны для данного элемента)
| Параметр       | Обоснование                                                       |
|----------------|-------------------------------------------------------------------|
| `IN_MIRROR_MODE` | Устанавливается дизайнером, никогда не меняется в runtime       |
| `IN_FONT_SLOT`   | Тип шрифта для текстового элемента — статичен                   |
| `IN_FN_TYPE`     | Тип функции (button, slider, label) — не меняется               |
| `IN_STYLE_ID`    | ID стиля — статичен на весь lifetime элемента                   |
| `IN_TEX_ID`      | ID текстуры (если нет conditional) — аналогично imageID         |
| `IN_DRAW_MODE`   | Режим рисования (image / text / solid) — задаётся на экспорте   |

---

## 2. Концепция Default Props

### Принцип

> Если параметр **не объявлен в INI CommandList**, шейдер берёт его из
> статического буфера (`ElementStaticMap` или расширенного `ElementDefaultProps`).
> INI не обязан писать то, что не меняется. Это устраняет тысячи строк
> boilerplate без изменения логики.

### Отличие от Phase 0.5

Phase 0.5 работает только с `imageID`/`textID`. Phase 0.6 расширяет концепцию
на **весь Slot 6** и часть **Slot 4**, создавая полноценные дефолты для
`fn_type`, `style_id`, `tex_id`, `draw_mode`, `mirror_mode`, `font_slot`.

---

## 3. Структура нового буфера: ElementDefaultProps

### Формат файла `res/element_default_props.buf`

```
Buffer<float4>  (формат R32G32B32A32_FLOAT)
Записи отсортированы по id (возрастание).
Sentinel: {0, 0, 0, 0, 0, 0, 0, 0} — два float4 с нулевым id.
```

**Каждая запись: 2x float4 (32 байта на элемент)**

```
float4 A: { float(id),   float(fn_type),  float(style_id), float(tex_id)   }
float4 B: { float(draw_mode), float(mirror_mode), float(font_slot), float(rot_default) }
```

Размер для 158 элементов: 158 × 32 + 8 = ~5 KB.

> **Почему отдельный буфер, а не расширение ElementStaticMap?**
> ElementStaticMap (t106) зафиксирован в Phase 0.5 и имеет структуру
> `{id, imageID, textID, 0}`. Изменять его формат — это breaking change.
> Новый `ElementDefaultProps` (t107) — отдельный ресурс, регистрируется
> независимо. Оба буфера читаются в одном CS диспатче.

### Python генератор

```python
# core/element_default_props.py
import struct
from pathlib import Path

# Флаги наличия дефолта (для j2 whitelist)
FLAG_HAS_FN_TYPE    = 0x01
FLAG_HAS_STYLE_ID   = 0x02
FLAG_HAS_TEX_ID     = 0x04
FLAG_HAS_DRAW_MODE  = 0x08
FLAG_HAS_MIRROR     = 0x10
FLAG_HAS_FONT_SLOT  = 0x20
FLAG_HAS_ROT        = 0x40

def build_element_default_props(elements: list) -> bytes:
    """
    Compact sorted array of default (static) visual parameters.
    CS uses linear scan on id, same pattern as ElementStaticMap.
    """
    entries = []
    for elem in elements:
        eid = int(elem.get('id', 0))
        entries.append((
            eid,
            float(elem.get('fn_type',    0)),
            float(elem.get('style_id',   0)),
            float(elem.get('tex_id',     0)),
            float(elem.get('draw_mode',  0)),
            float(elem.get('mirror_mode',0)),
            float(elem.get('font_slot',  0)),
            float(elem.get('rotation',   0)),
        ))

    entries.sort(key=lambda e: e[0])

    result = bytearray()
    for e in entries:
        eid, fn, sty, tex, dm, mir, fnt, rot = e
        result += struct.pack('<ffff', float(eid), fn, sty, tex)
        result += struct.pack('<ffff', dm, mir, fnt, rot)

    # Sentinel (2x float4)
    result += struct.pack('<ffff', 0.0, 0.0, 0.0, 0.0)
    result += struct.pack('<ffff', 0.0, 0.0, 0.0, 0.0)
    return bytes(result)


def build_default_props_flags(elements: list) -> dict:
    """
    Returns {elem_id: omit_set} — набор параметров которые можно
    исключить из INI CommandList (j2 whitelist фильтр).
    """
    omit_map = {}
    for elem in elements:
        eid = int(elem.get('id', 0))
        omit = set()
        # Параметр можно опустить если: нет формулы И нет условного override
        if not elem.get('formula_fn_type')    and not elem.get('conditional_fn_type'):    omit.add('fn_type')
        if not elem.get('formula_style_id')   and not elem.get('conditional_style'):      omit.add('style_id')
        if not elem.get('formula_tex_id')     and not elem.get('conditional_tex'):        omit.add('tex_id')
        if not elem.get('formula_draw_mode')  and not elem.get('conditional_draw_mode'): omit.add('draw_mode')
        if not elem.get('formula_mirror'):                                                 omit.add('mirror_mode')
        if not elem.get('formula_font_slot'):                                              omit.add('font_slot')
        if not elem.get('formula_rotation')   and not elem.get('conditional_rotation'):   omit.add('rotation')
        omit_map[eid] = omit
    return omit_map
```

---

## 4. Расширение draw_controller.hlsl

> **Принцип невмешательства**: существующие 130 строк шейдера — не тронуты.
> Блок Default Props добавляется ПОСЛЕ Phase 0.5 блока.

```hlsl
// Phase 0.6: Default visual props (fn_type, style_id, tex_id, draw_mode, mirror, font, rot)
// Format: 2x float4 per entry: {id, fn, sty, tex}, {dm, mir, fnt, rot}
// Indexed by linear scan on IN_ELEMENT_ID. Sentinel id==0 stops scan.
Buffer<float4> ElementDefaultProps : register(t107);   // <-- НОВЫЙ

// Phase 0.6: flag bits для DEFAULT PROPS (в IN_FLAGS, старшие биты)
#define FLAG_USE_DEFAULT_SLOT6  0x08u  // fn_type/style_id/tex_id/draw_mode из буфера
#define FLAG_USE_DEFAULT_SLOT4X 0x10u  // mirror_mode/font_slot из буфера
#define FLAG_USE_DEFAULT_ROT    0x20u  // rotation из буфера

// --- В теле main(), ПОСЛЕ Phase 0.5 блока ---

    // ── Phase 0.6: ElementDefaultProps lookup ─────────────────────────────────
    // Runs only for main elements (FLAG_IS_ELEMENT). Same pattern as Phase 0.5.
    [branch]
    if ((flags & FLAG_IS_ELEMENT) && (flags & (FLAG_USE_DEFAULT_SLOT6 | FLAG_USE_DEFAULT_SLOT4X | FLAG_USE_DEFAULT_ROT)))
    {
        uint target_id = IN_ELEMENT_ID;
        float fn_def = 0, sty_def = 0, tex_def = 0, dm_def = 0;
        float mir_def = 0, fnt_def = 0, rot_def = 0;
        bool found = false;

        [loop]
        for (int j = 0; j < 2048; j += 2)  // 2 float4 per entry
        {
            float4 A = ElementDefaultProps[j];
            if ((uint)A.x == 0u) break;             // sentinel
            if ((uint)A.x == target_id)
            {
                float4 B = ElementDefaultProps[j + 1];
                fn_def  = A.y; sty_def = A.z; tex_def = A.w;
                dm_def  = B.x; mir_def = B.y; fnt_def = B.z; rot_def = B.w;
                found = true;
                break;
            }
        }

        [branch]
        if (found)
        {
            // Slot 6: fn_type / style_id / tex_id / draw_mode
            // Применяем только если INI не предоставил override (значение == 0)
            [branch]
            if (flags & FLAG_USE_DEFAULT_SLOT6)
            {
                float4 s6 = DataBuffer[base_idx + 6];
                if (s6.x < 0.5f) s6.x = fn_def;
                if (s6.y < 0.5f) s6.y = sty_def;
                if (s6.z < 0.5f) s6.z = tex_def;
                if (s6.w < 0.5f) s6.w = dm_def;
                DataBuffer[base_idx + 6] = s6;
            }

            // Slot 4: mirror_mode / font_slot / rotation
            [branch]
            if (flags & (FLAG_USE_DEFAULT_SLOT4X | FLAG_USE_DEFAULT_ROT))
            {
                float4 s4 = DataBuffer[base_idx + 4];
                if ((flags & FLAG_USE_DEFAULT_SLOT4X) && s4.x < 0.5f) s4.x = mir_def;
                if ((flags & FLAG_USE_DEFAULT_SLOT4X) && s4.y < 0.5f) s4.y = fnt_def;
                if ((flags & FLAG_USE_DEFAULT_ROT)    && s4.w < 0.5f) s4.w = rot_def;
                DataBuffer[base_idx + 4] = s4;
            }
        }
    }
    // ── END Phase 0.6 ─────────────────────────────────────────────────────────
```

---

## 5. INI шаблон: что исчезает из CommandList

### До (текущий шаблон, ~7 строк на элемент × 158 = ~1100 строк)

```ini
[CommandListElement_19]
x110 = 2      ; fn_type = BUTTON
y110 = 14     ; style_id
z110 = 0      ; tex_id
w110 = 1      ; draw_mode
x105 = 0      ; mirror_mode
y105 = 2      ; font_slot
w105 = 0.0    ; rotation
run = CustomShaderRCI2D
```

### После (если все параметры статичны)

```ini
[CommandListElement_19]
; fn_type/style_id/tex_id/draw_mode/mirror/font/rot — из ElementDefaultProps (t107)
run = CustomShaderRCI2D
```

**Slot 6 + Slot 4 частично переезжают в буфер → экономия ~7 строк × 158 элементов ≈ 1 100 строк INI (~3.3% от 33k).**

При полной реализации в связке с boilerplate reduction (MIGRATION_PLAN Фаза 3) вклад суммируется.

---

## 6. Приоритет (INI > Default Props > 0)

```
Сценарий 1: статичный style_id (флаг FLAG_USE_DEFAULT_SLOT6, y110 не задан)
  CS: s6.y == 0.0 < 0.5 → s6.y = sty_def (из буфера) ✓

Сценарий 2: conditional style (y110 = 5 задан в if-блоке)
  CS: s6.y == 5.0 >= 0.5 → буфер не перезаписывает ✓

Сценарий 3: пресет/хелпер (FLAG_IS_ELEMENT = 0)
  CS: блок Phase 0.6 полностью пропускается ✓

Сценарий 4: элемент с формулой вращения (FLAG_USE_DEFAULT_ROT не установлен)
  CS: флаг не выставлен j2 → rotation читается только из INI ✓
```

---

## 7. Модуль Formula Analyzer (оставляем на потом — Фаза 0.7)

> ⚠️ Не блокирует реализацию Phase 0.6. Реализуем позже.

**Задача:** перед запечкой параметра проверить, не использует ли он
нестандартную формулу, которую нельзя запечь.

```python
# Концепция — НЕ реализовывать сейчас
class FormulaAnalyzer:
    STATIC_PATTERNS = [r'^\d+(\.\d+)?$', r'^\$\w+$']  # литерал или одна переменная
    DYNAMIC_PATTERNS = [r'\$Position', r'\$hover', r'\$click', r'\$value']

    def is_bakeable(self, formula: str) -> bool:
        """True если формула безопасна для запечки."""
        for pat in self.DYNAMIC_PATTERNS:
            if re.search(pat, formula, re.IGNORECASE):
                return False
        return True

    def classify(self, formula: str) -> str:
        """'static' | 'relative' | 'absolute' | 'dynamic'"""
        ...
```

**Почему откладываем:** большинство запекаемых параметров (fn_type, style_id,
draw_mode) на практике уже являются литералами. Analyzer нужен только для
edge cases. Добавим в Phase 0.7 перед Фазой 3 MIGRATION_PLAN.

---

## 8. Место в общем плане миграции

```
MIGRATION_PLAN.md                    PHASE_05 / PHASE_06
─────────────────────────────────── ─────────────────────────────────────
Фаза 0 — Анализ (ВЫПОЛНЕНО)         Phase 0.5 ✅ image_id + text_id в buf
Фаза 1 — Расширение шейдеров        Phase 0.6 ← МЫ ЗДЕСЬ (Slot 6, Slot 4x)
Фаза 1 — Расширение шейдеров        Phase 0.7 (Formula Analyzer, оставляем)
Фаза 1 — Расширение шейдеров        Slot 7 / PropagatePositions (MIGRATION_PLAN)
Фаза 2 — static_data.buf            полный static_data.buf для всех слотов
Фаза 3 — Гибридный j2               j2 whitelist фильтр (omit_map)
Фаза 4 — Валидация                  < 30% строк, < 0.4s парсинг
```

> **Позиция Phase 1 выбрана намеренно.** Slot 7 / PropagatePositions из
> MIGRATION_PLAN требует нового CS шейдера (`CustomShaderPropagatePositions`).
> Phase 0.6 работает внутри существующего `draw_controller.hlsl` — нет новых
> шейдеров, нет новых регистров dispatch, минимальный риск.

---

## 9. Связь с parent_id (нужна ли интеграция?)

**Вывод: для Phase 0.6 parent_id НЕ нужен.**

`parent_id` и PropagatePositions из MIGRATION_PLAN нужны только когда
мы запекаем позиции (Slot 1). Phase 0.6 запекает **визуальные свойства**
(Slot 4/6) — они не зависят от иерархии и порядка буферов.

Единственное пересечение: `font_slot` теоретически мог бы наследоваться
от родительского контейнера (тема/стиль). Это — фича Phase 2+, не Phase 0.6.

---

## 10. QA Чеклист

### Python (core/element_default_props.py)
- [ ] `build_element_default_props(elements)` → bytes (2x float4 per elem)
- [ ] Записи отсортированы по id
- [ ] Sentinel 2×{0,0,0,0} в конце
- [ ] `build_default_props_flags(elements)` → {id: omit_set}
- [ ] Тест: элемент с conditional_style → style_id НЕ в omit_set

### draw_controller.hlsl
- [ ] `Buffer<float4> ElementDefaultProps : register(t107)` добавлен
- [ ] `FLAG_USE_DEFAULT_SLOT6 / SLOT4X / ROT` определены (биты 0x08, 0x10, 0x20)
- [ ] Блок Phase 0.6 расположен ПОСЛЕ блока Phase 0.5 (строки 70-129)
- [ ] Строки 1-129 оригинала — **не тронуты**
- [ ] Loop: `for (j = 0; j < 2048; j += 2)` — шаг 2 (2 float4 на запись)
- [ ] INI-override check: `value < 0.5f` → применяем дефолт

### INI / j2 шаблон
- [ ] `cs-t107 = ResourceElementDefaultProps` в каждом CustomShaderRCI2D*
- [ ] `[ResourceElementDefaultProps]` объявление (Buffer, R32G32B32A32_FLOAT)
- [ ] j2 whitelist: строки из omit_set не генерируются в CommandList
- [ ] x111 флаги (биты 0x08/0x10/0x20) устанавливаются по omit_set

### QA тесты
- [ ] `test_default_slot6_applied` — fn_type/style_id/tex_id из буфера
- [ ] `test_ini_override_wins` — если INI задал style_id → буфер не перезаписывает
- [ ] `test_preset_skip` — пресет (FLAG_IS_ELEMENT=0) → блок 0.6 не запускается
- [ ] `test_formula_element_skip` — элемент с formula_rotation → флаг не ставится

---

## 11. Ожидаемый результат

| Метрика                          | До Phase 0.6 | После Phase 0.6 |
|----------------------------------|:------------:|:---------------:|
| Строк INI на статичный элемент   | ~63          | ~55 (-8)        |
| % от общего INI (Slot 6 + 4x)   | 100%         | ~97%            |
| Новых CS диспатчей               | —            | 0               |
| Новых шейдерных файлов           | —            | 0               |
| Новых Python модулей             | —            | 1               |
| Новых буферов (`.buf`)           | —            | 1 (~5 KB)       |
| Риск поломки логики              | —            | Минимальный     |

Экономия ~8 строк на элемент × 158 = **~1 264 строки** из 33k (~3.8%).
В сочетании с Phase 0.5 и последующей Фазой 3 (boilerplate) суммарная
цель < 30% строк достижима.
