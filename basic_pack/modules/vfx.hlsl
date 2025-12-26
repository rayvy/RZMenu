
Texture1D<float4> IniParams : register(t120);
SamplerState s0_s : register(s0);

Texture2D<float4> tex : register(t40);
#define value IniParams[88].x

struct vs2ps {
	float4 pos : SV_Position0;
	float2 uv : TEXCOORD1;
};
struct PS_INPUT
{
    float4 pos : SV_POSITION;  // позиция на экране
    float2 uv  : TEXCOORD0;    // координаты текстуры
    float4 color : COLOR0;     // цвет (опционально)
};

static const float2 SIZE = float2(1.0, 1.0);
static const float2 OFFSET = float2(0.0, 0.0);
#ifdef VERTEX_SHADER
// Константы сетки (для тестов захардкожены, потом можно заменить на define или IniParams)
#define TILE_X 16
#define TILE_Y 1

void main(
    out vs2ps output,
    uint vertex : SV_VertexID)
{
    float2 BaseCoord, Offset;
    Offset.x = OFFSET.x*2-1;
    Offset.y = (1-OFFSET.y)*2-1;
    BaseCoord.xy = float2((2*SIZE.x),(2*(-SIZE.y)));

    // ======= Позиции модели (оставляем без изменений) =======
    switch(vertex) {
        case 0:
            output.pos.xy = float2(BaseCoord.x+Offset.x, BaseCoord.y+Offset.y);
            output.uv = float2(1,0);
            break;
        case 1:
            output.pos.xy = float2(BaseCoord.x+Offset.x, 0+Offset.y);
            output.uv = float2(1,1);
            break;
        case 2:
            output.pos.xy = float2(0+Offset.x, BaseCoord.y+Offset.y);
            output.uv = float2(0,0);
            break;
        case 3:
            output.pos.xy = float2(0+Offset.x, 0+Offset.y);
            output.uv = float2(0,1);
            break;
        default:
            output.pos.xy = 0;
            output.uv = float2(0,0);
            break;
    };

    output.pos.zw = float2(0, 1);

    // ======= TILE UV =======
    int tileIndex = (int)round(value);

    int tileX = tileIndex % TILE_X;
    int tileY = tileIndex / TILE_X;

    float2 tileSize = float2(1.0 / TILE_X, 1.0 / TILE_Y);
    float2 tileOffset = float2(tileX, tileY) * tileSize;

   tileSize.x += 0.05;

    // Масштаб и сдвиг UV под нужный тайл
    output.uv = output.uv * tileSize + tileOffset;
}
#endif





#ifdef PIXEL_SHADER

void main(vs2ps input, out float4 result : SV_Target0)
{
    uint width, height;
    tex.GetDimensions(width, height);
    if (!width || !height) discard;

    input.uv.y = 1 - input.uv.y;

    float4 baseColor = tex.SampleLevel(s0_s, input.uv.xy, 0);

    result.rgb = baseColor.rgb;
    result.a   = 1;
}
#endif


RWTexture2D<float4>  tex0 : register(u5);
RWTexture2D<float4>  tex1 : register(u4);
#ifdef COMPUTE_SHADER
[numthreads(32, 32, 1)]
void main(uint3 id : SV_DispatchThreadID)
{
    tex0[id.xy] = tex1.Load(id.xy);
	// tex0[id.xy].xyz = result.xyz;
}
#endif