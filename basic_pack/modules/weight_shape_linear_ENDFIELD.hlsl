struct VertexAttributes {
    uint2 weights; // 4x16-bit UNORM (8 bytes)
    uint indices;  // 4x8-bit UINT (4 bytes)
};

RWStructuredBuffer<VertexAttributes> rw_buffer : register(u5);
StructuredBuffer<VertexAttributes> base : register(t50);
StructuredBuffer<VertexAttributes> shapekey : register(t51);

Texture1D<float4> IniParams : register(t120);
#define key IniParams[88].x

struct BoneEntry {
    uint index;
    float weight;
};

void AddToPool(uint idx, float w, inout BoneEntry pool[12], inout int size) {
    if (abs(w) < 0.000001f) return;
    for (int i = 0; i < size; i++) {
        if (pool[i].index == idx) {
            pool[i].weight += w;
            return;
        }
    }
    if (size < 12) {
        pool[size].index = idx;
        pool[size].weight = w;
        size++;
    }
}

[numthreads(1024, 1, 1)]
void main(uint3 threadID : SV_DispatchThreadID)
{
    uint i = threadID.x;
    uint vertex_count, stride;
    rw_buffer.GetDimensions(vertex_count, stride);
    if (i >= vertex_count) return;

    BoneEntry pool[12];
    for (int k_init = 0; k_init < 12; k_init++) {
        pool[k_init].index = 0;
        pool[k_init].weight = 0.0f;
    }
    int poolSize = 0;

    // 1. Извлекаем текущее состояние из RW буфера (результат предыдущих шейпкеев)
    uint2 curW = rw_buffer[i].weights;
    uint curI = rw_buffer[i].indices;
    AddToPool(curI & 0xFF,         (float(curW.x & 0xFFFF) / 65535.0f), pool, poolSize);
    AddToPool((curI >> 8) & 0xFF,  (float(curW.x >> 16) / 65535.0f),    pool, poolSize);
    AddToPool((curI >> 16) & 0xFF, (float(curW.y & 0xFFFF) / 65535.0f), pool, poolSize);
    AddToPool((curI >> 24) & 0xFF, (float(curW.y >> 16) / 65535.0f),    pool, poolSize);

    // 2. Извлекаем Базис (нужен для вычисления дельты)
    uint2 basW = base[i].weights;
    uint basI = base[i].indices;
    // Отрицательный вклад базиса: -Base * Key
    AddToPool(basI & 0xFF,         -(float(basW.x & 0xFFFF) / 65535.0f) * key, pool, poolSize);
    AddToPool((basI >> 8) & 0xFF,  -(float(basW.x >> 16) / 65535.0f) * key,    pool, poolSize);
    AddToPool((basI >> 16) & 0xFF, -(float(basW.y & 0xFFFF) / 65535.0f) * key, pool, poolSize);
    AddToPool((basI >> 24) & 0xFF, -(float(basW.y >> 16) / 65535.0f) * key,    pool, poolSize);

    // 3. Извлекаем Целевой шейпкей (Target)
    uint2 shpW = shapekey[i].weights;
    uint shpI = shapekey[i].indices;
    // Положительный вклад шейпкея: +Target * Key
    AddToPool(shpI & 0xFF,         (float(shpW.x & 0xFFFF) / 65535.0f) * key, pool, poolSize);
    AddToPool((shpI >> 8) & 0xFF,  (float(shpW.x >> 16) / 65535.0f) * key,    pool, poolSize);
    AddToPool((shpI >> 16) & 0xFF, (float(shpW.y & 0xFFFF) / 65535.0f) * key, pool, poolSize);
    AddToPool((shpI >> 24) & 0xFF, (float(shpW.y >> 16) / 65535.0f) * key,    pool, poolSize);

    // Очищаем шум и микро-отрицательные значения после вычитания дельты
    for (int m_clamp = 0; m_clamp < poolSize; m_clamp++) {
        pool[m_clamp].weight = max(0.0f, pool[m_clamp].weight);
    }

    // 4. Выборка ТОП-4 костей по весам (Runtime Selection)
    uint outIndices[4] = {0, 0, 0, 0};
    float outWeights[4] = {0, 0, 0, 0};

    for (int n_top = 0; n_top < 4; n_top++) {
        int maxIdx = -1;
        float maxW = -1.0f;
        for (int k_pool = 0; k_pool < poolSize; k_pool++) {
            if (pool[k_pool].weight > maxW) {
                maxW = pool[k_pool].weight;
                maxIdx = k_pool;
            }
        }
        if (maxIdx != -1) {
            outIndices[n_top] = pool[maxIdx].index;
            outWeights[n_top] = pool[maxIdx].weight;
            pool[maxIdx].weight = -2.0f; // Помечаем как использованную
        }
    }

    // 5. Финальная нормализация (Runtime Normalization)
    float sum = outWeights[0] + outWeights[1] + outWeights[2] + outWeights[3];
    if (sum > 0.00001f) {
        float invSum = 1.0f / sum;
        outWeights[0] *= invSum;
        outWeights[1] *= invSum;
        outWeights[2] *= invSum;
        outWeights[3] *= invSum;
    } else {
        // Фоллбэк: если веса обнулились, берем первую кость из базиса
        outIndices[0] = basI & 0xFF;
        outWeights[0] = 1.0f;
    }

    // 6. Упаковка обратно в 12-байтовую структуру EFMI (Weights R16_UNORM, Indices R8_UINT)
    uint2 finalW;
    finalW.x = (uint(outWeights[0] * 65535.0f + 0.5f)) | (uint(outWeights[1] * 65535.0f + 0.5f) << 16);
    finalW.y = (uint(outWeights[2] * 65535.0f + 0.5f)) | (uint(outWeights[3] * 65535.0f + 0.5f) << 16);
    uint finalI = (outIndices[0] & 0xFF) | ((outIndices[1] & 0xFF) << 8) | ((outIndices[2] & 0xFF) << 16) | ((outIndices[3] & 0xFF) << 24);

    rw_buffer[i].weights = finalW;
    rw_buffer[i].indices = finalI;
}
