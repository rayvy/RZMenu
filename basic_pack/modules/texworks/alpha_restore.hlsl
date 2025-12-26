// ==================================================================
// == alpha_restore.hlsl
// == Принимает текстуру с правильным цветом, но испорченной альфой,
// == и восстанавливает оригинальный альфа-канал с текстуры кожи.
// ==================================================================

// t40: Результат работы инстансера (Правильный RGB, Альфа = 1.0)
Texture2D<float4> DecalResultTex : register(t40);
// t41: Оригинальная текстура кожи (Неправильный RGB, ПРАВИЛЬНАЯ Альфа)
Texture2D<float4> OriginalSkinTex : register(t41);

SamplerState s0_s : register(s0);

struct vs2ps {
    float4 pos : SV_Position;
    float2 uv  : TEXCOORD0;
};

#ifdef VERTEX_SHADER
void main(out vs2ps output, uint vertex_id : SV_VertexID) {
    output.uv = float2((vertex_id << 1) & 2, vertex_id & 2);
    output.pos = float4(output.uv * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
}
#endif

#ifdef PIXEL_SHADER
void main(vs2ps input, out float4 result : SV_Target0)
{
    // Берем цвет из результата работы инстансера
    float3 correctRGB = DecalResultTex.Sample(s0_s, input.uv).rgb;
    
    // Берем альфа-канал из ОРИГИНАЛЬНОЙ текстуры кожи
    float originalAlpha = OriginalSkinTex.Sample(s0_s, input.uv).a;
    
    // Собираем финальный пиксель.
    // Вместо result.w = 0 мы используем настоящую альфу.
    result = float4(correctRGB, originalAlpha);
}
#endif