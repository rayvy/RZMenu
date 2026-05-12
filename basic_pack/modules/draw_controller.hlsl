// ==================================================================
// == cs.hlsl - Версия "Бригадир" + Phase 0.5 ElementStaticMap
// ==================================================================
RWBuffer<float4> DataBuffer           : register(u0);
RWBuffer<uint>   IndexBuffer          : register(u1);
Buffer<float4>   ResourceStyleBuffer  : register(t105);
// Phase 0.5: compact sorted array {float(id), float(imageID), float(textID), 0}
// Indexed by linear scan matching IN_ELEMENT_ID. Sentinel entry id==0 stops scan.
Buffer<float4>   ElementStaticMap     : register(t106);

Texture1D<float4> IniParams : register(t120);
Buffer<uint>      InputTextBuffer : register(t24);

#define SCREEN_RES       IniParams[99].zw

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
// Phase 0.5: w111 = $id of the current main element (set by j2 template)
#define IN_ELEMENT_ID    (uint)IniParams[111].w

// Phase 0.5: flag bits (mirrors element_static_map.py)
#define FLAG_USE_STATIC_IMG  0x01u  // read imageID from ElementStaticMap
#define FLAG_USE_STATIC_TEXT 0x02u  // read textID  from ElementStaticMap
#define FLAG_IS_ELEMENT      0x04u  // this is a main rzm.element

[numthreads(1, 1, 1)]
void main(uint3 ThreadId : SV_DispatchThreadID)
{
    uint base_idx = IN_BUFFER_OFFSET;
    uint flags    = IN_FLAGS;

    IndexBuffer[BUFFER_INDEX] = base_idx;

    // ── EXISTING WRITES (unchanged) ──────────────────────────────────────────
    DataBuffer[base_idx + 0] = float4(asfloat(flags), 0, 0, 0);
    DataBuffer[base_idx + 1] = float4(IN_POS, IN_SIZE);
    DataBuffer[base_idx + 2] = IN_COLOR;
    DataBuffer[base_idx + 3] = IN_TILE_DATA;
    DataBuffer[base_idx + 4] = float4(IN_MIRROR_MODE, IN_FONT_SLOT, 0, IN_ROT);

    // Проверяем, нужно ли вообще применять клиппинг (если не 0,0,0,0)
    if (any(IN_CLIP_RECT))
    {
        // Прямоугольник уже в пикселях, просто записываем его в буфер как есть.
        DataBuffer[base_idx + 5] = IN_CLIP_RECT;
    }
    else
    {
        // Если клиппинг не нужен, записываем нули.
        DataBuffer[base_idx + 5] = float4(0, 0, 0, 0);
    }

    DataBuffer[base_idx + 6] = float4(IN_FN_TYPE, IN_STYLE_ID, IN_TEX_ID, IN_DRAW_MODE);
    // ── END EXISTING WRITES ──────────────────────────────────────────────────

    // ── Phase 0.5: ElementStaticMap lookup ───────────────────────────────────
    // Only runs when FLAG_IS_ELEMENT is set (main rzm.elements only).
    // Presets, helpers, and prebuild elements have x111=0 — this block is skipped.
    [branch]
    if (flags & FLAG_IS_ELEMENT)
    {
        uint target_id   = IN_ELEMENT_ID;  // $id of the element (from w111)
        uint found_image = 0u;
        uint found_text  = 0u;

        // Linear scan — N < 512, negligible cost for a single-thread CS
        [loop]
        for (int i = 0; i < 2048; i++)
        {
            float4 entry    = ElementStaticMap[i];
            uint   entry_id = (uint)entry.x;
            if (entry_id == 0u) break;           // sentinel reached, stop
            if (entry_id == target_id)
            {
                found_image = (uint)entry.y;
                found_text  = (uint)entry.z;
                break;
            }
        }

        // ── Apply static imageID ──
        // Override slot 3 .x only if:
        //   1. FLAG_USE_STATIC_IMG is set (no conditional_images on this element)
        //   2. The buffer actually has a valid imageID for this element
        //   3. INI did NOT supply an override (x102.x == 0 when $imageID was commented out)
        //      When INI sets $imageID via conditional block, x102 > 0 → INI wins.
        [branch]
        if ((flags & FLAG_USE_STATIC_IMG) && found_image > 0u)
        {
            float ini_image = IN_TILE_DATA.x;
            if (ini_image < 0.5f)
            {
                // INI provided no value -> use static buffer
                float4 temp = DataBuffer[base_idx + 3];
                temp.x = (float)found_image;
                DataBuffer[base_idx + 3] = temp;
            }
            // else: INI conditional block set a value → already written above, keep it
        }

        // ── Apply static textID ──
        // Same priority logic as imageID above.
        [branch]
        if ((flags & FLAG_USE_STATIC_TEXT) && found_text > 0u)
        {
            float ini_text = IN_TILE_DATA.x;  // textID also comes through x102
            if (ini_text < 0.5f)
            {
                float4 temp = DataBuffer[base_idx + 3];
                temp.x = (float)found_text;
                DataBuffer[base_idx + 3] = temp;
            }
        }
    }
    // ── END Phase 0.5 ────────────────────────────────────────────────────────
}