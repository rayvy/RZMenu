// **** CYCLIC ANIMATION SHADER (ENDFIELD ADAPTED) ****

struct VertexAttributes {
    float3 position;
    uint normal; // Упакованная нормаль (не трогаем в расчетах)
};

RWStructuredBuffer<VertexAttributes> rw_buffer : register(u5);
StructuredBuffer<VertexAttributes> base : register(t50);
StructuredBuffer<VertexAttributes> shapekey : register(t51);

Texture1D<float4> IniParams : register(t120);

// FREQ — это накопленное время из ини-файла ($Freq)
#define FREQ IniParams[88].x

[numthreads(1, 1, 1)]
void main(uint3 threadID : SV_DispatchThreadID)
{
    uint i = threadID.x;

    // Вычисляем дельту только для позиции
    float3 diffPos = shapekey[i].position - base[i].position;

    // Вычисляем вес анимации (синусоида от 0 до 1)
    // 0.5 * (sin(...) + 1) превращает диапазон [-1, 1] в [0, 1]
    float weight = 0.5 * (sin(FREQ * 30.0) + 1.0);

    // Применяем смещение к буферу вывода
    rw_buffer[i].position += diffPos * weight;
    
    // ПРИМЕЧАНИЕ: rw_buffer[i].normal не трогаем, 
    // так как это упакованный uint, и обычная математика его испортит.
}