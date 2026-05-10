# RZMenu — Static Buffer Migration Plan
## Цель: сократить INI-файл без изменения поведения системы

---

## 1. Что показал реальный анализ test_mod.ini

### Факты из 33 059 строк (222 CommandListElement секции)

| Метрика | Значение |
|---|---|
| Средних строк на элемент | **63.3** |
| Мин / Макс | 27 / 197 |
| **Boilerplate строки** (паттерн в >50% элементов) | **81.1%** (11 398 строк) |
| **Уникальные строки** (специфичны для элемента) | **18.9%** (2 654 строки) |

### Почему тест показал 10%, а не больше?

Первый тест считал **целые элементы** как статичные.
Реальная картина другая: **ни один элемент в текущем экспортере целиком не статичен**, потому что каждый получает одинаковый шаблонный код:

```ini
run = CommandListCoreAlignment.Check      ; 68% элементов
run = CommandListCoreFNUpdateHoverState   ; 42%
run = CommandListNavProcessElement        ; 41%
run = CommandListRestoreElement           ; 68%
if ($cursorX >= $positionX && ...)        ; 68% -- hover AABB check
```

Это не уникальные данные -- это структурный шаблон, одинаковый для всех.
**Именно эти 81% и переедут в буфер + статичный инстансер.**

Уникальные 18.9% = конкретные значения позиций, формулы, условия кликов.

---

## 2. Архитектура гибридной системы

### Принцип: INI редактирует буфер, а не пишет элемент с нуля

```
ЭКСПОРТ (один раз):
  static_data.buf  <-- все статичные данные всех элементов (112 байт x N)

КАДР (каждый кадр):
  Шаг 1: DataBuffer = copy(static_data.buf)   -- инит из статики
  Шаг 2: Для динамичных элементов -- INI патчит только изменившиеся слоты
  Шаг 3: PropagatePositions CS -- разматывает цепочки parent->child
  Шаг 4: DrawInstanced -- рендер (читает DataBuffer)
```

### Новый Slot 7 (расширение с 7 до 8 float4 на элемент)

```
Slot 0: flags
Slot 1: pos + size
Slot 2: color RGBA
Slot 3: tile_data / imageID
Slot 4: mirror / font / rotation
Slot 5: clip_rect
Slot 6: fn / style / tex / draw_mode
Slot 7: [parent_buf_index | position_flags | visibility_alpha | reserved]  <- НОВЫЙ
```

**Slot 7 поля:**
- `x = parent_buf_index` -- индекс родителя в буфере (-1 = нет родителя)
- `y = position_flags` -- битовые флаги:
  - `bit 0` = позиция RELATIVE (X/Y = смещение от родителя)
  - `bit 1` = позиция ABSOLUTE (X/Y = мировые координаты, игнорировать родителя)
  - `bit 2` = формула RELATIVE (формула использует $PositionX как смещение)
  - `bit 3` = формула ABSOLUTE (формула задаёт конечные координаты напрямую)
- `z = visibility_alpha` -- мультипликатор (0.0 = скрыт, 1.0 = виден)
- `w = reserved`

---

## 3. Разматывание цепочки позиций

### Проблема
15-элементная цепочка: root ANCHOR -> ... -> elem 15.
Элемент 15 не знает про первоначальный anchor.
Некоторые промежуточные элементы имеют формулы.

### Решение: двухпроходной линейный CS

**Pass 1 -- PropagatePositions:**

```hlsl
// Для каждого элемента i в порядке buf_index (PARENT ВСЕГДА < CHILD):
float4 s7    = DataBuffer[i*8 + 7];
int    pid   = (int)s7.x;   // parent_buf_index
uint   flags = asuint(s7.y);

float2 self_pos = DataBuffer[i*8 + 1].xy;

if (pid < 0 || (flags & BIT_ABSOLUTE)) {
    FinalPosBuffer[i] = self_pos;         // абсолютная -- берём как есть
} else {
    float2 parent_final = FinalPosBuffer[pid]; // родитель уже вычислен!
    if (flags & BIT_RELATIVE) {
        FinalPosBuffer[i] = parent_final + self_pos; // смещение
    } else {
        FinalPosBuffer[i] = parent_final + self_pos; // по умолчанию тоже relative
    }
}
// Visibility alpha cascade
float parent_alpha = (pid < 0) ? 1.0 : FinalAlphaBuffer[pid];
FinalAlphaBuffer[i] = parent_alpha * s7.z;
```

**Pass 2 -- WriteBack:**

```hlsl
// Записать FinalPosBuffer[i] -> DataBuffer[i*8 + 1].xy
// Записать FinalAlphaBuffer[i] -> DataBuffer[i*8 + 2].w  (alpha)
```

### Почему нет рекурсии

Топологическая сортировка при экспорте гарантирует: `buf_index(parent) < buf_index(child)`.
CS итерирует от 0 до N линейно. Когда доходит до элемента i, все предки уже в FinalPosBuffer.

### Relative vs Absolute формула -- как определить при экспорте

```python
def classify_formula(formula_x: str, formula_y: str) -> int:
    uses_pos_vars = '$PositionX' in formula_x or '$positionX' in formula_x
    uses_pos_vars |= '$PositionY' in formula_y or '$positionY' in formula_y
    return BIT_FORMULA_RELATIVE if uses_pos_vars else BIT_FORMULA_ABSOLUTE
```

Примеры:
```ini
; RELATIVE -- добавляет 20 к позиции родителя
$PositionX = $PositionX + 20

; ABSOLUTE -- задаёт глобальную координату напрямую
$PositionX = $ElementAnchorPositionX + 25
```

---

## 4. Partial Patch -- slot_mask

Каждый dispatch в INI передаёт:
- `z111 = buf_index` -- какой элемент патчить
- `x111 = slot_mask` -- битовая маска слотов

```
Биты slot_mask:
  0x01 = slot 0 (flags)
  0x02 = slot 1 (pos+size)
  0x04 = slot 2 (color)
  0x08 = slot 3 (tile)
  0x10 = slot 4 (mirror/font/rot)
  0x20 = slot 5 (clip)
  0x40 = slot 6 (mode/style)
  0x80 = slot 7 (parent/flags/alpha)
  0xFF = все слоты (debug full export)
```

Пример -- только rotation_is_formula:
```ini
w105 = $computed_rotation
z111 = 47        ; buf_index
x111 = 0x10     ; только slot 4
dispatch CustomShaderPatchBuffer
```

Статика в остальных слотах не трогается.

---

## 5. $id vs buf_index -- два независимых пространства

| | $id (INI) | buf_index (Buffer) |
|---|---|---|
| **Что это** | Уникальный ID из Blender | Позиция в draw order (0..N) |
| **Для чего** | $hoveredID == $id, $clickTriggerID | Адресация DataBuffer, slot 7.x |
| **Меняется?** | Никогда | При изменении порядка элементов |

В static_data.buf хранится также **ID-to-BufIndex lookup table**:
```
[id=19  -> buf_index=34]
[id=2   -> buf_index=2 ]
```

INI пишет `$id = 19` (стабильно). Шейдер ищет buf_index через таблицу.

---

## 6. Preset / Underlayer / Helper -- расширенный instancer

Расширяем до **256 вершин на инстанцию** = **42 quads**:
- Quads 0-4:  5 underlayer слотов
- Quad  5:    сам элемент (main)
- Quads 6-10: 5 preset слотов
- Quads 11-15: 5 helper слотов (только визуал)

```hlsl
uint quad_slot  = vID / 6;
uint target_buf = (quad_slot == 5)  ? self_buf_idx :
                  (quad_slot < 5)   ? underlayer_ids[quad_slot] :
                  (quad_slot < 11)  ? preset_ids[quad_slot - 6] :
                                      helper_ids[quad_slot - 11];
// Если target_buf == -1 -- quad невидим (alpha=0)
```

Preset/underlayer/helper ID-ы хранятся в отдельном **InstanceDataBuffer** (indexed by buf_index).

Логика взаимодействия preset (click, value_link) остаётся в INI.

---

## 7. Debug / Full Export режим

Флаг `RZM_EXPORT_FULL_INI = True` при экспорте:
- Каждый элемент получает секцию с `x111 = 0xFF` (все 8 слотов)
- Перезаписывает свою область в DataBuffer явно из INI
- Используется для отладки и обновлений без перекомпиляции buf

Нормальный режим (`False`):
- Только динамичные элементы получают секции
- static_data.buf загружается один раз

---

## 8. Этапы миграции

### Фаза 0 -- Анализ (ВЫПОЛНЕНО)
- [x] 81% boilerplate в реальном INI подтверждено
- [x] Топологическая сортировка по parent_id (итеративная, без рекурсии)
- [x] QA тест suite -- 9/9 тестов на test_scene.json
- [ ] Парсер формул: relative vs absolute

### Фаза 1 -- Расширение шейдеров
- [ ] Slot 7 в draw_controller.hlsl
- [ ] Slot 7 в draw_instancer.hlsl
- [ ] CustomShaderPropagatePositions.hlsl (Pass 1 + Pass 2)
- [ ] CustomShaderPatchBuffer.hlsl (slot_mask)
- [ ] QA: render output идентичен до и после

### Фаза 2 -- Генератор static_data.buf
- [ ] generate_static_buffer(elements) -> bytes в Python экспортере
- [ ] Топологическая сортировка при экспорте
- [ ] ID-to-BufIndex lookup table
- [ ] QA: serialize -> load -> verify roundtrip

### Фаза 3 -- Гибридный .j2 шаблон
- [ ] rz_uni_hybrid.j2 -- минимальный INI
- [ ] classify_formula() -- relative vs absolute
- [ ] Whitelist фильтр (INI vs буфер)
- [ ] RZM_EXPORT_FULL_INI флаг
- [ ] QA: все элементы покрыты

### Фаза 4 -- Валидация
- [ ] Параллельный запуск старого и нового INI
- [ ] Цель: < 30% строк от текущего
- [ ] Цель: время парсинга < 0.4s (сейчас 1.2s)
- [ ] Smoke test: вся интерактивность работает идентично

---

## 9. Ответы на вопросы

**Q: 0% статики -- почему тест показал 10%?**
A: Два разных вопроса. 10% = целые элементы без командлиста. 0% = ни один элемент не обходится без хотя бы одной шаблонной строки. Реальная экономия -- в строках внутри элементов: 81% из них шаблон.

**Q: Цепочка из 15 элементов?**
A: Топосортировка. buf_index(parent) < buf_index(child) всегда. CS итерирует линейно от 0 до N. Элемент 15 обрабатывается последним, все предки уже в FinalPosBuffer.

**Q: Формула relative vs absolute?**
A: Парсер смотрит есть ли $PositionX/$PositionY в тексте формулы. Да -> RELATIVE, нет -> ABSOLUTE. Флаг в slot 7.y.

**Q: Как буфер не перезапишет статику при частичном обновлении?**
A: slot_mask в x111. Шейдер патчит только помеченные слоты. static_data.buf read-only, DataBuffer инициализируется из него в начале кадра.

**Q: Preset/Helper -- логика vs визуал?**
A: Визуал -- через расширенный instancer (42 quads). Логика -- остаётся в INI как отдельный CommandListElement_<preset_name>.
