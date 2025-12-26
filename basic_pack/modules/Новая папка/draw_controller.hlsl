// ==================================================================
// == cs.hlsl - Rayvich
// ==================================================================
RWBuffer<float4> PosSizeBuffer    : register(u2);
RWBuffer<float4> TileDataBuffer   : register(u3);
RWBuffer<float4> DrawParamsBuffer : register(u4);

Texture1D<float4> IniParams : register(t120);

#define IN_SIZE        IniParams[87].xy
#define IN_OFFSET      IniParams[87].zw
#define IN_TILE_INDEX  IniParams[88].xy
#define IN_TOTAL_TILES IniParams[88].zw
#define IN_DRAW_TYPE   IniParams[89].x
#define IN_TEX_TYPE    IniParams[89].y
#define BUFFER_INDEX   (int)IniParams[89].w


[numthreads(1, 1, 1)]
void main(uint3 ThreadId : SV_DispatchThreadID)
{
    float2 pos = IN_OFFSET;
    float2 size = IN_SIZE;
    float2 tile_idx = IN_TILE_INDEX;
    float2 total_tiles = IN_TOTAL_TILES;
    float draw_type = IN_DRAW_TYPE;

    PosSizeBuffer[BUFFER_INDEX]    = float4(size,pos);
    TileDataBuffer[BUFFER_INDEX]   = float4(tile_idx, total_tiles);
    DrawParamsBuffer[BUFFER_INDEX] = float4(draw_type, IN_TEX_TYPE, 0.0, BUFFER_INDEX);
}