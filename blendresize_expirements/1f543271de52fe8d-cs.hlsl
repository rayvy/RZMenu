cbuffer CB0 : register(b0)
{
    uint4 cb0_params;
}

ByteAddressBuffer t0 : register(t0);

struct OutputData
{
    float4 val;
};
RWStructuredBuffer<OutputData> u0 : register(u0);

Texture1D<float4> IniParams : register(t120);

// --- ПЕРЕНАЗНАЧЕННЫЕ ПАРАМЕТРЫ ИЗ INI ---
#define MOD_ID_LIMIT   IniParams[54].w    // Лимит ID (сколько костей менять)
#define OFFSET_VEC     IniParams[54].xyz  // x54, y54, z54
#define ROT_ANGLES     IniParams[55].xyz  // x55, y55, z55 (уже с учетом времени)
#define RESIZE_COEFF   IniParams[56].x    // x56 (масштаб)

// Вспомогательная функция для создания матрицы поворота
float3x3 GetRotationMatrix(float3 angles)
{
    float3 s, c;
    sincos(angles, s, c); 

    float3x3 rotX = float3x3(
        1, 0, 0,
        0, c.x, -s.x,
        0, s.x, c.x
    );
    float3x3 rotY = float3x3(
        c.y, 0, s.y,
        0, 1, 0,
        -s.y, 0, c.y
    );
    float3x3 rotZ = float3x3(
        c.z, -s.z, 0,
        s.z, c.z, 0,
        0, 0, 1
    );

    // Порядок перемножения: Z * Y * X
    return mul(rotZ, mul(rotY, rotX));
}

[numthreads(128, 1, 1)]
void main(uint3 vThreadID : SV_DispatchThreadID)
{
    float resize_val;
    resize_val = RESIZE_COEFF;
    // Проверка границ потоков
    if (vThreadID.x >= cb0_params.y) return;

    // Определяем, какую строку (0, 1 или 2) матрицы кости обрабатывает этот поток
    int modID;
    // if (vThreadID.x < (uint)MOD_ID_LIMIT) {
    //     modID = vThreadID.x % 3;
    // } else { 
    //     modID = 4; // Пропуск модификации для остальных данных
    // }
    modID = vThreadID.x % 3;
    // Читаем текущую строку
    uint readOffset = (vThreadID.x << 4) + cb0_params.w;
    float4 fData = asfloat(t0.Load4(readOffset));


    // 1. Читаем все три строки матрицы данной кости для правильной трансформации
    uint boneBaseIndex = vThreadID.x - modID; 
    uint baseOffset = (boneBaseIndex << 4) + cb0_params.w;
    
    float4 row0 = asfloat(t0.Load4(baseOffset));      // Row 0 (X axis + Pos X)
    float4 row1 = asfloat(t0.Load4(baseOffset + 16)); // Row 1 (Y axis + Pos Y)
    float4 row2 = asfloat(t0.Load4(baseOffset + 32)); // Row 2 (Z axis + Pos Z)

    // 2. Применяем РЕСАЙЗ (Масштаб) ко всей матрице
    row0 *= resize_val;
    row1 *= resize_val;
    row2 *= resize_val;

    // 3. Создаем матрицу поворота из углов, пришедших из IniParams[55]
    float3x3 rotMat = GetRotationMatrix(ROT_ANGLES);

    // 4. ПРИМЕНЯЕМ ПОВОРОТ (Матричное умножение)
    // Вычисляем новую строку на основе комбинации трех старых строк и матрицы поворота
    float3 R = float3(rotMat[modID][0], rotMat[modID][1], rotMat[modID][2]);
    fData = R.x * row0 + R.y * row1 + R.z * row2;

    // 5. ПРИМЕНЯЕМ ОФФСЕТ (Позиция из IniParams[54])
    // Добавляем соответствующую компоненту смещения к колонке W
    if (modID == 0) fData.w += OFFSET_VEC.x;
    else if (modID == 1) fData.w += OFFSET_VEC.y;
    else if (modID == 2) fData.w += OFFSET_VEC.z;

    // Запись результата в выходной буфер
    uint writeIndex = vThreadID.x + cb0_params.x;
    u0[writeIndex].val = fData;
}