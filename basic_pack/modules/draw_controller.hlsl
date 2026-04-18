// ==================================================================
// == cs.hlsl - Версия "Бригадир" (Исправленная)
// ==================================================================
RWBuffer<float4> DataBuffer           : register(u0);

Texture1D<float4> IniParams : register(t120);
Buffer<uint>      InputTextBuffer : register(t24);

#define SCREEN_RES     IniParams[99].zw

#define IN_POS         IniParams[100].xy
#define IN_SIZE        IniParams[100].zw
#define IN_COLOR       IniParams[101]
#define IN_TILE_DATA   IniParams[102]
#define IN_FX_PARAMS   IniParams[104]
#define IN_MIRROR_MODE IniParams[105].x
#define IN_FONT_SLOT   IniParams[105].y
#define IN_ROT         IniParams[105].w
#define IN_CLIP_RECT   IniParams[109].xyzw
#define IN_FN_TYPE     IniParams[110].x
#define IN_FX_TYPE     IniParams[110].y
#define IN_TEX_ID      IniParams[110].z
#define IN_DRAW_MODE   IniParams[110].w
#define BUFFER_INDEX   (int)IniParams[111].y

[numthreads(1, 1, 1)]
void main(uint3 ThreadId : SV_DispatchThreadID)
{
    uint base_idx = BUFFER_INDEX * 6;
    
    DataBuffer[base_idx + 0] = float4(IN_POS, IN_SIZE);
    DataBuffer[base_idx + 1] = IN_COLOR;
    DataBuffer[base_idx + 2] = IN_TILE_DATA;
    DataBuffer[base_idx + 3] = float4(IN_MIRROR_MODE, IN_FONT_SLOT, 0, IN_ROT);
    
    // Проверяем, нужно ли вообще применять клиппинг (если не 0,0,0,0)
    if (any(IN_CLIP_RECT))
    {
        // Прямоугольник уже в пикселях, просто записываем его в буфер как есть.
        DataBuffer[base_idx + 4] = IN_CLIP_RECT;
    }
    else
    {
        // Если клиппинг не нужен, записываем нули.
        DataBuffer[base_idx + 4] = float4(0, 0, 0, 0);
    }
    
    DataBuffer[base_idx + 5] = float4(IN_FN_TYPE, IN_FX_TYPE, IN_TEX_ID, IN_DRAW_MODE);
}