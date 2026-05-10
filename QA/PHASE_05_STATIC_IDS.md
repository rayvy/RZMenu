# Phase 0.5 (v2) — Static ImageID/TextID Buffer
## Архитектор: Antigravity | Статус: REVISED

---

## Что изменилось от v1

| v1 (неверно) | v2 (верно) |
|---|---|
| Индекс по `$di_count` | Индекс по `$id` |
| Buffer size 158*4 байт | Compact sorted array (id,imgID,txtID) |
| Ломается при visibility off | Стабильно — $id не зависит от видимости |
| Ломается от хелперов +2 | Хелперы: x111=0, буфер игнорируется |

---

## Ключевые факты о системе

- `$di_count` — счётчик слотов, сбивается при visibility/helpers/presets. **Не использовать как ключ.**
- `$id` — единственный стабильный идентификатор элемента. Для InputManager пресеты намеренно используют родительский `$id`.
- Все элементы в `rzm.elements[N]` — полноценные (включая id=836767 с image_id=10009).
- Visibility = CPU-рубильник, при off элемент не вызывает RCI2D вообще.
- Хелперы prebuild: нет imageID/textID из атласа → не нуждаются в маппинге.
- `w111` — свободен, используем для передачи `$id` в CS.

---

## Новый параметр: `$isElement`

Флаг устанавливается **только для основных элементов** (не пресетов, не хелперов).  
Технически = bit 2 в `x111` (IN_FLAGS). Также как INI-переменная для расширяемости.

```
FLAG_IS_ELEMENT      = 0x04   (bit 2)
FLAG_USE_STATIC_IMG  = 0x01   (bit 0)  — подтягивать imageID из буфера
FLAG_USE_STATIC_TEXT = 0x02   (bit 1)  — подтягивать textID из буфера
```

**Шаблон для основного элемента:**
```ini
; set by j2 template for main elements:
w111 = $id
x111 = 5   ; 0x05 = FLAG_IS_ELEMENT | FLAG_USE_STATIC_IMG
run = CustomShaderRCI2D

; Preset/helper — не получают x111 с битом IS_ELEMENT:
x111 = 0
run = CustomShaderRCI2D
```

---

## ElementStaticMap: формат буфера

**НЕ** разрежённый массив по $id (836767 → 3.3 MB, неприемлемо).  
**Compact sorted array** с линейным поиском по id.

### Формат файла `res/element_static_map.buf`

```
Buffer<float4>  (формат R32G32B32A32_FLOAT)
Каждая запись: float4{ float(id), float(imageID), float(textID), 0.0 }
Записи отсортированы по id (возрастание).
Последняя запись — sentinel: {0, 0, 0, 0}
```

Размер: (N_elements + 1) * 16 байт.  
Для 158 элементов = ~2.5 KB.

### Python генератор:

```python
# core/element_static_map.py

import struct
from pathlib import Path

def build_element_static_map(elements: list) -> bytes:
    """
    Compact sorted array of (id, imageID, textID) for all rzm.elements.
    CS does linear scan matching on id field.
    Terminated by sentinel entry (0, 0, 0, 0).
    """
    def safe_id(val):
        if val is None: return 0
        try: v = int(val); return max(0, v)
        except: return 0

    entries = []
    for elem in elements:
        eid = elem.get('id', 0)
        img = safe_id(elem.get('image_id'))
        txt = safe_id(elem.get('text_id'))
        # Only include if element has at least one mappable ID
        # (all elements included for future extensibility)
        entries.append((eid, img, txt))

    # Sort by id for potential future binary search optimization
    entries.sort(key=lambda e: e[0])

    result = bytearray()
    for eid, img, txt in entries:
        result += struct.pack('<ffff',
            float(eid),
            float(img),
            float(txt),
            0.0
        )
    # Sentinel
    result += struct.pack('<ffff', 0.0, 0.0, 0.0, 0.0)
    return bytes(result)


def build_element_flags_map(elements: list) -> dict:
    """
    Returns {elem_id: x111_flags} for use in j2 template.
    
    FLAG_IS_ELEMENT      = 0x04  -- always set for main elements
    FLAG_USE_STATIC_IMG  = 0x01  -- set if image_id is static (no conditional_images)
    FLAG_USE_STATIC_TEXT = 0x02  -- set if text_id is static (no conditional_texts)
    """
    FLAG_IS_ELEMENT      = 0x04
    FLAG_USE_STATIC_IMG  = 0x01
    FLAG_USE_STATIC_TEXT = 0x02

    def safe_id(val):
        if val is None: return -1
        try: return int(val)
        except: return -1

    flags_map = {}
    for elem in elements:
        flags = FLAG_IS_ELEMENT  # always set for rzm.elements

        img = safe_id(elem.get('image_id'))
        txt = safe_id(elem.get('text_id'))

        if img > 0 and not elem.get('conditional_images'):
            flags |= FLAG_USE_STATIC_IMG

        if txt > 0 and not elem.get('conditional_texts'):
            flags |= FLAG_USE_STATIC_TEXT

        flags_map[elem['id']] = flags
    return flags_map


def export_element_static_map(elements: list, output_path: str) -> dict:
    """Main export function. Returns flags_map for j2 template context."""
    data = build_element_static_map(elements)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    n = len(elements)
    print(f"[ElementStaticMap] {len(data)} bytes, {n} entries -> {path}")
    return build_element_flags_map(elements)
```

---

## draw_controller.hlsl — расширение (существующий код не меняется)

```hlsl
// ==================================================================
// == cs.hlsl — Extended with ElementStaticMap support
// ==================================================================
RWBuffer<float4> DataBuffer           : register(u0);
RWBuffer<uint>   IndexBuffer          : register(u1);
Buffer<float4>   ResourceStyleBuffer  : register(t105);
// NEW: Compact element static data (sorted by id, sentinel-terminated)
Buffer<float4>   ElementStaticMap     : register(t106);   // <-- НОВЫЙ

Texture1D<float4> IniParams : register(t120);
Buffer<uint>      InputTextBuffer : register(t24);

#define SCREEN_RES      IniParams[99].zw
#define IN_POS          IniParams[100].xy
#define IN_SIZE         IniParams[100].zw
#define IN_COLOR        IniParams[101]
#define IN_TILE_DATA    IniParams[102]
#define IN_FX_PARAMS    IniParams[104]
#define IN_MIRROR_MODE  IniParams[105].x
#define IN_FONT_SLOT    IniParams[105].y
#define IN_ROT          IniParams[105].w
#define IN_CLIP_RECT    IniParams[109].xyzw
#define IN_FN_TYPE      IniParams[110].x
#define IN_STYLE_ID     IniParams[110].y
#define IN_TEX_ID       IniParams[110].z
#define IN_DRAW_MODE    IniParams[110].w
#define BUFFER_INDEX    (int)IniParams[111].y
#define IN_BUFFER_OFFSET (uint)IniParams[111].z
#define IN_FLAGS        (uint)IniParams[111].x
// NEW:
#define IN_ELEMENT_ID   (uint)IniParams[111].w   // w111 = $id

#define FLAG_USE_STATIC_IMG  0x01u
#define FLAG_USE_STATIC_TEXT 0x02u
#define FLAG_IS_ELEMENT      0x04u

[numthreads(1, 1, 1)]
void main(uint3 ThreadId : SV_DispatchThreadID)
{
    uint base_idx = IN_BUFFER_OFFSET;
    uint flags    = IN_FLAGS;

    IndexBuffer[BUFFER_INDEX] = base_idx;

    // === EXISTING CODE — UNCHANGED ===
    DataBuffer[base_idx + 0] = float4(asfloat(flags), 0, 0, 0);
    DataBuffer[base_idx + 1] = float4(IN_POS, IN_SIZE);
    DataBuffer[base_idx + 2] = IN_COLOR;
    DataBuffer[base_idx + 3] = IN_TILE_DATA;
    DataBuffer[base_idx + 4] = float4(IN_MIRROR_MODE, IN_FONT_SLOT, 0, IN_ROT);

    if (any(IN_CLIP_RECT))
        DataBuffer[base_idx + 5] = IN_CLIP_RECT;
    else
        DataBuffer[base_idx + 5] = float4(0, 0, 0, 0);

    DataBuffer[base_idx + 6] = float4(IN_FN_TYPE, IN_STYLE_ID, IN_TEX_ID, IN_DRAW_MODE);
    // === END EXISTING CODE ===

    // === NEW: ElementStaticMap lookup ===
    // Only runs when $isElement flag is set (main elements only)
    [branch]
    if (flags & FLAG_IS_ELEMENT)
    {
        uint target_id    = IN_ELEMENT_ID;
        uint found_image  = 0;
        uint found_text   = 0;

        // Linear scan — N < 512, negligible cost for a CS
        [loop]
        for (int i = 0; i < 2048; i++)
        {
            float4 entry   = ElementStaticMap[i];
            uint   entry_id = (uint)entry.x;
            if (entry_id == 0u) break;          // sentinel reached
            if (entry_id == target_id) {
                found_image = (uint)entry.y;
                found_text  = (uint)entry.z;
                break;
            }
        }

        // Apply imageID if:
        // 1. Static flag set AND static map has a value
        // 2. AND INI did NOT provide an override (x102.x < 0.5 means commented out / zero)
        [branch]
        if ((flags & FLAG_USE_STATIC_IMG) && found_image > 0u)
        {
            float ini_image = IN_TILE_DATA.x;
            if (ini_image < 0.5f)   // INI did not override -> use static
                DataBuffer[base_idx + 3].x = (float)found_image;
            // else: INI provided value (conditional override) -> already written above
        }

        // Apply textID similarly (goes into tile data slot x for text draw mode)
        [branch]
        if ((flags & FLAG_USE_STATIC_TEXT) && found_text > 0u)
        {
            float ini_text = IN_TILE_DATA.x;
            if (ini_text < 0.5f)
                DataBuffer[base_idx + 3].x = (float)found_text;
        }
    }
    // === END NEW ===
}
```

---

## INI: что меняется в шаблоне

### Регистрация ресурса (core.j2)

```ini
; Добавить в [CustomShaderRCI2D], [CustomShaderRCI2D_TEXT], [CustomShaderRCI2D_SLIDER]:
cs-t106 = ResourceElementStaticMap

; Добавить после [ResourceStyleBuffer]:
[ResourceElementStaticMap]
type = Buffer
format = R32G32B32A32_FLOAT
filename = .\res\element_static_map.buf
```

### Шаблон основного элемента (j2)

```jinja2
{# x111 = flags, w111 = $id #}
{% set elem_flags = static_flags_map.get(element.id, 0x04) %}

; --- static map lookup params ---
w111 = $id
x111 = {{ elem_flags }}

{# Comment out static imageID — буфер подставит #}
{% if elem_flags & 0x01 %}
x102 = 0   {# imageID static: CS reads from ElementStaticMap #}
;$imageID = {{ element.image_id }}
{% else %}
$imageID = {{ element.image_id }}
{% endif %}

{# Conditional images stay in INI (override wins) #}
{% for cond in element.conditional_images %}
{% if loop.first %}if {{ cond.condition }}
{% else %}elif {{ cond.condition }}{% endif %}
    $imageID = {{ cond.image_id }}
{% endfor %}
{% if element.conditional_images %}endif{% endif %}

run = CustomShaderRCI2D
```

### Шаблон пресета/хелпера

```jinja2
{# Пресет: не является main element, не получает IS_ELEMENT флаг #}
{# $id не сбрасывается — InputManager логика сохраняется #}
x111 = 0    {# no flags: CS ignores ElementStaticMap entirely #}
$imageID = {{ preset.image_id }}   {# пресет всегда задаёт явно #}
run = CustomShaderRCI2D
```

---

## Как работает приоритет (INI vs Buffer)

```
Сценарий 1: статичный imageID (x111=0x05, x102=0)
  CS: found_image=47, ini_image=0.0 < 0.5 → DataBuffer.imageID = 47  ✓

Сценарий 2: conditional override (x111=0x05, $imageID=46 из if-блока)
  CS: found_image=47, ini_image=46.0 >= 0.5 → DataBuffer.imageID = 46 (INI wins) ✓

Сценарий 3: пресет (x111=0x00, $imageID=9)
  CS: FLAG_IS_ELEMENT не установлен → lookup пропускается → DataBuffer.imageID = 9 (from x102) ✓

Сценарий 4: пребилд хелпер Numbers/Popup (x111=0x00)
  CS: FLAG_IS_ELEMENT = 0 → всё работает как раньше, ничего не меняется ✓

Сценарий 5: элемент visibility=off
  INI: run не вызывается вообще → $id не передаётся → буфер не трогается ✓
  (di_count не инкрементируется — стабильность ключа не нарушается)
```

---

## QA Чеклист для агента-исполнителя

### Python (core/element_static_map.py)
- [ ] `build_element_static_map(elements)` → bytes
- [ ] Записи отсортированы по id
- [ ] Sentinel {0,0,0,0} в конце
- [ ] `build_element_flags_map(elements)` → {id: flags}
- [ ] FLAG_IS_ELEMENT (0x04) у всех rzm.elements
- [ ] FLAG_USE_STATIC_IMG (0x01) только если нет conditional_images
- [ ] `export_element_static_map()` — вызвать при экспорте, вернуть flags_map в j2 context

### draw_controller.hlsl
- [ ] Добавить `Buffer<float4> ElementStaticMap : register(t106)`
- [ ] Добавить defines: `IN_ELEMENT_ID`, все FLAG_*
- [ ] Блок lookup расположен ПОСЛЕ существующих строк 37-55
- [ ] Строки 37-55 оригинала — **не тронуты**
- [ ] Loop bounded: `for (int i = 0; i < 2048; i++)`

### core.j2
- [ ] `cs-t106 = ResourceElementStaticMap` в каждом CustomShaderRCI2D*
- [ ] `[ResourceElementStaticMap]` объявление

### j2 элементный шаблон
- [ ] `w111 = $id` перед dispatch для main elements
- [ ] `x111 = {{ elem_flags }}` из flags_map
- [ ] Статичный `$imageID` закомментирован / заменён на `x102 = 0`
- [ ] Conditional images — остаются в INI
- [ ] Пресеты/хелперы: `x111 = 0`, без w111 в элементном шаблоне

### QA тесты
- [ ] Запустить `QA/test_phase05_static_ids_v2.py` (обновить тесты)
- [ ] `test_compact_sorted_array` — sentinel на конце, порядок id
- [ ] `test_id_lookup_simulation` — linear scan находит нужный элемент
- [ ] `test_836767_included` — системный элемент в маппинге
- [ ] `test_flag_is_element_always_set` — все rzm.elements имеют 0x04
- [ ] `test_conditional_override_wins` — при x102>0 буфер не используется
