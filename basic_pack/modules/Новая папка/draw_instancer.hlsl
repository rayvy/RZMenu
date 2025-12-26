// code writed > Rayvich
// Shader Base > Sinsofseven

Texture1D<float4> IniParams : register(t120);
#define CURSOR     IniParams[90].xy
#define SCREEN_RES IniParams[90].zw
Buffer<float4> PosSizeBuffer    : register(t87);
Buffer<float4> TileDataBuffer   : register(t88);
Buffer<float4> DrawParamsBuffer : register(t89);
Texture2D<float4> tex_violet : register(t97);
Texture2D<float4> tex_red : register(t98);
Texture2D<float4> tex_black : register(t99);
Texture2D<float4> tex100 : register(t100);
Texture2D<float4> tex101 : register(t101);
Texture2D<float4> tex102 : register(t102);
Texture2D<float4> tex103 : register(t103);
Texture2D<float4> tex104 : register(t104);
Texture2D<float4> tex105 : register(t105);
Texture2D<float4> tex106 : register(t106);
Texture2D<float4> tex107 : register(t107);
Texture2D<float4> tex108 : register(t108);
Texture2D<float4> tex_backbuffer : register(t109);
Texture2D<float4> tex110 : register(t110);
SamplerState s0_s : register(s0);

float easyIN(float x, float y, float z) {
    // Линейная интерполяция с замедлением в начале
    float t = x * x;
    return lerp(y, z, t);
}

float easyOUT(float x, float y, float z) {
    // Линейная интерполяция с замедлением в конце
    float t = 1 - (1 - x) * (1 - x);
    return lerp(y, z, t);
}

float overshoot(float x, float y, float z) {
    // Overshoot: небольшой пик, затем возврат к z
    float peak = z * 0.95; // Максимальное значение "прыжка"
    if (x < 0.5) {
        // Первая половина кривой (подъем)
        float t = 2 * x;
        return lerp(y, peak, t * t); // Легкий скачок вверх
    } else {
        // Вторая половина кривой (возврат)
        float t = 2 * (x - 0.5);
        return lerp(peak, z, t * t); // Спад обратно к конечному значению
    }
}

struct vs2ps {
    float4 pos       : SV_Position;
    float2 uv        : TEXCOORD0;
    float  draw_type : TEXCOORD1;
    float  tex_type : TEXCOORD2;
};
#ifdef VERTEX_SHADER
void main(out vs2ps output, uint vertex_id : SV_VertexID, uint instance_id : SV_InstanceID)
{
    float4 pos_size    = PosSizeBuffer[instance_id];
    float4 tile_data   = TileDataBuffer[instance_id];
    float4 draw_params = DrawParamsBuffer[instance_id];

    float2 final_pos  = pos_size.xy;
    float2 final_size = pos_size.zw;
    
    // ... (логика для draw_params.x == 9 и 8 остается без изменений) ...
    if (draw_params.x == 9) 
    {
        float2 CursorPos = CURSOR;
        float2 IconCenter = final_pos + final_size * 0.5;
        float DetectionRadius = 0.20;
        float Distance = length(IconCenter - CursorPos);
        float Proximity = saturate(1.0 - (Distance / DetectionRadius));
        float IntensityFactor = 10;
        Proximity = pow(Proximity, IntensityFactor);
        float ScaleFactor = 1.0 + Proximity * 0.33;
        float2 original_size = final_size;
        final_size *= ScaleFactor;
        final_pos -= (final_size - original_size) * 0.5;
    }
    if (draw_params.x == 8) 
    {
        float2 CursorPos = CURSOR;
        float2 IconCenter = final_pos + final_size * 0.5;
        float DetectionRadius = 0.2;
        float IntensityFactor = 0.25;
        float FinalFactor = 0.0025;
        float Distance = length(IconCenter - CursorPos);
        float Proximity = saturate(1.0 - (Distance / DetectionRadius));
        Proximity = pow(Proximity, IntensityFactor);
        float2 Direction = normalize(IconCenter - CursorPos);
        float DeviationStrength = Proximity * FinalFactor;
        final_pos += Direction * DeviationStrength;
    }

    float2 screen_pos;
    switch (vertex_id) {
        case 0: screen_pos = float2(0.0, 1.0); break;
        case 1: screen_pos = float2(1.0, 1.0); break;
        case 2: screen_pos = float2(0.0, 0.0); break;
        case 3: screen_pos = float2(1.0, 0.0); break;
        default: screen_pos = float2(0,0); break;
    }
    output.pos.xy = (final_pos + screen_pos * final_size) * 2.0 - 1.0;
    output.pos.zw = float2(0.5, 1.0);
    float2 tile_idx_to_use;
    float2 total_tiles_to_use = tile_data.zw;
    if (total_tiles_to_use.x == 0) total_tiles_to_use.x = 1;
    if (total_tiles_to_use.y == 0) total_tiles_to_use.y = 1;
    if (draw_params.x == 1)
    {
        float displayValue = round(tile_data.x);
        float max_tile_number = total_tiles_to_use.x * total_tiles_to_use.y - 1.0;
        displayValue = clamp(displayValue, 0.0, max_tile_number);
        float tileX = fmod(displayValue, total_tiles_to_use.x);
        float tileY = floor(displayValue / total_tiles_to_use.x);
        tile_idx_to_use = float2(tileX, tileY);
    }
    else
    {
        tile_idx_to_use = tile_data.xy;
    }

    // --- НАЧАЛО ИЗМЕНЕНИЯ: ИСПРАВЛЕНИЕ "ПРОСАЧИВАНИЯ" ТЕКСТУР ---
    
    // 1. Рассчитываем размер одного тайла в UV-координатах
    float2 tile_size_uv = 1.0 / total_tiles_to_use;
    
    // 2. Определяем "пиксельный отступ" (половина текселя). Это самая важная часть.
    // Мы берем размер одного тайла и делим на его примерное разрешение (например, 64 пикселя).
    // Если ваши тайлы другого размера, можете поменять 64.0 на 32.0, 128.0 и т.д.
    // Это создает крошечный отступ, чтобы не задевать соседей.
    float2 pixel_inset = tile_size_uv / 64.0; 

    // 3. Смещаем начальную точку UV внутрь на этот отступ
    float2 corrected_tile_idx = float2(tile_idx_to_use.x, total_tiles_to_use.y - tile_idx_to_use.y - 1);
    float2 tile_start_uv = corrected_tile_idx * tile_size_uv + pixel_inset;
    
    // 4. Уменьшаем размер области сэмплирования на два отступа (с каждой стороны)
    float2 uv_area_size = tile_size_uv - (pixel_inset * 2.0);

    // 5. Вычисляем итоговые UV, используя новые, "безопасные" значения
    output.uv = tile_start_uv + screen_pos * uv_area_size;

    // --- КОНЕЦ ИЗМЕНЕНИЯ ---

    if(draw_params.x == 90) {
        switch (vertex_id) {
            case 0: output.uv = float2(pos_size.x + pos_size.z * 0.0, 1.0 - pos_size.y - pos_size.w * 1.0); break;
            case 1: output.uv = float2(pos_size.x + pos_size.z * 1.0, 1.0 - pos_size.y - pos_size.w * 1.0); break;
            case 2: output.uv = float2(pos_size.x + pos_size.z * 0.0, 1.0 - pos_size.y - pos_size.w * 0.0); break;
            case 3: output.uv = float2(pos_size.x + pos_size.z * 1.0, 1.0 - pos_size.y - pos_size.w * 0.0); break;
            default: output.uv = float2(0, 0); break;
        }
    }
    output.draw_type = draw_params.x;
    output.tex_type = draw_params.y;
}
#endif
#ifdef PIXEL_SHADER
void main(vs2ps input, out float4 result : SV_Target0)
{
    input.uv.y = 1 - input.uv.y;
    
    switch ((int)input.tex_type)
    {
        default: result = tex_violet.Sample(s0_s, input.uv); break;
        case 97: result = tex_violet.Sample(s0_s, input.uv); break;
        case 98: result = float4(1,0,0,1.0); break;
        case 99: result = tex_black.Sample(s0_s, input.uv); break;
        case 100: result = tex100.Sample(s0_s, input.uv); break;
        case 101: result = tex101.Sample(s0_s, input.uv); break;
        case 102: result = tex102.Sample(s0_s, input.uv); break;
        case 103: result = tex103.Sample(s0_s, input.uv); break;
        case 104: result = tex104.Sample(s0_s, input.uv); break;
        case 105: result = tex105.Sample(s0_s, input.uv); break;
        case 106: result = tex106.Sample(s0_s, input.uv); break;
        case 107: result = tex107.Sample(s0_s, input.uv); break;
        case 108: result = tex108.Sample(s0_s, input.uv); break;
        case 110: result = tex110.Sample(s0_s, input.uv); break;
    }

    switch ((int)input.draw_type)
    {
        case 0:
        {
            break;
        }
        case 1:
        {
            break;
        }
        case 2:
        {
            result.rgb *= 1.5;
            break;
        }
        case 8:
            result.r *= 1;
            result.gb *= 0;
            break;
        case 90:
        {
            input.uv.y = 1 - input.uv.y;
            float4 sumColor = float4(0, 0, 0, 0);
            const int BlurRadius = 4;
            const float2 TexelSize = (1.0 / SCREEN_RES.xy)*1.5;
            int numSamples = (BlurRadius * 2 + 1) * (BlurRadius * 2 + 1);
            for (int y = -BlurRadius; y <= BlurRadius; ++y) {
                for (int x = -BlurRadius; x <= BlurRadius; ++x) {
                    sumColor += tex_backbuffer.Sample(s0_s, input.uv + float2(x, y) * TexelSize);
                }
            }
            result = sumColor / numSamples;
            result.xyz *= 0.5;
            result.w = 1;
            break;
        }
        default:
        {
            break;
        }
    }
}
#endif