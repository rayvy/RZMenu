// **** THANOS SNAP V2: WAVE DEFORMATION + FINE NaN CHEESE ****

struct VertexAttributes {
    float3 position;
    uint normal; 
};

RWStructuredBuffer<VertexAttributes> rw_buffer : register(u5);
StructuredBuffer<VertexAttributes> base : register(t50);
StructuredBuffer<VertexAttributes> shapekey : register(t51);

Texture1D<float4> IniParams : register(t120);

// Накопленное время
#define FREQ IniParams[88].x

// **** CINEMATIC THANOS SNAP (SMOOTH GRADIENT & TINY GRAINS) ****

float hash(float3 p) {
    p = frac(p * 0.3183099 + 0.1); p *= 17.0;
    return frac(p.x * p.y * p.z * (p.x + p.y + p.z));
}
float noise(float3 x) {
    float3 i = floor(x); float3 f = frac(x);
    f = f * f * (3.0 - 2.0 * f);
    return lerp(lerp(lerp(hash(i), hash(i+float3(1,0,0)), f.x),
                     lerp(hash(i+float3(0,1,0)), hash(i+float3(1,1,0)), f.x), f.y),
                lerp(lerp(hash(i+float3(0,0,1)), hash(i+float3(1,0,1)), f.x),
                     lerp(hash(i+float3(0,1,1)), hash(i+float3(1,1,1)), f.x), f.y), f.z);
}

// **** STRICT VERTICAL CYBER GLITCH ****

// **** FINALE 1: LIQUID METAL MELT ****

float noise2D(float2 p) {
    float2 i = floor(p); float2 f = frac(p);
    f = f * f * (3.0 - 2.0 * f);
    return lerp(lerp(frac(sin(dot(i + float2(0,0), float2(12.9898, 78.233))) * 43758.5453),
                     frac(sin(dot(i + float2(1,0), float2(12.9898, 78.233))) * 43758.5453), f.x),
                lerp(frac(sin(dot(i + float2(0,1), float2(12.9898, 78.233))) * 43758.5453),
                     frac(sin(dot(i + float2(1,1), float2(12.9898, 78.233))) * 43758.5453), f.x), f.y);
}

[numthreads(1, 1, 1)]
void main(uint3 threadID : SV_DispatchThreadID) {
    uint i = threadID.x;
    float3 basePos = base[i].position;
    float3 pos = basePos + (shapekey[i].position - basePos) * 0.5 * (sin(FREQ * 30.0) + 1.0);

    // Волна плавления идет СВЕРХУ ВНИЗ (от 2.5 до -0.5)
    float globalProgress = 0.5 * (sin(FREQ * 1.5) + 1.0);
    float meltLine = 2.5 - (globalProgress * 3.0);

    // Размер кусков (крупные капли воска)
    float chunkSize = 0.05;
    float3 chunkCenter = floor(basePos / chunkSize) * chunkSize;

    // Насколько глубоко точка ушла под линию плавления
    float meltAmount = meltLine - chunkCenter.y;

    if (meltAmount < 0.0) {
        // --- Точка расплавилась ---
        
        // АНТИ-ЖВАЧКА: Отрезаем расплавленное от твердого
        float distToCenter = length(basePos - (chunkCenter + chunkSize * 0.5));
        if (distToCenter > chunkSize * 0.45) {
            pos = asfloat(0x7FC00000).xxx; 
        } 
        else {
            // ЛОГИКА ПЛАВЛЕНИЯ
            float3 localPos = pos - chunkCenter;
            
            // 1. Падение вниз (гравитация). Ограничиваем уровень пола, например Y = 0.0
            float floorLevel = 0.0;
            float fallProgress = saturate(-meltAmount * 2.0); // от 0 (начал падать) до 1 (на полу)
            
            // Плавное падение кубика
            float3 newCenter = chunkCenter;
            newCenter.y = lerp(chunkCenter.y, floorLevel, fallProgress);

            // 2. Растекание лужи
            if (fallProgress > 0.99) {
                // Как только коснулся пола - растекается в стороны
                float puddleTime = -meltAmount - 0.5; // Время после удара об пол
                
                // Вектор растекания от центра тела (0,0) наружу
                float2 spreadDir = normalize(newCenter.xz + 0.001); 
                
                // Неровность лужи (шум)
                float n = noise2D(newCenter.xz * 10.0);
                
                // Растекается со временем
                newCenter.xz += spreadDir * puddleTime * (1.0 + n * 2.0);
                
                // Сплющиваем кубик в блинчик, чтобы лужа была плоской
                localPos.y *= max(0.01, 1.0 - puddleTime * 2.0);
            }

            pos = newCenter + localPos;
        }
    }

    rw_buffer[i].position = pos;
}