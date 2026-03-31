# Идея по объединению буферов в один (Shader Buffer)

Сейчас аддон генерирует (по всей видимости для 3DMigoto/GIMI/SRMI/EFMI) большое количество отдельных буферов:
- Position Buffer (vb0 / `Resource...Position`)
- Texcoord Buffer (vb1 / `Resource...Texcoord`)
- Blend/Normal/Tangent Buffers (`Resource...Blend`, и т.д.)
- Custom Data Buffers (цвета, трансформы, флаги UI-элементов)

Ограничение на количество слотов (8 UAV или SRV) — это известная проблема в DX11/3DMigoto, когда нужно передавать много кастомных данных (например, для UI-рендера или сложной анимации вершин).

## Суть идеи: Packed ByteAddressBuffer (Raw Buffer)

Вместо того чтобы биндить 8 разных `StructuredBuffer<T>`, мы можем использовать всего **один** большой `ByteAddressBuffer` (или `Buffer<uint>`), в который "упакованы" (Interleaved или Sequential) абсолютно все данные.

### Как это будет работать (Архитектура)

1. **Единый Resource-файл на диске (или в памяти):**
   При экспорте мы сливаем Position, Texcoord, Blend, Color, Transform в один большой бинарный блоб.
   Формат может быть, например, таким (Interleaved):
   `[PosX, PosY, PosZ, PosW, U, V, Nx, Ny, Nz, BlendWeight, Color, Flags...]`
   Все это конвертируется в массив `uint` или `float` (в памяти они занимают 4 байта).

2. **INI-конфиг 3DMigoto:**
   Вместо нескольких `Resource`:
   ```ini
   [ResourceMegaBuffer]
   filename = mega_buffer.buf
   type = Buffer
   format = R32_UINT
   ```

   Биндим в шейдер (выбираем любой свободный слот, например, `t114`):
   ```ini
   [ShaderOverride...]
   ps-t114 = ResourceMegaBuffer
   ```

3. **Логика в HLSL (Сложный парсер):**
   Шейдер должен уметь "распаковывать" данные. Для этого мы передаем ему `override_byte_stride` или константы через `cb0` (или `iniParams`), чтобы он знал, как читать:

   ```hlsl
   // Один глобальный буфер
   Buffer<uint> MegaBuffer : register(t114);

   // Константы структуры (задаются через ini)
   cbuffer LayoutInfo : register(b10) {
       uint stride_in_uints; // Например, 16 uint'ов на вершину
       uint offset_pos;      // 0
       uint offset_uv;       // 4
       uint offset_blend;    // 6
       // ...
   };

   struct VertexData {
       float4 position;
       float2 uv;
       float4 blend;
   };

   VertexData UnpackVertex(uint vertexID) {
       VertexData v;
       uint base_idx = vertexID * stride_in_uints;

       // Распаковка позиции (float4)
       v.position.x = asfloat(MegaBuffer[base_idx + offset_pos + 0]);
       v.position.y = asfloat(MegaBuffer[base_idx + offset_pos + 1]);
       v.position.z = asfloat(MegaBuffer[base_idx + offset_pos + 2]);
       v.position.w = asfloat(MegaBuffer[base_idx + offset_pos + 3]);

       // Распаковка UV (float2)
       v.uv.x = asfloat(MegaBuffer[base_idx + offset_uv + 0]);
       v.uv.y = asfloat(MegaBuffer[base_idx + offset_uv + 1]);

       // Можно даже паковать данные! Например 4 байта цвета в 1 uint:
       // uint packed_color = MegaBuffer[base_idx + offset_color];
       // float r = (packed_color & 0xFF) / 255.0;

       return v;
   }
   ```

### Плюсы:
1. Занимает всего 1 слот (SRV/UAV) в шейдере. Ограничение в 8 буферов полностью исчезает.
2. Меньше строк в `.ini` файлах (1 `Resource` вместо 8).
3. Производительность чтения (Cache Locality) может вырасти, так как данные вершины лежат в памяти рядом (Interleaved data).

### Что нужно изменить в коде RZMenu:
Понадобится переписать этап "Сборки" (Serialization / Export).
Нужно написать класс-сборщик (Parser/Packer), который на этапе экспорта будет брать данные из объектов Blender (Vertices, UVs, Custom Props) и записывать их через `struct.pack('f f f f...', ...)` в единый `bytearray`, а затем сохранять как `.buf` файл.
Также нужно будет обновить шаблонизатор Jinja2 (`rztemplate`), чтобы он генерировал новый `.hlsl` код для чтения этого MegaBuffer.
