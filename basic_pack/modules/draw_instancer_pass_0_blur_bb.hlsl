Texture1D<float4> IniParams : register(t120);
SamplerState s0_s : register(s0);

static float BlurStrength = IniParams[101].x;

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
Texture2D<float4> tex : register(t92);

void main(vs2ps input, out float4 result : SV_Target0)
{
    uint width, height;
    tex.GetDimensions(width, height);
    
    float2 uv = input.uv;
    float2 texelSize = 1.0 / float2(width, height);
    
    // Регулировка "мыльности"
    // 4.0 - очень мыльно, 8.0 - экстремально
    const float BLUR_SPREAD = BlurStrength; 
    
    float4 acc = 0;
    
    // Используем 16 выборок, разнесенных на большое расстояние
    // Благодаря линейному самплеру, каждая выборка уже сама по себе блюрит 4 пикселя
    float2 offsets[16] = {
        float2(-1.5, -1.5), float2(-0.5, -1.5), float2(0.5, -1.5), float2(1.5, -1.5),
        float2(-1.5, -0.5), float2(-0.5, -0.5), float2(0.5, -0.5), float2(1.5, -0.5),
        float2(-1.5,  0.5), float2(-0.5,  0.5), float2(0.5,  0.5), float2(1.5,  0.5),
        float2(-1.5,  1.5), float2(-0.5,  1.5), float2(0.5,  1.5), float2(1.5,  1.5)
    };

    [unroll]
    for(int i = 0; i < 16; i++)
    {
        // Умножаем смещение на SPREAD, чтобы разнести выборки подальше
        acc += tex.Sample(s0_s, uv + offsets[i] * texelSize * BLUR_SPREAD);
    }

    result = acc / 16.0;
    result.a = 1.0;
}
#endif