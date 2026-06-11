// ==================================================================
// == cs.hlsl - Версия "Бригадир" + Phase 0.5 ElementStaticMap
//           + Phase 0.5.5: Color Bake, BlackList Buffer, loop i+=2
//           + Phase 0.6: Dual Collector (slots 10-21 + 100-111)
// ==================================================================
RWBuffer<float4> DataBuffer           : register(u0);
RWBuffer<uint>   IndexBuffer          : register(u1);
Buffer<float4>   ResourceStyleBuffer  : register(t105);

Buffer<float4>   ElementStaticMap     : register(t106);
Buffer<uint4>    ElementBlackList     : register(t108);

Texture1D<float4> IniParams : register(t120);
Buffer<uint>      InputTextBuffer : register(t24);

#define SCREEN_RES       IniParams[99].zw

// ── Slot A (100-111) ─────────────────────────────────────────────
#define IN_POS           IniParams[100].xy
#define IN_SIZE          IniParams[100].zw
#define IN_COLOR         IniParams[101]
#define IN_TILE_DATA     IniParams[102]
#define IN_FX_PARAMS     IniParams[104]
#define IN_MIRROR_MODE   IniParams[105].x
#define IN_FONT_SLOT     IniParams[105].y
#define IN_ROT           IniParams[105].w
#define IN_CLIP_RECT     IniParams[109].xyzw
#define IN_FN_TYPE       IniParams[110].x
#define IN_STYLE_ID      IniParams[110].y
#define IN_TEX_ID        IniParams[110].z
#define IN_DRAW_MODE     IniParams[110].w
#define BUFFER_INDEX     (int)IniParams[111].y
#define IN_BUFFER_OFFSET (uint)IniParams[111].z
#define IN_FLAGS         (uint)IniParams[111].x
#define IN_ELEMENT_ID    (uint)IniParams[111].w

// ── Slot B (10-21) ───────────────────────────────────────────────
#define IN_B_POS           IniParams[10].xy
#define IN_B_SIZE          IniParams[10].zw
#define IN_B_COLOR         IniParams[11]
#define IN_B_TILE_DATA     IniParams[12]
#define IN_B_FX_PARAMS     IniParams[14]
#define IN_B_MIRROR_MODE   IniParams[15].x
#define IN_B_FONT_SLOT     IniParams[15].y
#define IN_B_ROT           IniParams[15].w
#define IN_B_CLIP_RECT     IniParams[19].xyzw
#define IN_B_FN_TYPE       IniParams[20].x
#define IN_B_STYLE_ID      IniParams[20].y
#define IN_B_TEX_ID        IniParams[20].z
#define IN_B_DRAW_MODE     IniParams[20].w
#define IN_B_BUFFER_INDEX  (int)IniParams[21].y
#define IN_B_BUFFER_OFFSET (uint)IniParams[21].z
#define IN_B_FLAGS         (uint)IniParams[21].x
#define IN_B_ELEMENT_ID    (uint)IniParams[21].w

// ── Flag bits ────────────────────────────────────────────────────
#define FLAG_USE_STATIC_IMG   0x01u
#define FLAG_USE_STATIC_TEXT  0x02u
#define FLAG_IS_ELEMENT       0x04u
#define FLAG_USE_STATIC_COLOR 0x08u
#define FLAG_SLOT_B_VALID     0x10u  // set в x21 если второй слот активен

// ── BlackList mask bits ──────────────────────────────────────────
#define BL_COLOR     0x001u
#define BL_IMAGE_ID  0x002u
#define BL_TEXT_ID   0x004u


// ================================================================
// Общая функция записи одного элемента в буфер
// ================================================================
void WriteElement(
    uint   base_idx,
    uint   flags,
    int    buf_index,
    float2 pos,
    float2 size,
    float4 color,
    float4 tile_data,
    float  mirror_mode,
    float  font_slot,
    float  rot,
    float4 clip_rect,
    float  fn_type,
    float  style_id,
    float  tex_id,
    float  draw_mode,
    uint   element_id
)
{
    IndexBuffer[buf_index] = base_idx;

    DataBuffer[base_idx + 0] = float4(asfloat(flags), 0, 0, 0);
    DataBuffer[base_idx + 1] = float4(pos, size);
    DataBuffer[base_idx + 2] = color;
    DataBuffer[base_idx + 3] = tile_data;
    DataBuffer[base_idx + 4] = float4(mirror_mode, font_slot, 0, rot);

    if (any(clip_rect))
        DataBuffer[base_idx + 5] = clip_rect;
    else
        DataBuffer[base_idx + 5] = float4(0, 0, 0, 0);

    DataBuffer[base_idx + 6] = float4(fn_type, style_id, tex_id, draw_mode);

    // ── ElementStaticMap lookup ──────────────────────────────────
    [branch]
    if ((flags & FLAG_IS_ELEMENT) && (flags & (FLAG_USE_STATIC_IMG | FLAG_USE_STATIC_TEXT | FLAG_USE_STATIC_COLOR)))
    {
        uint  target_id   = element_id;
        uint  found_image = 0u;
        uint  found_text  = 0u;
        float found_r     = 0.0f;
        float found_g     = 0.0f;
        float found_b     = 0.0f;
        float found_a     = 0.5f;
        float has_color   = 0.0f;

        uint num_structs = 0;
        ElementStaticMap.GetDimensions(num_structs);
        int low = 0;
        int high = (int)(num_structs / 2) - 2; // Exclude sentinel at the end

        [loop]
        while (low <= high)
        {
            int mid = (low + high) / 2;
            float4 A = ElementStaticMap[mid * 2];
            uint entry_id = (uint)A.x;

            if (entry_id == target_id)
            {
                found_image = (uint)A.y;
                found_text  = (uint)A.z;
                has_color   = A.w;
                float4 B    = ElementStaticMap[mid * 2 + 1];
                found_r = B.x;
                found_g = B.y;
                found_b = B.z;
                found_a = B.w;
                break;
            }
            if (entry_id < target_id)
            {
                low = mid + 1;
            }
            else
            {
                high = mid - 1;
            }
        }

        [branch]
        if (found_image > 0u && fn_type != 2.0f)
        {
            float ini_image = DataBuffer[base_idx + 3].x;
            if (ini_image < 0.5f)
            {
                float4 temp = DataBuffer[base_idx + 3];
                temp.x = (float)found_image;
                DataBuffer[base_idx + 3] = temp;
            }
        }

        [branch]
        if (found_text > 0u && fn_type == 2.0f)
        {
            float ini_text = DataBuffer[base_idx + 3].x;
            if (ini_text < 0.5f)
            {
                float4 temp = DataBuffer[base_idx + 3];
                temp.x = (float)found_text;
                DataBuffer[base_idx + 3] = temp;
            }
        }

        [branch]
        if ((flags & FLAG_USE_STATIC_COLOR) && has_color > 0.5f)
        {
            DataBuffer[base_idx + 2] = float4(found_r, found_g, found_b, found_a);
        }

        // ── BlackList ────────────────────────────────────────────
        uint bl_mask = 0u;
        uint total_bl_structs = 0;
        ElementBlackList.GetDimensions(total_bl_structs);
        int low_bl = 0;
        int high_bl = (int)total_bl_structs - 2; // Exclude sentinel at the end

        [loop]
        while (low_bl <= high_bl)
        {
            int mid = (low_bl + high_bl) / 2;
            uint4 bl_entry = ElementBlackList[mid];
            uint entry_id = bl_entry.x;

            if (entry_id == target_id)
            {
                bl_mask = bl_entry.y;
                break;
            }
            if (entry_id < target_id)
            {
                low_bl = mid + 1;
            }
            else
            {
                high_bl = mid - 1;
            }
        }

        [branch]
        if (bl_mask != 0u)
        {
            [branch]
            if ((bl_mask & BL_COLOR) && has_color > 0.5f)
                DataBuffer[base_idx + 2] = float4(found_r, found_g, found_b, found_a);

            [branch]
            if ((bl_mask & BL_IMAGE_ID) && found_image > 0u && fn_type != 2.0f)
            {
                float4 temp = DataBuffer[base_idx + 3];
                temp.x = (float)found_image;
                DataBuffer[base_idx + 3] = temp;
            }

            [branch]
            if ((bl_mask & BL_TEXT_ID) && found_text > 0u && fn_type == 2.0f)
            {
                float4 temp = DataBuffer[base_idx + 3];
                temp.x = (float)found_text;
                DataBuffer[base_idx + 3] = temp;
            }
        }
    }
}


[numthreads(1, 1, 1)]
void main(uint3 ThreadId : SV_DispatchThreadID)
{
    // ── Slot A всегда пишем ──────────────────────────────────────
    WriteElement(
        IN_BUFFER_OFFSET,
        IN_FLAGS,
        BUFFER_INDEX,
        IN_POS,
        IN_SIZE,
        IN_COLOR,
        IN_TILE_DATA,
        IN_MIRROR_MODE,
        IN_FONT_SLOT,
        IN_ROT,
        IN_CLIP_RECT,
        IN_FN_TYPE,
        IN_STYLE_ID,
        IN_TEX_ID,
        IN_DRAW_MODE,
        IN_ELEMENT_ID
    );

    // ── Slot B пишем только если активен ────────────────────────
    [branch]
    if (IN_B_FLAGS & FLAG_SLOT_B_VALID)
    {
        WriteElement(
            IN_BUFFER_OFFSET + 7u,  // <-- сдвиг на один элемент вперёд
            IN_B_FLAGS,
            IN_B_BUFFER_INDEX,
            IN_B_POS,
            IN_B_SIZE,
            IN_B_COLOR,
            IN_B_TILE_DATA,
            IN_B_MIRROR_MODE,
            IN_B_FONT_SLOT,
            IN_B_ROT,
            IN_B_CLIP_RECT,
            IN_B_FN_TYPE,
            IN_B_STYLE_ID,
            IN_B_TEX_ID,
            IN_B_DRAW_MODE,
            IN_B_ELEMENT_ID
        );
    }
}