// Простой шейдер для вывода текстуры из канала t50
Texture2D<float4> tex50 : register(t50);
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
    result = tex50.Sample(s0_s, float2(input.uv.x, input.uv.y));
}
#endif