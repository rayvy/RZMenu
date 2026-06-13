// ============================================================
// X-Ray fullscreen composite shader
//
// Extended with:
// - 3-layer batch composite
// - shared opacity multiplier
// - independent opacity per X-Ray layer
// - one-pass fullscreen overlay
// - external wall occlusion mask from t23
//
// LayerMask contains pixels of the external body that passed
// the real game depth test.
//
// If a mask pixel does not exist, the X-Ray overlay is discarded.
//
// Made by Unicornshell, SinsOfSeven
// Edited by: Eminem
// ============================================================

Texture1D<float4> IniParams : register(t120);

Texture2D<float4> Layer0    : register(t20);
Texture2D<float4> Layer1    : register(t21);
Texture2D<float4> Layer2    : register(t22);
Texture2D<float4> LayerMask : register(t23);

#define FLIP IniParams[0].zw

#define OPACITY0       IniParams[24].x
#define OPACITY1       IniParams[24].y
#define OPACITY2       IniParams[24].z
#define OPACITY_MASTER IniParams[24].w

#define READY0 IniParams[25].x
#define READY1 IniParams[25].y
#define READY2 IniParams[25].z


#ifdef VERTEX_SHADER

void main(
    uint vid   : SV_VertexID,
    out float4 pos : SV_POSITION,
    out float2 uv  : TEXCOORD0)
{
    float2 positions[3] = {
        float2(-1.0, -1.0),
        float2(-1.0,  3.0),
        float2( 3.0, -1.0)
    };

    float2 uvs[3] = {
        float2(0.0,  1.0),
        float2(0.0, -1.0),
        float2(2.0,  1.0)
    };

    pos = float4(positions[vid], 0.0, 1.0);
    uv  = uvs[vid];
}

#endif


#ifdef PIXEL_SHADER

float PixelExists(float4 color)
{
    return any(abs(color) > 0.000001) ? 1.0 : 0.0;
}


float4 LoadLayer(Texture2D<float4> layer, float2 uv)
{
    uint width;
    uint height;

    layer.GetDimensions(width, height);

    float2 fixedUV = uv;
    fixedUV.y = 1.0 - fixedUV.y;
    if (FLIP.x)
        fixedUV.x = 1.0 - fixedUV.x;

    if (FLIP.y)
        fixedUV.y = 1.0 - fixedUV.y;

    fixedUV = saturate(fixedUV);

    int2 pixel = int2(fixedUV * float2(width, height));

    pixel.x = clamp(pixel.x, 0, (int)width  - 1);
    pixel.y = clamp(pixel.y, 0, (int)height - 1);

    return layer.Load(int3(pixel, 0));
}


void AddLayerOver(
    inout float3 accumPremul,
    inout float  accumAlpha,
    float4 color,
    float  opacity,
    float  ready)
{
    float alpha =
        PixelExists(color) *
        saturate(opacity) *
        saturate(OPACITY_MASTER) *
        saturate(ready);

    accumPremul =
        color.rgb * alpha +
        accumPremul * (1.0 - alpha);

    accumAlpha =
        alpha +
        accumAlpha * (1.0 - alpha);
}


void main(
    float4 svpos : SV_POSITION,
    float2 uv    : TEXCOORD0,
    out float4 target : SV_Target0)
{
    float4 maskColor = LoadLayer(LayerMask, uv);

    float visibility = PixelExists(maskColor);

    if (visibility <= 0.000001)
        discard;

    float4 color0 = LoadLayer(Layer0, uv);
    float4 color1 = LoadLayer(Layer1, uv);
    float4 color2 = LoadLayer(Layer2, uv);

    float3 accumPremul = 0.0;
    float  accumAlpha  = 0.0;

    // bottom -> middle -> top
    AddLayerOver(accumPremul, accumAlpha, color0, OPACITY0, READY0);
    AddLayerOver(accumPremul, accumAlpha, color1, OPACITY1, READY1);
    AddLayerOver(accumPremul, accumAlpha, color2, OPACITY2, READY2);

    if (accumAlpha <= 0.000001)
        discard;

    float3 straightColor =
        accumPremul /
        max(accumAlpha, 0.000001);

    target = float4(straightColor, accumAlpha);
}

#endif