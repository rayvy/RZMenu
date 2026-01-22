// Rayvich's runtime material combiner - Модифицирован для произвольного размещения
// Текстурные слоты t50-t73 (всего 24)
Texture1D<float4> IniParams : register(t120);
#define colorshift IniParams[55].x

Texture2D<float4> tex00 : register(t50);
Texture2D<float4> tex01 : register(t51);
Texture2D<float4> tex02 : register(t52);
Texture2D<float4> tex03 : register(t53);
Texture2D<float4> tex04 : register(t54);
Texture2D<float4> tex05 : register(t55);
Texture2D<float4> tex06 : register(t56);
Texture2D<float4> tex07 : register(t57);
Texture2D<float4> tex08 : register(t58);
Texture2D<float4> tex09 : register(t59);
Texture2D<float4> tex10 : register(t60);
Texture2D<float4> tex11 : register(t61);
Texture2D<float4> tex12 : register(t62);
Texture2D<float4> tex13 : register(t63);
Texture2D<float4> tex14 : register(t64);
Texture2D<float4> tex15 : register(t65);
Texture2D<float4> tex16 : register(t66);
Texture2D<float4> tex17 : register(t67);
Texture2D<float4> tex18 : register(t68);
Texture2D<float4> tex19 : register(t69);
Texture2D<float4> tex20 : register(t70);
Texture2D<float4> tex21 : register(t71);
Texture2D<float4> tex22 : register(t72);
Texture2D<float4> tex23 : register(t73);


// Буфер, содержащий данные о позиции и размере для каждой текстуры.
// Каждый float4 хранит: pos.x, pos.y, size.x, size.y
StructuredBuffer<float4> AtlasData : register(t0);

SamplerState s0_s : register(s0);

struct vs2ps {
    float4 pos : SV_Position;
    float2 uv  : TEXCOORD0;
};

float4 SafeSample(in Texture2D<float4> tex, float2 uv)
{
    return tex.Sample(s0_s, uv);
}

#ifdef VERTEX_SHADER
// Вершинный шейдер остался без изменений - он просто рисует полноэкранный треугольник.
void main(out vs2ps output, uint vertex_id : SV_VertexID) {
    output.uv = float2((vertex_id << 1) & 2, vertex_id & 2);
    output.pos = float4(output.uv * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
}
#endif


float3 RGBtoHSV(float3 c)
{
    float4 K = float4(0.0, -1.0/3.0, 2.0/3.0, -1.0);
    float4 p = lerp(float4(c.bg, K.wz), float4(c.gb, K.xy), step(c.b, c.g));
    float4 q = lerp(float4(p.xyw, c.r), float4(c.r, p.yzx), step(p.x, c.r));

    float d = q.x - min(q.w, q.y);
    float e = 1e-10;
    return float3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}

float3 HSVtoRGB(float3 c)
{
    float4 K = float4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    float3 p = abs(frac(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * lerp(K.xxx, saturate(p - 1.0), c.y);
}


#ifdef PIXEL_SHADER
void main(vs2ps input, out float4 result : SV_Target0)
{
    [loop]
    for (int i = 0; i < 4; i++)
    {
        float4 data = AtlasData[i];
        float topY = 1.0 - data.y - data.w;
        if (input.uv.x >= data.x && input.uv.x < (data.x + data.z) &&
            input.uv.y >= topY && input.uv.y < (topY + data.w))
        {
            // Теперь вычисляем localUV, используя уже правильные, согласованные координаты
            float2 localUV = float2(
                (input.uv.x - data.x) / data.z,
                (input.uv.y - topY) / data.w 
            );

            // Семплируем нужную текстуру в зависимости от индекса
            switch(i)
            {  
                // localUV.y = 1.0 - localUV.y;
                case 0: result = SafeSample(tex00, localUV); break;
                case 1: result = SafeSample(tex01, localUV); break;
                case 2: result = SafeSample(tex02, localUV); break;
                case 3: result = SafeSample(tex03, localUV); break;
            }
            float hueShiftAmount = colorshift.x;
            float3 hsv = RGBtoHSV(result.rgb);
            hsv.x = frac(hsv.x + hueShiftAmount); // сдвигаем оттенок
            result.xyz = HSVtoRGB(hsv.rgb);
            return;
        }
    }
    result = float4(0, 0, 0, 0);
}
#endif