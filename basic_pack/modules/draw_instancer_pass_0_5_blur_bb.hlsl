Texture1D<float4> IniParams : register(t120);
SamplerState s0_s : register(s0);

struct vs2ps {
    float4 pos : SV_Position;
    float2 uv : TEXCOORD1;
};

static const float2 SIZE = float2(1.0, 1.0);
static const float2 OFFSET = float2(0.0, 0.0);

// Параметры из IniParams


#ifdef VERTEX_SHADER
void main(out vs2ps output, uint vertex : SV_VertexID)
{
    float2 pos[6] = {
    float2(-1,  1), float2( 1,  1), float2(-1, -1), // Первый треугольник (Верх-Лево, Верх-Право, Низ-Лево)
    float2(-1, -1), float2( 1,  1), float2( 1, -1)  // Второй треугольник (Низ-Лево, Верх-Право, Низ-Право)
};

float2 uv[6] = {
    float2(0, 0), float2(1, 0), float2(0, 1),
    float2(0, 1), float2(1, 0), float2(1, 1)
};

    uint id = vertex % 6; 

    output.pos = float4(pos[id], 0, 1);
    output.uv  = uv[id];
}
#endif

#ifdef PIXEL_SHADER
Texture2D<float4> tex : register(t91);

// Параметры из IniParams (примерные индексы, подставь свои)
#define BLUR_POWER    2.0 
#define SAT_VAL       1.25  // 1.0 = нейтрально
#define WHITE_VAL     -0.05  // 0.0 = нейтрально

void main(vs2ps input, out float4 result : SV_Target0)
{
    float2 uv = input.uv;
    uint width, height;
    tex.GetDimensions(width, height);
    float2 texelSize = 1.0 / float2(width, height);

    // 1. МЯГКИЙ ГАУСС С НОРМАЛИЗАЦИЕЙ (исправляет баг отбеливания)
    float weights[5] = { 0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216 };
    float4 acc = tex.Sample(s0_s, uv) * weights[0];
    float totalWeight = weights[0];
    
    [unroll]
    for(int i = 1; i < 5; i++)
    {
        float2 offset = texelSize * i * (1.0 + BLUR_POWER);
        float w = weights[i];
        
        acc += tex.Sample(s0_s, uv + float2(offset.x, 0)) * w;
        acc += tex.Sample(s0_s, uv - float2(offset.x, 0)) * w;
        acc += tex.Sample(s0_s, uv + float2(0, offset.y)) * w;
        acc += tex.Sample(s0_s, uv - float2(0, offset.y)) * w;
        
        totalWeight += w * 4.0; 
    }

    float3 color = (acc / totalWeight).rgb;

    // 2. УМНАЯ ЦВЕТОКОРРЕКЦИЯ
    
    // Насыщенность: работаем только если SAT_VAL != 1.0
    if (abs(SAT_VAL - 1.0) > 0.001)
    {
        float luma = dot(color, float3(0.299, 0.587, 0.114));
        color = lerp(luma.xxx, color, SAT_VAL);
    }

    // Отбеливание: работаем только если WHITE_VAL > 0
    // Используем мягкое осветление, чтобы не "выбивать" цвета в чистый белый сразу
    if (WHITE_VAL != 0.0)
    {
        // color += WHITE_VAL; // Грубый метод
        color = 1.0 - (1.0 - color) * (1.0 - WHITE_VAL); // Мягкий метод (Screen)
    }

    result = float4(color, 1.0);
}
#endif