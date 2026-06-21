// RZMenu draw controller
// Direct indexed element draw data path.

RWBuffer<float4> DataBuffer          : register(u0);
RWBuffer<uint>   IndexBuffer         : register(u1);
Buffer<float4>   ResourceStyleBuffer : register(t105);

// Legacy resources are still bound by older templates. The hot path below uses
// ElementDrawData instead of binary-searching these buffers.
Buffer<float4>   ElementStaticMap    : register(t106);
Buffer<float4>   ElementDefaultProps : register(t107);
Buffer<uint4>    ElementBlackList    : register(t108);
Buffer<float4>   ElementDrawData     : register(t109);

Texture1D<float4> IniParams : register(t120);
Buffer<uint>      InputTextBuffer : register(t24);

#define IN_POS           IniParams[100].xy
#define IN_SIZE          IniParams[100].zw
#define IN_COLOR         IniParams[101]
#define IN_TILE_DATA     IniParams[102]
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

#define IN_B_POS           IniParams[10].xy
#define IN_B_SIZE          IniParams[10].zw
#define IN_B_COLOR         IniParams[11]
#define IN_B_TILE_DATA     IniParams[12]
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

#define FLAG_USE_STATIC_IMG    0x01u
#define FLAG_USE_STATIC_TEXT   0x02u
#define FLAG_IS_ELEMENT        0x04u
#define FLAG_USE_STATIC_COLOR  0x08u
#define FLAG_SLOT_B_VALID      0x10u

#define FLAG_USE_DEFAULT_STYLE 0x100u
#define FLAG_USE_DEFAULT_FONT  0x200u
#define FLAG_USE_DEFAULT_ROT   0x400u

#define BL_COLOR     0x001u
#define BL_IMAGE_ID  0x002u
#define BL_TEXT_ID   0x004u

#define ELEMENT_DRAW_RECORDS_PER_ELEMENT 5u

void ApplyPackedElementData(
    uint base_idx,
    uint flags,
    float draw_mode,
    uint element_id
)
{
    [branch]
    if (!(flags & FLAG_IS_ELEMENT))
        return;

    uint draw_base = element_id * ELEMENT_DRAW_RECORDS_PER_ELEMENT;
    float4 d1 = ElementDrawData[draw_base + 1u];
    float4 d2 = ElementDrawData[draw_base + 2u];
    float4 d3 = ElementDrawData[draw_base + 3u];
    float4 d4 = ElementDrawData[draw_base + 4u];

    uint found_image = (uint)d1.z;
    uint found_text  = (uint)d1.w;
    uint bl_mask     = (uint)d3.y;
    float has_color  = d4.z;
    bool writes_text_id = (draw_mode == 3.0f || draw_mode == 4.0f);

    [branch]
    if ((flags & FLAG_USE_STATIC_COLOR) && has_color > 0.5f)
    {
        DataBuffer[base_idx + 2] = float4(d3.z, d3.w, d4.x, d4.y);
    }

    [branch]
    if ((flags & FLAG_USE_STATIC_IMG) && found_image > 0u && !writes_text_id)
    {
        float4 tile = DataBuffer[base_idx + 3];
        if (tile.x < 0.5f)
            tile.x = (float)found_image;
        DataBuffer[base_idx + 3] = tile;
    }

    [branch]
    if ((flags & FLAG_USE_STATIC_TEXT) && found_text > 0u && writes_text_id)
    {
        float4 tile = DataBuffer[base_idx + 3];
        if (tile.x < 0.5f)
            tile.x = (float)found_text;
        DataBuffer[base_idx + 3] = tile;
    }

    [branch]
    if (bl_mask != 0u)
    {
        [branch]
        if ((bl_mask & BL_COLOR) && has_color > 0.5f)
        {
            DataBuffer[base_idx + 2] = float4(d3.z, d3.w, d4.x, d4.y);
        }

        [branch]
        if ((bl_mask & BL_IMAGE_ID) && found_image > 0u && !writes_text_id)
        {
            float4 tile = DataBuffer[base_idx + 3];
            tile.x = (float)found_image;
            DataBuffer[base_idx + 3] = tile;
        }

        [branch]
        if ((bl_mask & BL_TEXT_ID) && found_text > 0u && writes_text_id)
        {
            float4 tile = DataBuffer[base_idx + 3];
            tile.x = (float)found_text;
            DataBuffer[base_idx + 3] = tile;
        }
    }

    [branch]
    if ((flags & FLAG_USE_DEFAULT_STYLE) && d2.y > 0.5f)
    {
        float4 params = DataBuffer[base_idx + 6];
        if (params.y < 0.5f)
            params.y = d2.y;
        DataBuffer[base_idx + 6] = params;
    }

    [branch]
    if (flags & (FLAG_USE_DEFAULT_FONT | FLAG_USE_DEFAULT_ROT))
    {
        float4 mirror = DataBuffer[base_idx + 4];
        if ((flags & FLAG_USE_DEFAULT_FONT) && d2.z > 0.5f && mirror.y < 0.5f)
            mirror.y = d2.z;
        if ((flags & FLAG_USE_DEFAULT_ROT) && abs(d2.w) > 0.000001f && abs(mirror.w) <= 0.000001f)
            mirror.w = d2.w;
        DataBuffer[base_idx + 4] = mirror;
    }
}

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

    ApplyPackedElementData(base_idx, flags, draw_mode, element_id);
}

[numthreads(1, 1, 1)]
void main(uint3 ThreadId : SV_DispatchThreadID)
{
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

    [branch]
    if (IN_B_FLAGS & FLAG_SLOT_B_VALID)
    {
        WriteElement(
            IN_BUFFER_OFFSET + 7u,
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
