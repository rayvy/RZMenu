// ==================================================================
// == cs.hlsl - Версия "Бригадир" (Исправленная)
// ==================================================================
RWBuffer<float4> PosSizeDataBuffer    : register(u0);
RWBuffer<float4> ColorDataBuffer      : register(u1);
RWBuffer<float4> TileDataBuffer       : register(u2);
RWBuffer<uint>   TextPoolBuffer       : register(u3);
RWBuffer<float4> FxParamsBuffer       : register(u4);
RWBuffer<float4> ClippingDataBuffer     : register(u6);
RWBuffer<float4> DrawParamsBuffer     : register(u7);
Texture1D<float4> IniParams : register(t120);
Buffer<uint>      InputTextBuffer : register(t24);

#define SCREEN_RES     IniParams[99].zw

#define IN_POS         IniParams[100].xy
#define IN_SIZE        IniParams[100].zw
#define IN_COLOR       IniParams[101]
#define IN_TILE_DATA   IniParams[102]
#define IN_FX_PARAMS   IniParams[104]
#define IN_CLIP_RECT   IniParams[109].xyzw
#define IN_FN_TYPE     IniParams[110].x
#define IN_FX_TYPE     IniParams[110].y
#define IN_TEX_ID      IniParams[110].z
#define IN_DRAW_MODE   IniParams[110].w
#define BUFFER_INDEX   (int)IniParams[111].y

[numthreads(1, 1, 1)]
void main(uint3 ThreadId : SV_DispatchThreadID)
{
    PosSizeDataBuffer[BUFFER_INDEX] = float4(IN_POS, IN_SIZE);
    ColorDataBuffer[BUFFER_INDEX]   = IN_COLOR;
    FxParamsBuffer[BUFFER_INDEX]    = IN_FX_PARAMS;
    TileDataBuffer[BUFFER_INDEX] = IN_TILE_DATA;
    // Проверяем, нужно ли вообще применять клиппинг (если не 0,0,0,0)
    if (any(IN_CLIP_RECT))
    {
        // Прямоугольник уже в пикселях, просто записываем его в буфер как есть.
        // Больше не нужно преобразовывать в нормализованные координаты.
        ClippingDataBuffer[BUFFER_INDEX] = IN_CLIP_RECT;
    }
    else
    {
        // Если клиппинг не нужен, записываем нули.
        ClippingDataBuffer[BUFFER_INDEX] = float4(0, 0, 0, 0);
    }
    if (IN_DRAW_MODE == 3) // Режим текста
    {
        // +++ ИСПРАВЛЕННАЯ ЛОГИКА +++

        // source_offset: Откуда мы начинаем читать в ИСХОДНОМ буфере (например, если там несколько строк).
        uint source_offset = (uint)IN_TILE_DATA.x;
        // chunk_length: Сколько символов мы хотим скопировать.
        uint chunk_length  = (uint)IN_TILE_DATA.y;
        // dest_offset: В какое место в общем ПУЛЕ текстов мы хотим положить эту строку.

        // Цикл копирования. Он берет символы из InputTextBuffer, НАЧИНАЯ С source_offset,
        // и кладет их в TextPoolBuffer, НАЧИНАЯ С dest_offset.
        for (uint i = 0; i < chunk_length; ++i)
        {
            TextPoolBuffer[source_offset + i] = InputTextBuffer[i];
        }
    }
    
    DrawParamsBuffer[BUFFER_INDEX] = float4(IN_FN_TYPE, IN_FX_TYPE, IN_TEX_ID, IN_DRAW_MODE);
}