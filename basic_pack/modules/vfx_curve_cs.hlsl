struct VertexAttributes {
    float3 position;
    float3 normal;
    float4 tangent;
};

RWStructuredBuffer<VertexAttributes> rw_buffer : register(u5);
Texture1D<float4> IniParams : register(t120);

#define TIME IniParams[98].x
#define ORIG_V_COUNT IniParams[115].x

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
#define AXIS_MAP_X   1
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
};

SampledPoint SampleCurve(uint curve_idx, float cycle) {
    float t_scaled = clamp(cycle, 0.0f, 1.0f) * 31.0f;
    uint idx0 = (uint)floor(t_scaled);
    uint idx1 = min(idx0 + 1, 31);
    float factor = t_scaled - float(idx0);

    uint base_idx = curve_idx * 33; // 33 points per curve block
    CurvePoint p0 = CurveData[base_idx + idx0];
    CurvePoint p1 = CurveData[base_idx + idx1];

    SampledPoint result;
    result.position = lerp(p0.position, p1.position, factor);
    result.tangent = normalize(lerp(p0.tangent, p1.tangent, factor));
    result.normal = normalize(lerp(p0.normal, p1.normal, factor));
    return result;
}

[numthreads(128, 1, 1)]
void main(uint3 threadID : SV_DispatchThreadID)
{
    uint i = threadID.x;
    uint vertex_count, stride;
    rw_buffer.GetDimensions(vertex_count, stride);
    if (i >= vertex_count) return;

    // ==========================================
    // 1. НАСТРОЙКА ОФФСЕТИНГА (БЕЗОПАСНАЯ)
    // ==========================================
    uint cutoff_index = (uint)ORIG_V_COUNT;

    // Не трогаем оригинальные вершины меша персонажа!
    if (i < cutoff_index) {
        return;
    }

    // ==========================================
    // 2. ИЗВЛЕЧЕНИЕ ПАРАМЕТРОВ ЧЕРЕЗ METADATA POINT
    // ==========================================
    uint curve_idx = (uint)rw_buffer[i].normal.z;
    
    CurvePoint p_meta = CurveData[curve_idx * 33 + 32];
    uint mesh_fx_type = (uint)p_meta.position.x;
    float CFG_BASE_SIZE = p_meta.position.y;
    float CFG_TRI_ASPECT = p_meta.position.z;
    float CFG_SPEED = p_meta.tangent.x;
    float CFG_START_RADIUS = p_meta.tangent.y;
    float CFG_END_RADIUS   = p_meta.tangent.z;
    float CFG_CURVE_RIGHT  = p_meta.normal.x;
    float CFG_CURVE_UP     = p_meta.normal.y;

    uint v_local_id = (uint)rw_buffer[i].tangent.w;

    float3 local_pos = float3(0.0f, 0.0f, 0.0f);
    if (mesh_fx_type == 1) { // Quad
        float3 quad_verts[4] = {
            float3(-0.5f * CFG_TRI_ASPECT, -0.5f, 0.0f),
            float3( 0.5f * CFG_TRI_ASPECT, -0.5f, 0.0f),
            float3(-0.5f * CFG_TRI_ASPECT,  0.5f, 0.0f),
            float3( 0.5f * CFG_TRI_ASPECT,  0.5f, 0.0f)
        };
        local_pos = quad_verts[v_local_id % 4];
    } else if (mesh_fx_type == 2) { // Circle (pentagon)
        if (v_local_id == 0) {
            local_pos = float3(0.0f, 0.0f, 0.0f);
        } else {
            float angle = float(v_local_id - 1) * (2.0f * 3.14159265f / 5.0f);
            local_pos = float3(cos(angle) * CFG_TRI_ASPECT, sin(angle), 0.0f);
        }
    } else { // Triangle
        float3 tri_verts[3] = {
            float3(0.0f, 1.0f, 0.0f),
            float3(-0.866f * CFG_TRI_ASPECT, -0.5f, 0.0f),
            float3( 0.866f * CFG_TRI_ASPECT, -0.5f, 0.0f)
        };
        local_pos = tri_verts[v_local_id % 3];
    }

    uint v_per_particle = 3;
    if (mesh_fx_type == 1) v_per_particle = 4;
    else if (mesh_fx_type == 2) v_per_particle = 6;

    uint active_i = i - cutoff_index;
    uint particle_id = active_i / v_per_particle;

    // Извлекаем уникальные для частицы фазу, скорость и направление
    float phase = rw_buffer[i].normal.x;
    float speed_scale = rw_buffer[i].normal.y;
    float3 spread_dir = rw_buffer[i].tangent.xyz;

    float p_seed_1 = hash(particle_id * 13 + 7);
    float p_seed_2 = hash(particle_id * 37 + 11);
    float p_seed_3 = hash(particle_id * 59 + 3);
    
    bool is_spark = (p_seed_1 > 0.75f); 

    // СИНУСОИДАЛЬНЫЙ ЦИКЛ ДЛЯ ПЛАВНОГО ДВИЖЕНИЯ
    float angle_time = TIME * 1.57079f * (CFG_SPEED * speed_scale) + (phase * 6.28318f);
    float raw_cycle = sin(angle_time) * 0.5f + 0.5f;
    float cycle = pow(raw_cycle, 1.2f); 

    // Сэмпл кривой
    SampledPoint sampled = SampleCurve(curve_idx, cycle);
    
    // Apply shifts in local curve space: right is cross(tangent, normal), up is normal
    float3 right_dir = normalize(cross(sampled.tangent, sampled.normal));
    float3 pos_on_line = sampled.position + sampled.normal * CFG_CURVE_UP + right_dir * CFG_CURVE_RIGHT;

    // Направление распыления ортогонально направлению кривой
    float3 plane_dir = normalize(spread_dir - sampled.tangent * dot(spread_dir, sampled.tangent));

    float current_radius = lerp(CFG_START_RADIUS, CFG_END_RADIUS, cycle);
    if (is_spark) {
        current_radius *= 3.0f;
    }
    
    float3 final_center = pos_on_line + plane_dir * (p_seed_3 * current_radius);

    // Управление размером (Затухание к концу)
    float current_size = CFG_BASE_SIZE;
    float distance_fade = 1.0f - cycle;
    current_size *= distance_fade;

    if (is_spark) current_size *= (0.3f + p_seed_2 * 0.4f);

    // Плавное появление у основания
    current_size *= smoothstep(0.01f, 0.15f, raw_cycle); 

    // Вращение
    float3 rot_axis = normalize(float3(p_seed_1, p_seed_2, p_seed_3) * 2.0f - 1.0f);
    float rot_speed = is_spark ? 15.0f : 5.0f; 
    float current_rot = sin(TIME * (CFG_SPEED * speed_scale) + p_seed_2) * rot_speed + (p_seed_1 * 30.0f); 
    
    float4 q_rot = q_from_axis_angle(rot_axis, current_rot);
    local_pos = q_rotate(local_pos, q_rot) * current_size;

    // Запись геометрии (Сохраняем normal и tangent с метаданными нетронутыми!)
    rw_buffer[i].position = RemapCoords(final_center + local_pos);
}
