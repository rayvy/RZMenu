// ==================================================================
// == cs.hlsl - Версия "Бригадир" + Phase 0.5 ElementStaticMap
//           + Phase 0.5.5: Color Bake, BlackList Buffer, loop i+=2
// ==================================================================
RWBuffer<float4> DataBuffer           : register(u0);
RWBuffer<uint>   IndexBuffer          : register(u1);
Buffer<float4>   ResourceStyleBuffer  : register(t105);

// Phase 0.5/0.5.5: compact sorted array {float(id), float(imageID), float(textID), float(has_color)}
//                                      + {float(R), float(G), float(B), float(A)}
// 2x float4 per entry. Loop step = 2. Sentinel: first float4 with id==0.
Buffer<float4>   ElementStaticMap     : register(t106);

// Phase 0.5.5: BlackList buffer — compact sorted array {uint(id), uint(mask), 0, 0}
// mask bits force static values from ElementStaticMap regardless of INI input.
// BL_COLOR=0x001, BL_IMAGE_ID=0x002, BL_TEXT_ID=0x004
// Slots 0x008+ reserved for Phase 0.6 (style_id, fn_type, etc.)
Buffer<uint4>    ElementBlackList     : register(t108);

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
// Phase 0.5: w111 = $id of the current element (set by j2 template)
// Phase 0.5.5: for presets/helpers w111 = $preset_id/$helper_id (true Blender id)
#define IN_ELEMENT_ID    (uint)IniParams[111].w

// Phase 0.5: flag bits
#define FLAG_USE_STATIC_IMG   0x01u  // read imageID from ElementStaticMap
#define FLAG_USE_STATIC_TEXT  0x02u  // read textID  from ElementStaticMap
#define FLAG_IS_ELEMENT       0x04u  // this is a main rzm.element (or preset/helper using their true id)
// Phase 0.5.5: flag bits
#define FLAG_USE_STATIC_COLOR 0x08u  // read RGBA color from ElementStaticMap

// Phase 0.5.5: BlackList mask bits (mirror element_blacklist.py)
#define BL_COLOR     0x001u
#define BL_IMAGE_ID  0x002u
#define BL_TEXT_ID   0x004u
// Reserved Phase 0.6: BL_STYLE_ID=0x008, BL_FN_TYPE=0x010, ...

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

    if (any(IN_CLIP_RECT))
    {
        DataBuffer[base_idx + 5] = IN_CLIP_RECT;
    }
    else
    {
        DataBuffer[base_idx + 5] = float4(0, 0, 0, 0);
    }

    DataBuffer[base_idx + 6] = float4(IN_FN_TYPE, IN_STYLE_ID, IN_TEX_ID, IN_DRAW_MODE);
    // ── END EXISTING WRITES ──────────────────────────────────────────────────

    // ── Phase 0.5/0.5.5: ElementStaticMap lookup ─────────────────────────────
    // Runs when FLAG_IS_ELEMENT is set — main elements, and presets/helpers
    // that pass their true Blender id via w111 (Phase 0.5.5).
    [branch]
    if (flags & FLAG_IS_ELEMENT)
    {
        uint target_id   = IN_ELEMENT_ID;
        uint found_image = 0u;
        uint found_text  = 0u;
        float found_r    = 0.0f;
        float found_g    = 0.0f;
        float found_b    = 0.0f;
        float found_a    = 0.5f;
        float has_color  = 0.0f;

        // Phase 0.5.5: loop step = 2 (each entry is now 2x float4)
        [loop]
        for (int i = 0; i < 4096; i += 2)
        {
            float4 A        = ElementStaticMap[i];
            uint   entry_id = (uint)A.x;
            if (entry_id == 0u) break;           // sentinel reached, stop
            if (entry_id == target_id)
            {
                found_image = (uint)A.y;
                found_text  = (uint)A.z;
                has_color   = A.w;               // Phase 0.5.5: 1.0 if static color

                float4 B = ElementStaticMap[i + 1];
                found_r = B.x;
                found_g = B.y;
                found_b = B.z;
                found_a = B.w;
                break;
            }
        }

        // ── Apply static imageID ──
        // Condition: buffer has a valid imageID AND INI did not supply an override.
        // The FLAG_USE_STATIC_IMG bit is an INI-generation hint (suppresses $imageID write
        // in the template). The CS applies from buffer whenever found_image > 0 and INI
        // didn't set a value (ini_image < 0.5). This matches Phase 0.5 behaviour and
        // correctly handles hover_image_id elements (their $imageID is written by INI
        // conditionally; when it is, ini_image >= 1, so buffer won't override).
        [branch]
        if (found_image > 0u && IN_FN_TYPE != 2.0f)
        {
            float ini_image = IN_TILE_DATA.x;
            if (ini_image < 0.5f)
            {
                float4 temp = DataBuffer[base_idx + 3];
                temp.x = (float)found_image;
                DataBuffer[base_idx + 3] = temp;
            }
        }

        // ── Apply static textID ──
        // Same: buffer wins when found_text > 0 and INI didn't write $TextID.
        [branch]
        if (found_text > 0u && IN_FN_TYPE == 2.0f)
        {
            float ini_text = IN_TILE_DATA.x;
            if (ini_text < 0.5f)
            {
                float4 temp = DataBuffer[base_idx + 3];
                temp.x = (float)found_text;
                DataBuffer[base_idx + 3] = temp;
            }
        }

        // ── Phase 0.5.5: Apply static color ──
        // Condition: FLAG_USE_STATIC_COLOR set AND has_color == 1.0 in buffer.
        // INI wrote $colorR/G/B/A = 0 (RestoreElement reset), so we always apply.
        // BlackList will also enforce this, but this early write is the primary path.
        [branch]
        if ((flags & FLAG_USE_STATIC_COLOR) && has_color > 0.5f)
        {
            DataBuffer[base_idx + 2] = float4(found_r, found_g, found_b, found_a);
        }

        // ── Phase 0.5.5: BlackList enforcement ──────────────────────────────
        // Secondary protection: forces static data REGARDLESS of what INI wrote.
        // Handles edge cases where RestoreElement reset didn't fully protect against
        // residual values from parent/sibling CommandLists.
        uint bl_mask = 0u;
        [loop]
        for (int k = 0; k < 2048; k++)
        {
            uint4 bl_entry = ElementBlackList[k];
            if (bl_entry.x == 0u) break;
            if (bl_entry.x == target_id)
            {
                bl_mask = bl_entry.y;
                break;
            }
        }

        [branch]
        if (bl_mask != 0u)
        {
            // BL_COLOR: force RGBA from StaticMap — static color is iron-clad
            [branch]
            if ((bl_mask & BL_COLOR) && has_color > 0.5f)
            {
                DataBuffer[base_idx + 2] = float4(found_r, found_g, found_b, found_a);
            }

            // BL_IMAGE_ID: force imageID from StaticMap
            [branch]
            if ((bl_mask & BL_IMAGE_ID) && found_image > 0u && IN_FN_TYPE != 2.0f)
            {
                float4 temp = DataBuffer[base_idx + 3];
                temp.x = (float)found_image;
                DataBuffer[base_idx + 3] = temp;
            }

            // BL_TEXT_ID: force textID from StaticMap
            [branch]
            if ((bl_mask & BL_TEXT_ID) && found_text > 0u && IN_FN_TYPE == 2.0f)
            {
                float4 temp = DataBuffer[base_idx + 3];
                temp.x = (float)found_text;
                DataBuffer[base_idx + 3] = temp;
            }

            // Phase 0.6 slots will be enforced here:
            // BL_STYLE_ID  -> DataBuffer[base_idx + 6].y
            // BL_FN_TYPE   -> DataBuffer[base_idx + 6].x
            // BL_TEX_ID    -> DataBuffer[base_idx + 6].z
            // BL_DRAW_MODE -> DataBuffer[base_idx + 6].w
            // BL_MIRROR    -> DataBuffer[base_idx + 4].x
            // BL_ROT       -> DataBuffer[base_idx + 4].w
        }
        // ── END Phase 0.5.5 ──────────────────────────────────────────────────
    }
    // ── END Phase 0.5/0.5.5 ─────────────────────────────────────────────────
}