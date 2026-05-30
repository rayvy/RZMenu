struct VertexAttributes {
    float3 position;
    float3 normal;
    float4 tangent;
};

RWStructuredBuffer<VertexAttributes> rw_buffer : register(u5);
Texture1D<float4> IniParams : register(t120);

#define TIME IniParams.Load(int2(98, 0)).x
#define ORIG_V_COUNT ((uint)round(IniParams.Load(int2(115, 0)).x))

struct CurvePoint {
    float3 position;
    float3 tangent;
    float3 normal;
    float u;
};

StructuredBuffer<CurvePoint> CurveData : register(t50);

// =====================================================================
// COORDINATE SYSTEM AXIS CONFIGURATOR
// Use this to remap the output X, Y, Z coordinate axes of the VFX curve.
// Values can be:
//   1: +X,  -1: -X
//   2: +Y,  -2: -Y
//   3: +Z,  -3: -Z
// For example:
//   To swap Y and Z axes: map Y to 3, and Z to 2.
// =====================================================================
// Defaults configured for Zenless Zone Zero:
// (For Genshin Impact and Honkai Star Rail: X=-1, Y=2, Z=3)
#define AXIS_MAP_X  -1
#define AXIS_MAP_Y   2
#define AXIS_MAP_Z   3

float3 RemapCoords(float3 pos)
{
    float3 result;

    // Output X axis remapping
    #if AXIS_MAP_X == 1
        result.x = pos.x;
    #elif AXIS_MAP_X == -1
        result.x = -pos.x;
    #elif AXIS_MAP_X == 2
        result.x = pos.y;
    #elif AXIS_MAP_X == -2
        result.x = -pos.y;
    #elif AXIS_MAP_X == 3
        result.x = pos.z;
    #elif AXIS_MAP_X == -3
        result.x = -pos.z;
    #else
        result.x = pos.x;
    #endif

    // Output Y axis remapping
    #if AXIS_MAP_Y == 1
        result.y = pos.x;
    #elif AXIS_MAP_Y == -1
        result.y = -pos.x;
    #elif AXIS_MAP_Y == 2
        result.y = pos.y;
    #elif AXIS_MAP_Y == -2
        result.y = -pos.y;
    #elif AXIS_MAP_Y == 3
        result.y = pos.z;
    #elif AXIS_MAP_Y == -3
        result.y = -pos.z;
    #else
        result.y = pos.y;
    #endif

    // Output Z axis remapping
    #if AXIS_MAP_Z == 1
        result.z = pos.x;
    #elif AXIS_MAP_Z == -1
        result.z = -pos.x;
    #elif AXIS_MAP_Z == 2
        result.z = pos.y;
    #elif AXIS_MAP_Z == -2
        result.z = -pos.y;
    #elif AXIS_MAP_Z == 3
        result.z = pos.z;
    #elif AXIS_MAP_Z == -3
        result.z = -pos.z;
    #else
        result.z = pos.z;
    #endif

    return result;
}

float hash(uint n) {
    n = (n ^ 61) ^ (n >> 16);
    n *= 9;
    n = n ^ (n >> 4);
    n *= 0x27d4eb2d;
    n = n ^ (n >> 15);
    return float(n & 0x7fffffff) / 2147483647.0;
}

float4 q_from_axis_angle(float3 axis, float angle) {
    float half_angle = angle * 0.5f;
    float s, c;
    sincos(half_angle, s, c);
    return float4(axis * s, c);
}

float3 q_rotate(float3 v, float4 q) {
    return v + 2.0f * cross(q.xyz, cross(q.xyz, v) + q.w * v);
}

struct SampledPoint {
    float3 position;
    float3 tangent;
    float3 normal;
    float radius;
};

// Shape blend slots: one per curve (supports up to 4 curves with independent shapes)
// IniParams[116].x = shape blend for curve 0, IniParams[117].x = curve 1, etc.

SampledPoint SampleCurve(uint curve_idx, float path_progress, uint num_shapes, float shape_blend) {
    float t = clamp(path_progress, 0.0f, 1.0f);

    // Shape selection: driven by SEPARATE shape_blend value [0..1], NOT path_progress
    uint shape_idx0 = 0;
    uint shape_idx1 = 0;
    float shape_factor = 0.0f;

    if (num_shapes > 0) {
        float t_scaled = clamp(shape_blend, 0.0f, 1.0f) * (float)num_shapes;
        shape_idx0 = (uint)floor(t_scaled);
        shape_idx1 = min(shape_idx0 + 1, num_shapes);
        shape_factor = t_scaled - (float)shape_idx0;
        if (shape_idx0 >= num_shapes) {
            shape_idx0 = num_shapes;
            shape_idx1 = num_shapes;
            shape_factor = 0.0f;
        }
    }

    // Curve position sampling: driven by path_progress independently
    float t_spline = t * 31.0f;
    uint idx0 = (uint)floor(t_spline);
    uint idx1 = min(idx0 + 1, 31);
    float factor = t_spline - float(idx0);

    uint base_idx = curve_idx * 257;

    CurvePoint p0_s0 = CurveData[base_idx + shape_idx0 * 32 + idx0];
    CurvePoint p1_s0 = CurveData[base_idx + shape_idx0 * 32 + idx1];
    float3 pos_s0    = lerp(p0_s0.position, p1_s0.position, factor);
    float3 tan_s0    = lerp(p0_s0.tangent,  p1_s0.tangent,  factor);
    float3 nor_s0    = lerp(p0_s0.normal,   p1_s0.normal,   factor);
    float  rad_s0    = lerp(p0_s0.u,        p1_s0.u,        factor);

    CurvePoint p0_s1 = CurveData[base_idx + shape_idx1 * 32 + idx0];
    CurvePoint p1_s1 = CurveData[base_idx + shape_idx1 * 32 + idx1];
    float3 pos_s1    = lerp(p0_s1.position, p1_s1.position, factor);
    float3 tan_s1    = lerp(p0_s1.tangent,  p1_s1.tangent,  factor);
    float3 nor_s1    = lerp(p0_s1.normal,   p1_s1.normal,   factor);
    float  rad_s1    = lerp(p0_s1.u,        p1_s1.u,        factor);

    SampledPoint result;
    result.position = lerp(pos_s0, pos_s1, shape_factor);
    result.tangent  = normalize(lerp(tan_s0, tan_s1, shape_factor));
    result.normal   = normalize(lerp(nor_s0, nor_s1, shape_factor));
    result.radius   = lerp(rad_s0, rad_s1, shape_factor);
    return result;
}


[numthreads(32, 1, 1)]
void main(uint3 threadID : SV_DispatchThreadID)
{
    uint i = threadID.x;
    uint vertex_count, stride;
    rw_buffer.GetDimensions(vertex_count, stride);
    if (i >= vertex_count) return;

    // ==========================================
    // 1. НАСТРОЙКА ОФФСЕТИНГА (БЕЗОПАСНАЯ)
    // ==========================================
    // round() предотвращает потерю точности при передаче float→uint через IniParams
    uint cutoff_index = ORIG_V_COUNT;

    // Не трогаем оригинальные вершины меша персонажа!
    if (i < cutoff_index) {
        return;
    }

    // ==========================================
    // 2. ИЗВЛЕЧЕНИЕ ПАРАМЕТРОВ ЧЕРЕЗ METADATA POINT
    // ==========================================
    uint curve_idx = (uint)rw_buffer[i].normal.z;
    
    CurvePoint p_meta = CurveData[curve_idx * 257 + 256];
    float packed_fx_and_end = p_meta.position.x;
    uint packed_val = (uint)floor(packed_fx_and_end + 1e-6f);
    uint num_shapes = packed_val / 10;
    uint mesh_fx_type = packed_val % 10;
    float CFG_TL_END   = clamp((packed_fx_and_end - (float)packed_val) * 10.0f, 0.0f, 1.0f);

    float CFG_SIZE_BASE  = p_meta.position.y;
    float CFG_SIZE_START = p_meta.position.z;
    float CFG_SIZE_END   = p_meta.tangent.x;
    float CFG_CYCLE_DURATION = p_meta.tangent.y;
    float CFG_DISPERSION_SCALE = p_meta.tangent.z;
    float CFG_PHASE_RANDOMNESS = p_meta.normal.x;
    float CFG_POS_RANDOMNESS = p_meta.normal.y;
    
    // Unpack packed_tls (p_meta.normal.z = start_int + mid_int * 1000)
    float packed_tls = p_meta.normal.z + 0.1f;
    float CFG_TL_MID   = floor(packed_tls / 1000.0f) / 100.0f;
    float CFG_TL_START = frac(floor(packed_tls) / 1000.0f) * 10.0f;
    
    // Unpack packed_rand (p_meta.u = min_int + max_int * 1000)
    float packed_rand = p_meta.u + 0.1f;
    float CFG_SIZE_RAND_MAX = floor(packed_rand / 1000.0f) / 100.0f;
    float CFG_SIZE_RAND_MIN = frac(floor(packed_rand) / 1000.0f) * 10.0f;

    uint v_local_id = (uint)rw_buffer[i].tangent.w;

    float3 local_pos = float3(0.0f, 0.0f, 0.0f);
    if (mesh_fx_type == 1) { // Quad
        float3 quad_verts[4] = {
            float3(-0.5f, -0.5f, 0.0f),
            float3( 0.5f, -0.5f, 0.0f),
            float3(-0.5f,  0.5f, 0.0f),
            float3( 0.5f,  0.5f, 0.0f)
        };
        local_pos = quad_verts[v_local_id % 4];
    } else if (mesh_fx_type == 2) { // Circle (hexagon: center + 6 outer)
        if (v_local_id == 0) {
            local_pos = float3(0.0f, 0.0f, 0.0f);
        } else {
            float angle = float(v_local_id - 1) * (2.0f * 3.14159265f / 6.0f);
            local_pos = float3(cos(angle), sin(angle), 0.0f);
        }
    } else { // Triangle
        float3 tri_verts[3] = {
            float3(0.0f, 1.0f, 0.0f),
            float3(-0.866f, -0.5f, 0.0f),
            float3( 0.866f, -0.5f, 0.0f)
        };
        local_pos = tri_verts[v_local_id % 3];
    }

    uint v_per_particle = 3;
    if (mesh_fx_type == 1) v_per_particle = 4;
    else if (mesh_fx_type == 2) v_per_particle = 7;

    uint active_i = i - cutoff_index;
    uint particle_id = active_i / v_per_particle;

    // Извлекаем уникальные для частицы фазу, скорость и направление
    float phase_offset_raw = rw_buffer[i].normal.x;
    float speed_scale = rw_buffer[i].normal.y;
    float3 spread_dir = rw_buffer[i].tangent.xyz;

    float p_seed_1 = hash(particle_id * 13 + 7);
    float p_seed_2 = hash(particle_id * 37 + 11);
    float p_seed_3 = hash(particle_id * 59 + 3);
    float p_seed_4 = hash(particle_id * 97 + 23);
    
    bool is_spark = (p_seed_1 > 0.75f); 

    // Линейный цикл с учетом настройки фазовой случайности
    float phase_offset = phase_offset_raw * CFG_PHASE_RANDOMNESS;
    float cycle = frac(TIME / CFG_CYCLE_DURATION + phase_offset);

    // Active lifecycle fraction based on timeline start and end times
    float active_t = clamp((cycle - CFG_TL_START) / max(CFG_TL_END - CFG_TL_START, 1e-5f), 0.0f, 1.0f);

    // Timeline Easing: map active_t (0.0 to 1.0) to path_progress (0.0 to 1.0)
    // passing through 0.5 at the mid time: k = (TL_MID - TL_START) / (TL_END - TL_START)
    float k = clamp((CFG_TL_MID - CFG_TL_START) / max(CFG_TL_END - CFG_TL_START, 1e-5f), 0.01f, 0.99f);
    float A = (0.5f - k) / (k * k - k);
    float B = 1.0f - A;
    float path_progress = clamp(A * active_t * active_t + B * active_t, 0.0f, 1.0f);

    // Shape blend: глобальное время делит цикл на N равных сегментов.
    // Basis→SK1→SK2→...→SKN циклично за CFG_CYCLE_DURATION секунд.
    float shape_blend = frac(TIME / max(CFG_CYCLE_DURATION, 1e-5f));
    SampledPoint sampled = SampleCurve(curve_idx, path_progress, num_shapes, shape_blend);

    float3 pos_on_line = sampled.position;

    // Направление распыления ортогонально направлению кривой
    float3 plane_dir = normalize(spread_dir - sampled.tangent * dot(spread_dir, sampled.tangent));

    // Вычисляем локальный радиус распыления (scaled by CFG_DISPERSION_SCALE)
    float local_radius = sampled.radius * CFG_DISPERSION_SCALE;
    if (is_spark) {
        local_radius *= 3.0f;
    }
    
    float3 final_center = pos_on_line + plane_dir * (p_seed_3 * local_radius);

    // Вносим хаотичное смещение позиции (Position Randomness)
    float3 jitter_dir = normalize(float3(p_seed_1 - 0.5f, p_seed_2 - 0.5f, p_seed_3 - 0.5f));
    float jitter_amount = hash(particle_id * 79 + 5) * CFG_POS_RANDOMNESS;
    final_center += jitter_dir * jitter_amount;

    // Управление размером и фейдом в пределах активного жизненного цикла
    // Размер интерполируется от Start Scale к 1.0 (в середине) и затем от 1.0 к End Scale (в конце)
    float size_scale = (active_t <= 0.5f) 
        ? lerp(CFG_SIZE_START, 1.0f, active_t * 2.0f) 
        : lerp(1.0f, CFG_SIZE_END, (active_t - 0.5f) * 2.0f);
    
    float size_rand_mult = lerp(CFG_SIZE_RAND_MIN, CFG_SIZE_RAND_MAX, p_seed_4);
    float current_size = CFG_SIZE_BASE * size_scale * size_rand_mult;
    float fade = smoothstep(0.0f, 0.1f, active_t) * smoothstep(1.0f, 0.9f, active_t);
    
    // Если мы вне активного окна (cycle < tl_start или cycle > tl_end), полностью скрываем частицу
    if (cycle < CFG_TL_START || cycle > CFG_TL_END) {
        fade = 0.0f;
    }
    
    current_size *= fade;

    if (is_spark) {
        current_size *= (0.3f + p_seed_2 * 0.4f);
    }

    // Вращение
    float3 rot_axis = normalize(float3(p_seed_1, p_seed_2, p_seed_3) * 2.0f - 1.0f);
    float rot_speed_factor = 2.0f * 3.14159f / CFG_CYCLE_DURATION;
    float current_rot = (TIME * rot_speed_factor * speed_scale) + (p_seed_1 * 6.28f); 
    if (is_spark) {
        current_rot *= 2.5f;
    }
    
    float4 q_rot = q_from_axis_angle(rot_axis, current_rot);
    local_pos = q_rotate(local_pos, q_rot) * current_size;

    // Запись геометрии
    rw_buffer[i].position = RemapCoords(final_center + local_pos);
}
