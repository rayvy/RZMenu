SamplerState s0_s : register(s0);
struct vs2ps {
    float4 pos : SV_Position0;
    float2 uv : TEXCOORD1;
};

#ifdef VERTEX_SHADER
void main(
        out vs2ps output,
        uint vertex : SV_VertexID)
{
    float2 Offset = float2(-1.0, -1.0);
    float2 QuadSize = float2(2.0, 2.0);
    switch (vertex) {
        case 0: // Верхняя правая вершина
            output.pos.xy = float2(QuadSize.x + Offset.x, QuadSize.y + Offset.y);
            output.uv = float2(1, 0);
            break;
        case 1: // Нижняя правая вершина
            output.pos.xy = float2(QuadSize.x + Offset.x, 0 + Offset.y);
            output.uv = float2(1, 1);
            break;
        case 2: // Верхняя левая вершина
            output.pos.xy = float2(0 + Offset.x, QuadSize.y + Offset.y);
            output.uv = float2(0, 0);
            break;
        case 3: // Нижняя левая вершина
            output.pos.xy = float2(0 + Offset.x, 0 + Offset.y);
            output.uv = float2(0, 1);
            break;
        default:
            output.pos.xy = 0;
            output.uv = float2(0, 0);
            break;
    };

    output.pos.zw = float2(0, 1);
}
#endif

#ifdef PIXEL_SHADER
Texture2D<float4> tex90 : register(t90);
Texture2D<float4> tex91 : register(t91);
Texture2D<float4> tex92 : register(t92);
Texture2D<float4> tex93 : register(t93);
Texture2D<float4> tex94 : register(t94);
Texture2D<float4> tex95 : register(t95);
Texture2D<float4> tex96 : register(t96);
Texture2D<float4> tex97 : register(t97);
Texture2D<float4> tex98 : register(t98);
Texture2D<float4> tex99 : register(t99);

Texture1D<float4> IniParams : register(t120);
#define time IniParams[99].w

float rand(float2 uv) {
    return frac(sin(dot(uv, float2(12.9898, 78.233))) * 43758.5453);
}

float glitchPattern(float2 uv) {
    float sizeFactor = lerp(25.0, 30.0, rand(float2(0, uv.y)));
    float2 blockUV = floor(uv * sizeFactor) / sizeFactor;
    float noise = rand(blockUV + time * 0.3);
    return step(0.6, noise);
}

void main(vs2ps input, out float4 result : SV_Target0)
{
    // Берём базовый кадр без глитча
    float3 base = tex99.SampleLevel(s0_s, input.uv, 0).rgb;
    float alpha = 0.9;

    // Ghosting: от нового кадра к старому с постепенным уменьшением вклада
    base = lerp(base, tex98.SampleLevel(s0_s, input.uv, 0).rgb, 0.8);
    base = lerp(base, tex97.SampleLevel(s0_s, input.uv, 0).rgb, 0.7);
    base = lerp(base, tex96.SampleLevel(s0_s, input.uv, 0).rgb, 0.6);
    base = lerp(base, tex95.SampleLevel(s0_s, input.uv, 0).rgb, 0.5);
    base = lerp(base, tex94.SampleLevel(s0_s, input.uv, 0).rgb, 0.4);
    base = lerp(base, tex93.SampleLevel(s0_s, input.uv, 0).rgb, 0.3);
    base = lerp(base, tex92.SampleLevel(s0_s, input.uv, 0).rgb, 0.2);
    base = lerp(base, tex91.SampleLevel(s0_s, input.uv, 0).rgb, 0.1);
    base = lerp(base, tex90.SampleLevel(s0_s, input.uv, 0).rgb, 0.05);

    // Глитч — применяем после всех смешиваний
    float shift = 0.005 * glitchPattern(float2(0, input.uv.y));
    float2 glitchUV = float2(input.uv.x + shift * time, input.uv.y + shift * time);

    float3 glitchColor = tex99.SampleLevel(s0_s, glitchUV, 0).rgb;

    // Смешиваем итог с глитчем (регулируй 0.3 для силы эффекта)
    base = lerp(base, glitchColor, 0.9);

    result = float4(base, alpha);
}
#endif

