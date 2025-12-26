// ==================================================================
// == srgb_to_linear.hlsl - Конвертирует текстуру из sRGB в Linear
// ==================================================================

// Входная текстура в sRGB пространстве (например, ваш PNG)
Texture2D<float4> sRGB_Texture : register(t111);

SamplerState s0_s : register(s0)
{
    Filter = MIN_MAG_MIP_POINT;
    AddressU = CLAMP;
    AddressV = CLAMP;
};

struct vs2ps {
    float4 pos : SV_Position;
    float2 uv  : TEXCOORD0;
};

// Функция для преобразования одного цветового канала из sRGB в Linear
float sRGB_to_Linear(float c)
{
    if (c <= 0.04045)
    {
        return c / 12.92;
    }
    return pow((c + 0.055) / 1.055, 2.4);
}

#ifdef VERTEX_SHADER
void main(out vs2ps output, uint vertex_id : SV_VertexID) {
    output.uv = float2((vertex_id << 1) & 2, vertex_id & 2);
    output.pos = float4(output.uv * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
}
#endif

#ifdef PIXEL_SHADER
void main(vs2ps input, out float4 result : SV_Target0)
{
    result = sRGB_Texture.Sample(s0_s, input.uv);
}
#endif