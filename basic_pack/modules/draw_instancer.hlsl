Texture1D<float4> IniParams : register(t120);
#define SCREEN_RES IniParams[99].zw
#define CURSOR_POS IniParams[99].xy
#define time IniParams[98].w

Buffer<float4> PosSizeDataBuffer    : register(t100);
Buffer<float4> ColorDataBuffer      : register(t101);
Buffer<float4> TileDataBuffer       : register(t102); 
Buffer<uint>   TextPoolBuffer       : register(t103);
Buffer<float4> ClippingDataBuffer   : register(t109);
Buffer<float4> DrawParamsBuffer     : register(t110);
Texture2D<float4> tex_atlas_icons   : register(t80);
Texture2D<float4> tex_atlas_font    : register(t82);
Texture2D<float4> tex_backbuffer    : register(t89);
SamplerState s0_s : register(s0);

#define DRAW_MODE_SOLID                 0
#define DRAW_MODE_TEXTURE_OVERLAY       1
#define DRAW_MODE_TEXTURE_MULTIPLY      2
#define DRAW_MODE_TEXT                  3
#define DRAW_MODE_NUMBER                4
#define DRAW_MODE_BLUR_BACKGROUND_START 90
#define DRAW_MODE_BLUR_BACKGROUND_END   99

#define FN_ROTATE         1
#define FN_HOVER_TURN     2

#define FX_HOVER_OUTLINE_INWARD 1
#define FX_OUTLINE        2
#define FX_HOVER_SHEEN    3
#define FX_HOVER_RESIZE   4
#define FX_BLUR           9
#define FX_HOVER_SHINE    8

#define MAX_CHARS_PER_INSTANCE 32
#define MAX_CHARS_PER_NUMBER   32 
#define CELL_GRID_HEIGHT 6 
struct vs2ps {
    float4 pos             : SV_Position;
    float4 color           : COLOR0;
    float2 uv              : TEXCOORD0;
    float2 local_uv        : TEXCOORD1; // <--- ДОБАВИТЬ ЭТУ СТРОКУ
    float  fn_type         : TEXCOORD2;
    float  fx_type         : TEXCOORD3;
    int    draw_mode       : TEXCOORD4;
    float4 object_pos_size : TEXCOORD5;
    float4 clip_rect       : TEXCOORD6;
};

#ifdef VERTEX_SHADER

//--------------------------------------------------------------------------------------
// Структура и функция чтения метрик
//--------------------------------------------------------------------------------------
struct CharMetrics {
    float advance;      
    float glyphWidth;   
    float glyphHeight;
    float offsetX;      
    float offsetY;      
};

CharMetrics get_char_metrics(uint c) {
    CharMetrics metrics = (CharMetrics)0;
    
    if (c < 32 || c >= 127) c = 32;

    uint atlas_width, atlas_height;
    tex_atlas_font.GetDimensions(atlas_width, atlas_height);
    if (atlas_width == 0) return metrics;

    const uint BASE_CELL_SIZE = 16;
    uint scale = atlas_width / (BASE_CELL_SIZE * 16);
    if (scale < 1) scale = 1;
    float cell_size_px = (float)(BASE_CELL_SIZE * scale);

    // Координаты пикселя с метаданными
    uint char_index = c - 32;
    uint metadata_grid_height = atlas_height / cell_size_px - CELL_GRID_HEIGHT; 
    uint metadata_start_y = (atlas_height / cell_size_px - metadata_grid_height) * cell_size_px;
    
    uint meta_x = char_index % atlas_width;
    uint meta_y = metadata_start_y + (char_index / atlas_width) * 2;

    float4 encoded_metrics1 = tex_atlas_font.Load(int3(meta_x, meta_y, 0));
    float4 encoded_metrics2 = tex_atlas_font.Load(int3(meta_x, meta_y + 1, 0));
    
    metrics.advance     = (encoded_metrics1.r * 2.0) * cell_size_px;
    metrics.glyphWidth  = (encoded_metrics1.g * 2.0) * cell_size_px;
    metrics.offsetX     = ((encoded_metrics1.b * 2.0) - 1.0) * cell_size_px;
    metrics.offsetY     = ((encoded_metrics1.a * 2.0) - 1.0) * cell_size_px;
    metrics.glyphHeight = (encoded_metrics2.r * 2.0) * cell_size_px; 

    return metrics;
}
float2 GetTextureUV(int draw_mode, float2 local_quad_uv, float4 tile_data, uint vertex_id, inout float2 final_pos, inout float2 final_size)
{
    if (draw_mode >= DRAW_MODE_BLUR_BACKGROUND_START && draw_mode <= DRAW_MODE_BLUR_BACKGROUND_END) {
        return float2(final_pos.x + local_quad_uv.x * final_size.x, 1.0 - (final_pos.y + local_quad_uv.y * final_size.y));
    }
    
    switch(draw_mode) {
        case DRAW_MODE_TEXTURE_OVERLAY:
        case DRAW_MODE_TEXTURE_MULTIPLY: {
            uint texWidth, texHeight; tex_atlas_icons.GetDimensions(texWidth, texHeight);
            float2 atlas_size = float2(max(1, texWidth), max(1, texHeight));
            return (tile_data.xy + local_quad_uv * tile_data.zw) / atlas_size;
        }
        case DRAW_MODE_TEXT:
        case DRAW_MODE_NUMBER: {
            uint char_codes[MAX_CHARS_PER_INSTANCE];
            uint num_chars = 0;
            if (draw_mode == DRAW_MODE_TEXT) {
                uint string_start_offset = (uint)tile_data.x;
                num_chars = min((uint)tile_data.y, MAX_CHARS_PER_INSTANCE);
                for (uint i = 0; i < num_chars; ++i) char_codes[i] = TextPoolBuffer[string_start_offset + i];
            } else {
                float raw_val=tile_data.x;int precision=clamp((int)tile_data.y,0,9);float p10=1.0;for(int p=0;p<precision;p++)p10*=10.0;float val=round(raw_val*p10)/p10;if(val<0.0){if(num_chars<MAX_CHARS_PER_NUMBER)char_codes[num_chars++]='-';val=-val;}val+=1e-7;uint ip=(uint)val;if(ip==0){if(num_chars<MAX_CHARS_PER_NUMBER)char_codes[num_chars++]='0';}else{uint tip=ip;uint id[10];uint nid=0;while(tip>0&&nid<10){id[nid++]=tip%10;tip/=10;}for(uint i=0;i<nid;++i){if(num_chars<MAX_CHARS_PER_NUMBER)char_codes[num_chars++]='0'+id[nid-1-i];}}if(precision>0){if(num_chars<MAX_CHARS_PER_NUMBER)char_codes[num_chars++]='.';float fp=val-(float)ip;for(int i=0;i<precision;++i){fp*=10.0f;uint d=(uint)fp;if(d>9)d=9;if(num_chars<MAX_CHARS_PER_NUMBER)char_codes[num_chars++]='0'+d;fp-=(float)d;}}
            }
            float2 base_pos = final_pos;
            
            uint atlas_width, atlas_height; 
            tex_atlas_font.GetDimensions(atlas_width, atlas_height);
            float cell_size_px = (float)(atlas_width / 16);
            float desired_line_height = final_size.y * SCREEN_RES.y;
            float final_scale = desired_line_height / cell_size_px;

            CharMetrics reference_metrics = get_char_metrics('A');
            float reference_drop = reference_metrics.offsetY + reference_metrics.glyphHeight;

            int alignment = (int)tile_data.z;
            if (alignment > 0)
            {
                if (num_chars > 0)
                {
                    // --- ШАГ 1: Находим левую границу видимого текста ---
                    // Это просто смещение самого первого символа.
                    CharMetrics first_char_metrics = get_char_metrics(char_codes[0]);
                    float min_x_px = first_char_metrics.offsetX;

                    // --- ШАГ 2: Находим правую границу видимого текста ---
                    // Этот блок кода УЖЕ РАБОТАЕТ у вас корректно, так как правое выравнивание работает.
                    float advance_to_last_char_px = 0;
                    for (uint i = 0; i < num_chars - 1; ++i)
                    {
                        advance_to_last_char_px += get_char_metrics(char_codes[i]).advance;
                    }
                    CharMetrics last_char_metrics = get_char_metrics(char_codes[num_chars - 1]);
                    float max_x_px = advance_to_last_char_px + last_char_metrics.offsetX + last_char_metrics.glyphWidth;

                    // --- ШАГ 3: Вычисляем необходимое смещение для выравнивания ---
                    float shift_px = 0;
                    if (alignment == 1) // --- ЦЕНТРИРОВАНИЕ (НОВАЯ ЛОГИКА) ---
                    {
                        // Чтобы отцентрировать, мы должны сдвинуть текст влево на величину,
                        // равную координате его истинного геометрического центра.
                        // Центр = (левая_граница + правая_граница) / 2
                        shift_px = (min_x_px + max_x_px) / 2.0f;
                    }
                    else if (alignment == 2) // --- ПО ПРАВОМУ КРАЮ (ВАША РАБОЧАЯ ЛОГИКА) ---
                    {
                        // Чтобы выровнять по правому краю, мы сдвигаем на всю длину до правой границы.
                        shift_px = max_x_px;
                    }

                    // --- ШАГ 4: Применяем смещение к позиции ---
                    base_pos.x -= (shift_px / SCREEN_RES.x) * final_scale;
                }
            }

            uint char_index = vertex_id / 6;
            uint current_char_code = (char_index < num_chars) ? char_codes[char_index] : ' ';

            float cursor_offset_x = 0;
            for (uint i = 0; i < char_index; ++i) cursor_offset_x += get_char_metrics(char_codes[i]).advance;
            
            CharMetrics metrics = get_char_metrics(current_char_code);
            
            // <--- ИЗМЕНЕНО: Финальная формула с коррекцией по эталону 'A'
            float current_drop = metrics.offsetY + metrics.glyphHeight;
            final_pos.y = base_pos.y + (((reference_drop+(128/7.5)) - current_drop) / SCREEN_RES.y) * final_scale;

            final_pos.x = base_pos.x + ((cursor_offset_x + metrics.offsetX) / SCREEN_RES.x) * final_scale;
            final_size.x = (metrics.glyphWidth / SCREEN_RES.x) * final_scale;
            final_size.y = (metrics.glyphHeight / SCREEN_RES.y) * final_scale;

            // UV-вычисления остаются без изменений
            uint grid_x = (current_char_code - 32) % 16;
            uint grid_y = (current_char_code - 32) / 16;
            
            float2 uv_cell_size = 1.0 / float2(16.0, (float)(atlas_height / cell_size_px));
            float2 uv_start_pos = float2(grid_x, grid_y) * uv_cell_size;
            float2 uv_offset = float2(metrics.offsetX, metrics.offsetY) / cell_size_px * uv_cell_size;
            float2 uv_size = float2(metrics.glyphWidth, metrics.glyphHeight) / cell_size_px * uv_cell_size;

            return uv_start_pos + uv_offset + local_quad_uv * uv_size;
        }
    }
    return local_quad_uv;
}


// ... Остальная часть вертексного шейдера (CalculateVertexPosition, main) БЕЗ ИЗМЕНЕНИЙ ...
float2 CalculateVertexPosition(float fn_type, float2 final_pos, float2 final_size, float2 local_quad_uv)
{
    // --- FIX for warning X4000: Initialize a return value and use a single return point.
    float2 calculated_pos = final_pos + local_quad_uv * final_size;

    if (fn_type == FN_HOVER_TURN) {
        float2 local_model_pos = local_quad_uv - 0.5;
        float2 object_center = final_pos + final_size * 0.5;
        float2 direction = CURSOR_POS - object_center;
        direction.y *= SCREEN_RES.y / SCREEN_RES.x;
        const float MAX_DIST = 0.15; 
        float intensity = saturate(1.0 - length(direction) / MAX_DIST);
        intensity = pow(intensity, 2);
        if (length(direction) > 0.001) {
            direction = normalize(direction);
        }
        const float perspective_strength = 0.4;
        float perspective_offset = dot(local_model_pos, direction);
        local_model_pos -= direction * perspective_offset * intensity * perspective_strength;
        calculated_pos = (local_model_pos * final_size) + object_center;
    }
    else if (fn_type == FN_ROTATE) {
        float2 local_model_pos = local_quad_uv - 0.5;
        float angle = 2.0 * 3.14159265 * time;
        float s = sin(angle);
        float c = cos(angle);
        float2x2 rot_matrix = float2x2(c, -s, s, c);
        float2 rotated_local_pos = mul(rot_matrix, local_model_pos);
        float2 scaled_pos = rotated_local_pos * final_size;
        float2 center = final_pos + final_size * 0.5;
        calculated_pos = scaled_pos + center;
    }
    
    return calculated_pos;
}

void main(out vs2ps output, uint vertex_id : SV_VertexID, uint instance_id : SV_InstanceID)
{
    // --- FIX for warning X3578: Initialize the entire output structure to zero.
    output = (vs2ps)0;

    output.draw_mode = (int)DrawParamsBuffer[instance_id].w;
    
    // Отсечение лишних вертексов
    if (output.draw_mode != DRAW_MODE_TEXT && output.draw_mode != DRAW_MODE_NUMBER && vertex_id >= 6) { output.pos = float4(2,2,0,1); return; }
    if (output.draw_mode == DRAW_MODE_TEXT) { uint num_chars = (uint)TileDataBuffer[instance_id].y; if ((vertex_id / 6) >= min(num_chars, (uint)MAX_CHARS_PER_INSTANCE)) { output.pos = float4(2,2,0,1); return; } }
    if (output.draw_mode == DRAW_MODE_NUMBER) { if ((vertex_id / 6) >= (uint)MAX_CHARS_PER_NUMBER) { output.pos = float4(2,2,0,1); return; } }

    output.clip_rect = ClippingDataBuffer[instance_id];
    output.color   = ColorDataBuffer[instance_id];
    output.fn_type = DrawParamsBuffer[instance_id].x;
    output.fx_type = DrawParamsBuffer[instance_id].y;
    
    float2 final_pos  = PosSizeDataBuffer[instance_id].xy;
    float2 final_size = PosSizeDataBuffer[instance_id].zw;

    if (output.fx_type == FX_HOVER_RESIZE)
    {
        float2 object_center = final_pos + final_size * 0.5;
        float2 half_size = final_size * 0.5;
        float2 offset = CURSOR_POS - object_center;
        float2 closest_point_vec = clamp(offset, -half_size, half_size);
        float2 dist_vec = offset - closest_point_vec;
        dist_vec.x *= SCREEN_RES.x / SCREEN_RES.y;
        float dist = length(dist_vec);
        const float HOVER_RADIUS = 0.002;
        float proximity = saturate(1.0 - dist / HOVER_RADIUS);
        proximity = 1.0 - (1.0 - proximity) * (1.0 - proximity);
        const float max_scale = 1.2;
        float scale_factor = 1.0 + (max_scale - 1.0) * (proximity*2);
        final_pos = object_center - (final_size * scale_factor * 0.5);
        final_size *= scale_factor;
    }
    
    output.object_pos_size = float4(final_pos, final_size);
    
    // 1. Создаем ОРИГИНАЛЬНЫЕ UV для геометрии
    uint local_vertex_id = vertex_id % 6;
    float2 local_quad_uv;
    switch (local_vertex_id) {
        case 0: case 3: local_quad_uv = float2(0.0, 0.0); break; 
        case 1: case 5: local_quad_uv = float2(1.0, 1.0); break; 
        case 2:         local_quad_uv = float2(0.0, 1.0); break; 
        case 4:         local_quad_uv = float2(1.0, 0.0); break; 
    }

    // 2. Создаем отдельную копию UV для ТЕКСТУРЫ
    float2 texture_uv = local_quad_uv;
    
    // 3. Инвертируем ТОЛЬКО текстурные UV, если это текст или число
    if (output.draw_mode == DRAW_MODE_TEXT || output.draw_mode == DRAW_MODE_NUMBER) {
        texture_uv.y = 1.0 - texture_uv.y;
    }
    
    // 4. Используем инвертированные UV для получения текстурных координат из атласа
    output.uv = GetTextureUV(output.draw_mode, texture_uv, TileDataBuffer[instance_id], vertex_id, final_pos, final_size);
    
    // 5. Используем ОРИГИНАЛЬНЫЕ, нетронутые UV для расчета позиции вершин на экране
    float2 final_vertex_pos = CalculateVertexPosition(output.fn_type, final_pos, final_size, local_quad_uv);
    output.local_uv = local_quad_uv;
    output.pos.xy = final_vertex_pos * 2.0 - 1.0;
    output.pos.zw = float2(0.5, 1.0);
}

#endif

#ifdef PIXEL_SHADER

float4 ApplyOverlay(float4 base, float4 blend) {
    float r = (base.r < 0.5) ? (2.0 * base.r * blend.r) : (1.0 - 2.0 * (1.0 - base.r) * (1.0 - blend.r));
    float g = (base.g < 0.5) ? (2.0 * base.g * blend.g) : (1.0 - 2.0 * (1.0 - base.g) * (1.0 - blend.g));
    float b = (base.b < 0.5) ? (2.0 * base.b * blend.b) : (1.0 - 2.0 * (1.0 - base.b) * (1.0 - blend.b));
    return float4(r, g, b, base.a);
}
float4 GetBackgroundBlurColor(vs2ps input) {
    // --- Шаг 1: Получаем базовый размытый цвет фона (без изменений) ---
    float4 sumColor = 0;
    float blur_strength = input.draw_mode - DRAW_MODE_BLUR_BACKGROUND_START + 1;
    float2 TexelSize = (1.0 / SCREEN_RES.xy) * blur_strength;
    const int BlurRadius = 4;
    [unroll]
    for (int y = -BlurRadius; y <= BlurRadius; ++y) {
        [unroll]
        for (int x = -BlurRadius; x <= BlurRadius; ++x) {
            sumColor += tex_backbuffer.Sample(s0_s, input.uv + float2(x, y) * TexelSize);
        }
    }
    float4 blurred_background = sumColor / ((BlurRadius * 2 + 1) * (BlurRadius * 2 + 1));
    blurred_background.rgb *= 0.75; // Ваше оригинальное затемнение

    // --- Шаг 2: Рассчитываем результаты двух эффектов при 100% силе ---
    // a) Результат чистого Overlay
    float3 full_overlay_rgb = ApplyOverlay(blurred_background, input.color).rgb;
    // b) Результат чистого Lerp (это просто цвет панели, так как lerp(a, b, 1.0) = b)
    float3 full_lerp_rgb = input.color.rgb;

    // --- Шаг 3: Комбинируем эти два эффекта в заданной пропорции (75% / 25%) ---
    // lerp(a, b, t) = a * (1-t) + b * t
    // lerp(overlay, lerp, 0.25) = overlay * 0.75 + lerp * 0.25
    float3 combined_effect_rgb = lerp(full_overlay_rgb, full_lerp_rgb, 1.0);

    // --- Шаг 4: Применяем общую интенсивность с помощью альфа-канала ---
    // Смешиваем исходный размытый фон с нашим новым, сложным комбинированным эффектом.
    // input.color.a выступает как мастер-регулятор интенсивности.
    float3 final_rgb = lerp(blurred_background.rgb, combined_effect_rgb, input.color.a);

    // --- Шаг 5: Возвращаем итоговый цвет ---
    return float4(final_rgb, 1.0); 
}
float4 GetBaseTextureColor(vs2ps input) {
    // --- FIX for warning X4000: Initialize a return value and use a single return point.
    float4 base_color = float4(1, 1, 1, 1);
    switch(input.draw_mode) {
        case DRAW_MODE_NUMBER:
        case DRAW_MODE_TEXT:             
            base_color = tex_atlas_font.Sample(s0_s, input.uv);
            break;
        case DRAW_MODE_TEXTURE_OVERLAY:  
        case DRAW_MODE_TEXTURE_MULTIPLY: 
            base_color = tex_atlas_icons.Sample(s0_s, float2(input.uv.x, 1.0 - input.uv.y));
            break;
    }
    return base_color;
}
float4 ApplyObjectBlur(float4 base_color, vs2ps input) {
    if (input.fx_type != FX_BLUR || input.draw_mode == DRAW_MODE_SOLID) { return base_color; }
    float4 blur_sum = 0;
    float blur_spread = 2.0 / 256.0;
    [unroll]
    for (int y = -1; y <= 2; y++) {
        [unroll]
        for (int x = -1; x <= 2; x++) {
            float2 sample_uv = input.uv + float2(x, y) * blur_spread;
            switch (input.draw_mode) {
                case DRAW_MODE_NUMBER:
                case DRAW_MODE_TEXT:             blur_sum += tex_atlas_font.Sample(s0_s, sample_uv); break;
                case DRAW_MODE_TEXTURE_OVERLAY:  
                case DRAW_MODE_TEXTURE_MULTIPLY: blur_sum += tex_atlas_icons.Sample(s0_s, float2(sample_uv.x, 1.0 - sample_uv.y)); break;
            }
        }
    }
    return blur_sum / 16.0;
}
float4 GetFinalBlendedColor(float4 tex_color, vs2ps input) {
    switch(input.draw_mode) {
        case DRAW_MODE_TEXTURE_MULTIPLY:
            return tex_color * input.color;
        case DRAW_MODE_TEXTURE_OVERLAY: {
            return tex_color; // Просто возвращаем цвет из текстуры
        }
        case DRAW_MODE_NUMBER:
        case DRAW_MODE_TEXT:
            return float4(input.color.rgb, tex_color.r * input.color.a);
        case DRAW_MODE_SOLID: 
        default:
            return input.color;
    }
}
float GetDistanceToEdge(float2 uv)
{
    float dist_x = min(uv.x, 1.0 - uv.x);
    float dist_y = min(uv.y, 1.0 - uv.y);
    return min(dist_x, dist_y);
}
float GetAlpha(int mode, float2 uv) {
    switch(mode) {
        case DRAW_MODE_NUMBER:
        case DRAW_MODE_TEXT:             return tex_atlas_font.Sample(s0_s, uv).r;
        case DRAW_MODE_TEXTURE_OVERLAY:  
        case DRAW_MODE_TEXTURE_MULTIPLY: return tex_atlas_icons.Sample(s0_s, float2(uv.x, 1.0 - uv.y)).a;
        case DRAW_MODE_SOLID:            return 1.0;
        default:                         return 0.0;
    }
}

void main(vs2ps input, out float4 result : SV_Target0)
{
    result = float4(0,0,0,0); // Initialize result to avoid warnings on early discard
    if (input.clip_rect.z > 0.0 && input.clip_rect.w > 0.0)
    {
        float clip_min_x = input.clip_rect.x;
        float clip_max_x = input.clip_rect.x + input.clip_rect.z;
        float clip_min_y = SCREEN_RES.y - input.clip_rect.y - input.clip_rect.w;
        float clip_max_y = clip_min_y + input.clip_rect.w;
        bool is_outside = 
            input.pos.x < clip_min_x 
            || input.pos.x > clip_max_x
            || input.pos.y < clip_min_y 
            || input.pos.y > clip_max_y;
        if (is_outside)
        {
            discard;
        }
    }
    if (input.draw_mode >= DRAW_MODE_BLUR_BACKGROUND_START && input.draw_mode <= DRAW_MODE_BLUR_BACKGROUND_END)
    {
        result = GetBackgroundBlurColor(input);
        return; // Выходим из шейдера, так как цвет уже определен
    }
    float2 texel_size = float2(0,0);
    if (input.fx_type == FX_HOVER_OUTLINE_INWARD || input.fx_type == FX_HOVER_SHEEN)
    {
        uint width, height;
        switch(input.draw_mode) {
            case DRAW_MODE_NUMBER:
            case DRAW_MODE_TEXT:             tex_atlas_font.GetDimensions(width, height); break;
            case DRAW_MODE_TEXTURE_OVERLAY:
            case DRAW_MODE_TEXTURE_MULTIPLY: tex_atlas_icons.GetDimensions(width, height); break;
        }
        if (width > 0 && height > 0) {
            texel_size = 1.0 / float2(width, height);
        }
    }
    
    if (input.fx_type == FX_OUTLINE)
    {
        float center_alpha = GetAlpha(input.draw_mode, input.uv);
        if (center_alpha > 0.5) {
            result = GetFinalBlendedColor(GetBaseTextureColor(input), input);
            if(result.a < 0.01) discard;
            return;
        } else {
            float max_neighbor_alpha = 0.0;
            const float outline_thickness = 0.01;
            float2 offsets[8] = { 
                float2(0, 1), float2(0, -1), float2(1, 0), float2(-1, 0),
                float2(0.7, 0.7), float2(-0.7, 0.7), float2(0.7, -0.7), float2(-0.7, -0.7)
            };
            [unroll]
            for (int i = 0; i < 8; i++) {
                max_neighbor_alpha = max(max_neighbor_alpha, GetAlpha(input.draw_mode, input.uv + offsets[i] * outline_thickness));
            }
            if (max_neighbor_alpha > 0.5) {
                result = float4(1.0, 1.0, 1.0, max_neighbor_alpha);
                return;
            } else {
                discard;
            }
        }
    }

    float4 final_color = GetFinalBlendedColor(ApplyObjectBlur(GetBaseTextureColor(input), input), input);

    if (input.fx_type == FX_HOVER_OUTLINE_INWARD)
    {
        float dist_from_edge = GetDistanceToEdge(input.local_uv);
        const float outline_thickness = 0.05;
        float outline_factor = step(dist_from_edge, outline_thickness);
        
        if (GetAlpha(input.draw_mode, input.uv) > 0.5)
        {
            final_color.rgb = lerp(final_color.rgb, float3(1,1,1), outline_factor * 0.7);
        }
    }

    if (final_color.a > 0.01)
    {
        if (input.fx_type == FX_HOVER_SHEEN)
        {
            float dist_from_edge = GetDistanceToEdge(input.uv);
            const float sheen_border_width = 0.1;
            float edge_mask = pow(1.0 - saturate(dist_from_edge / sheen_border_width), 2.0);

            float2 object_pos = input.object_pos_size.xy;
            float2 object_size = input.object_pos_size.zw;
            float2 cursor_relative_to_object = (CURSOR_POS - object_pos) / object_size;
            float2 shine_dir = normalize(float2(1.0, -1.0));
            float2 local_uv = input.uv - 0.5;
            float projection = dot(local_uv, shine_dir);
            float shine_pos = (cursor_relative_to_object.x - 0.5) * 1.2;
            const float stripe_width = 0.15;
            float shine_intensity = pow(saturate(1.0 - abs(projection - shine_pos) / stripe_width), 3.0);
            
            float final_sheen = shine_intensity * edge_mask;

            if (GetAlpha(input.draw_mode, input.uv) > 0.5)
            {
                final_color.rgb += float3(1,1,1) * final_sheen * 1.5;
            }
        }
        if (input.fx_type == FX_HOVER_SHINE)
        {
            float2 object_pos = input.object_pos_size.xy;
            float2 object_size = input.object_pos_size.zw;
            float2 cursor_relative_to_object = (CURSOR_POS - object_pos) / object_size;
            float2 shine_dir = normalize(float2(1.0, -1.0));
            float2 local_uv = input.uv - 0.5;
            float projection = dot(local_uv, shine_dir);
            float shine_pos = (cursor_relative_to_object.x - 0.5) * 1.2;
            const float stripe_width = 0.15;
            float dist_from_shine = abs(projection - shine_pos);
            float intensity = pow(saturate(1.0 - dist_from_shine / stripe_width), 3.0);
            final_color.rgb += float3(1,1,1) * intensity * 0.7;
        }
    }

    if (final_color.a < 0.01) discard;
    result = final_color;
}
#endif