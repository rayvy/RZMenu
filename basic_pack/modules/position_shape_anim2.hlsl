struct VertexAttributes {
    float3 position;
    float3 normal;
    float4 tangent;
};

RWStructuredBuffer<VertexAttributes> rw_buffer : register(u5);
StructuredBuffer<VertexAttributes> base : register(t50);
StructuredBuffer<VertexAttributes> shapekey : register(t51);

Texture1D<float4> IniParams : register(t120);

#define PI 3.14159265

//================================================================================
// --- НАСТРОЙКА СКОРОСТИ ---
// 2.5 - значение, которое тебе подошло. Меняй по необходимости.
#define GLOBAL_SPEED_MULTIPLIER 10.0
//================================================================================

[numthreads(1, 1, 1)]
void main(uint3 threadID : SV_DispatchThreadID) 
{
    // --- 1. Получаем все параметры ---
    float input_phase = IniParams[88].x;
    int anim_type = (int)IniParams[88].y; 
    float start_time = IniParams[88].z;
    float end_time = IniParams[88].w;

    // --- НОВОЕ: Проверка на отрицательный anim_type ---
    // Если anim_type < 0, то игнорируем z88 и w88 и используем полный цикл
    if (anim_type < 0)
    {
        start_time = 0.0;
        end_time = 1.0;
    }

    // --- 2. Глобальный таймер с учетом скорости ---
    float global_time = frac(input_phase * GLOBAL_SPEED_MULTIPLIER);
    
    float weight = 0.0;

    // --- 3. Проверяем "окно активности" ---
    float duration = end_time - start_time;
    if (duration > 0.0 && global_time >= start_time && global_time <= end_time)
    {
        // --- 4. Вычисляем локальный прогресс (0.0 -> 1.0) ---
        float local_progress = (global_time - start_time) / duration;

        // --- 5. ВЫБОР ТИПА АНИМАЦИИ ---
        switch (anim_type)
        {
            // --- НОВОЕ: Case 200: Линейная анимация с удвоенной силой ---
            case 200:
            {
                float linear_weight;
                if (local_progress < 0.5)
                {
                    // Линейный рост от 0.0 до 1.0 на первой половине
                    linear_weight = local_progress * 2.0;
                }
                else
                {
                    // Линейный спад от 1.0 до 0.0 на второй половине
                    linear_weight = 1.0 - (local_progress - 0.5) * 2.0;
                }
                
                // Умножаем результат на 2 для удвоения импакта
                weight = linear_weight * 2.0;
                break;
            }

            // --- Case 1: Эффект "Молотка" ---
            case 1:
            {
                float hold_start = 0.2;
                float hold_end = 0.5;

                if (local_progress < hold_start)
                {
                    weight = sin((local_progress / hold_start) * PI / 2.0);
                }
                else if (local_progress <= hold_end)
                {
                    weight = 1.0;
                }
                else
                {
                    weight = cos(((local_progress - hold_end) / (1.0 - hold_end)) * PI / 2.0);
                }
                break;
            }

            // --- Case 0 (и все остальные, включая отрицательные): Стандартная синусоида ---
            case 0:
            default:
            {
                weight = sin(local_progress * PI);
                break;
            }
        }
    }

    // --- 6. Применяем шейп ---
    if (weight > 0.001)
    {
        uint i = threadID.x;
        VertexAttributes diff;
        diff.position = shapekey[i].position - base[i].position;
        diff.normal = shapekey[i].normal - base[i].normal;
        diff.tangent = shapekey[i].tangent - base[i].tangent;

        rw_buffer[i].position += diff.position * weight;
        rw_buffer[i].normal += diff.normal * weight;
        rw_buffer[i].tangent += diff.tangent * weight;
    }
}