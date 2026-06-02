// vfx_curve_physics_cs.hlsl
// Compute shader using character motion history (matrices) to trail spline positions in World Space.
// Coordinate spaces:
//   Blender space  = what CurveData stores, what rw_buffer.position expects
//   Game space     = what cb1 world matrix operates in (ZZZ/Hoyo)
//   AXIS_MAP_*     = Blender->Game remap:  game.x=-blender.x, game.y=blender.z, game.z=blender.y

struct VertexAttributes {
    float3 position;
    float3 normal;
    float4 tangent;
};

RWStructuredBuffer<VertexAttributes> rw_buffer : register(u5);
Buffer<float4> CoordsHistory : register(t6); // Character World Matrix history
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

// AXIS_MAP_*: Blender->Game (same as original RemapCoords)
#define AXIS_MAP_X  -1
#define AXIS_MAP_Y   2
#define AXIS_MAP_Z   3

// Blender space -> Game space
float3 RemapCoords(float3 pos)
{
    float3 result;

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

// Game space -> Blender space (exact inverse of RemapCoords with AXIS_MAP_X=-1, Y=2, Z=3)
// game.x = -blender.x  =>  blender.x = -game.x
// game.y =  blender.z  =>  blender.z =  game.y
// game.z =  blender.y  =>  blender.y =  game.z
float3 InverseRemapCoords(float3 game)
{
    float3 blender;
    blender.x = -game.x;  // inverse of AXIS_MAP_X = -1
    blender.y =  game.z;  // inverse of AXIS_MAP_Y =  2 (game.y=blender.z => blender.y=game.z)
    blender.z =  game.y;  // inverse of AXIS_MAP_Z =  3 (game.z=blender.y => blender.z=game.y)
    return blender;
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

SampledPoint SampleCurve(uint curve_idx, float path_progress, uint num_shapes, float shape_blend) {
    float t = clamp(path_progress, 0.0f, 1.0f);

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

[numthreads(128, 1, 1)]
void main(uint3 threadID : SV_DispatchThreadID)
{
    uint i = threadID.x;
    uint vertex_count, stride;
    rw_buffer.GetDimensions(vertex_count, stride);
    if (i >= vertex_count) return;

    uint cutoff_index = (uint)ORIG_V_COUNT;
    if (i < cutoff_index) return;

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
    
    float packed_tls = p_meta.normal.z + 0.1f;
    float CFG_TL_MID   = floor(packed_tls / 1000.0f) / 100.0f;
    float CFG_TL_START = frac(floor(packed_tls) / 1000.0f) * 10.0f;
    
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
    } else if (mesh_fx_type == 2) { // Circle
        if (v_local_id == 0) {
            local_pos = float3(0.0f, 0.0f, 0.0f);
        } else {
            float angle = float(v_local_id - 1) * (2.0f * 3.14159265f / 6.0f);
            local_pos = float3(cos(angle), sin(angle), 0.0f);
        }
    } else if (mesh_fx_type == 4) { // Heart
        float3 heart_verts[10] = {
            float3( 0.00f,  0.45f, 0.0f),
            float3(-0.28f,  0.78f, 0.0f),
            float3(-0.50f,  0.84f, 0.0f),
            float3(-0.82f,  0.60f, 0.0f),
            float3(-0.96f,  0.12f, 0.0f),
            float3( 0.00f, -1.00f, 0.0f),
            float3( 0.96f,  0.12f, 0.0f),
            float3( 0.82f,  0.60f, 0.0f),
            float3( 0.50f,  0.84f, 0.0f),
            float3( 0.28f,  0.78f, 0.0f)
        };
        local_pos = heart_verts[v_local_id % 10];
    } else if (mesh_fx_type == 5) { // Star
        float3 star_verts[11] = {
            float3( 0.00000f,  0.00000f, 0.0f),
            float3( 0.00000f,  1.00000f, 0.0f),
            float3(-0.24687f,  0.33979f, 0.0f),
            float3(-0.95106f,  0.30902f, 0.0f),
            float3(-0.39944f, -0.12979f, 0.0f),
            float3(-0.58779f, -0.80902f, 0.0f),
            float3( 0.00000f, -0.42000f, 0.0f),
            float3( 0.58779f, -0.80902f, 0.0f),
            float3( 0.39944f, -0.12979f, 0.0f),
            float3( 0.95106f,  0.30902f, 0.0f),
            float3( 0.24687f,  0.33979f, 0.0f)
        };
        local_pos = star_verts[v_local_id % 11];
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
    else if (mesh_fx_type == 4) v_per_particle = 10;
    else if (mesh_fx_type == 5) v_per_particle = 11;

    uint active_i = i - cutoff_index;
    uint particle_id = active_i / v_per_particle;

    float phase_offset_raw = rw_buffer[i].normal.x;
    float speed_scale = rw_buffer[i].normal.y;
    float3 spread_dir = rw_buffer[i].tangent.xyz;

    float p_seed_1 = hash(particle_id * 13 + 7);
    float p_seed_2 = hash(particle_id * 37 + 11);
    float p_seed_3 = hash(particle_id * 59 + 3);
    float p_seed_4 = hash(particle_id * 97 + 23);
    
    bool is_spark = (p_seed_1 > 0.75f); 

    float phase_offset = phase_offset_raw * CFG_PHASE_RANDOMNESS;
    float cycle = frac(TIME / CFG_CYCLE_DURATION + phase_offset);

    float active_t = clamp((cycle - CFG_TL_START) / max(CFG_TL_END - CFG_TL_START, 1e-5f), 0.0f, 1.0f);

    float k = clamp((CFG_TL_MID - CFG_TL_START) / max(CFG_TL_END - CFG_TL_START, 1e-5f), 0.01f, 0.99f);
    float A = (0.5f - k) / (k * k - k);
    float B = 1.0f - A;
    float path_progress = clamp(A * active_t * active_t + B * active_t, 0.0f, 1.0f);

    float shape_blend = frac(TIME / max(CFG_CYCLE_DURATION, 1e-5f));
    SampledPoint sampled = SampleCurve(curve_idx, path_progress, num_shapes, shape_blend);

    float3 pos_on_line = sampled.position;

    float3 plane_dir = normalize(spread_dir - sampled.tangent * dot(spread_dir, sampled.tangent));

    float local_radius = sampled.radius * CFG_DISPERSION_SCALE;
    if (is_spark) {
        local_radius *= 3.0f;
    }
    
    float3 final_center = pos_on_line + plane_dir * (p_seed_3 * local_radius);

    float3 jitter_dir = normalize(float3(p_seed_1 - 0.5f, p_seed_2 - 0.5f, p_seed_3 - 0.5f));
    float jitter_amount = hash(particle_id * 79 + 5) * CFG_POS_RANDOMNESS;
    final_center += jitter_dir * jitter_amount;

    // ----------------------------------------------------------------------
    // WORLD-SPACE TRAILING PHYSICS — DELTA METHOD
    // Records raw cb1 as-is; all transforms happen here at read time.
    // ----------------------------------------------------------------------
    uint len = 64; // ring buffer length — must match x1 in INI
    uint state_offset = len * 4;
    float4 state = CoordsHistory[state_offset];
    uint write_slot = (uint)(state.z + 0.5f);

    float max_lag_frames = 30.0f; // <-- TUNE: trail strength (frames)

    // Fractional K: instead of snapping to one history slot, interpolate between two
    float K_f = path_progress * max_lag_frames;
    uint  K0  = (uint)K_f;                          // floor slot
    uint  K1  = min(K0 + 1, len - 1);               // ceil slot (clamped to buffer)
    float Kfrac = K_f - (float)K0;                  // interpolation factor [0..1)

    uint hist_slot0 = (write_slot - K0 + len) % len;
    uint hist_slot1 = (write_slot - K1 + len) % len;

    // Current frame: columns of local->world rotation, c3 = world position
    float4 c0 = CoordsHistory[write_slot * 4 + 0];
    float4 c1 = CoordsHistory[write_slot * 4 + 1];
    float4 c2 = CoordsHistory[write_slot * 4 + 2];
    float4 c3 = CoordsHistory[write_slot * 4 + 3];

    // Historical positions at K0 and K1 frames ago
    float4 h3_K0 = CoordsHistory[hist_slot0 * 4 + 3];
    float4 h3_K1 = CoordsHistory[hist_slot1 * 4 + 3];

    // Safety: snap uninitialized slots to current position
    if (h3_K0.w < 0.5f) h3_K0 = c3;
    if (h3_K1.w < 0.5f) h3_K1 = c3;

    // Sub-frame interpolated historical position
    float3 h3_pos = lerp(h3_K0.xyz, h3_K1.xyz, Kfrac);

    // Teleport snap: if history is too far away, collapse to current
    if (distance(h3_pos, c3.xyz) > 2.0f) { // <-- TUNE: snap threshold (world units)
        h3_pos = c3.xyz;
    }

    // Delta in world space: direction of travel (current - old = forward vector)
    // Negated so particles trail BEHIND the character
    float3 world_delta = c3.xyz - h3_pos;

    // Rotate world_delta into current LOCAL game space via transpose (orthonormal inverse)
    float3 local_delta = float3(
        dot(world_delta, c0.xyz),
        dot(world_delta, c1.xyz),
        dot(world_delta, c2.xyz)
    );

    // Apply offset: root (path_progress=0) stays fixed, tip (path_progress=1) gets full delta
    float3 game_center = RemapCoords(final_center) + local_delta * path_progress;
    final_center = game_center;
    // ----------------------------------------------------------------------

    float size_scale = (active_t <= 0.5f) 
        ? lerp(CFG_SIZE_START, 1.0f, active_t * 2.0f) 
        : lerp(1.0f, CFG_SIZE_END, (active_t - 0.5f) * 2.0f);
    
    float size_rand_mult = lerp(CFG_SIZE_RAND_MIN, CFG_SIZE_RAND_MAX, p_seed_4);
    float current_size = CFG_SIZE_BASE * size_scale * size_rand_mult;
    float fade = smoothstep(0.0f, 0.1f, active_t) * smoothstep(1.0f, 0.9f, active_t);
    
    if (cycle < CFG_TL_START || cycle > CFG_TL_END) {
        fade = 0.0f;
    }
    
    current_size *= fade;

    if (is_spark) {
        current_size *= (0.3f + p_seed_2 * 0.4f);
    }

    float3 rot_axis = normalize(float3(p_seed_1, p_seed_2, p_seed_3) * 2.0f - 1.0f);
    float rot_speed_factor = 2.0f * 3.14159f / CFG_CYCLE_DURATION;
    float current_rot = (TIME * rot_speed_factor * speed_scale) + (p_seed_1 * 6.28f); 
    if (is_spark) {
        current_rot *= 2.5f;
    }
    
    float4 q_rot = q_from_axis_angle(rot_axis, current_rot);
    local_pos = q_rotate(local_pos, q_rot) * current_size;

    // final_center is in game space; remap local_pos Blender->Game before adding
    rw_buffer[i].position = final_center + RemapCoords(local_pos);
}
