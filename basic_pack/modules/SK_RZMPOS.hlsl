// **** UNIFIED SHAPE ANIMATION SHADER (SK_RZMPOS) ****
// Contributors: Zlevir, Antigravity

struct VertexAttributes {
    float3 position;
    float3 normal;
    float4 tangent;
};

struct SparseDelta {
    uint vertex_id;
    float3 delta;
    float3 padding1;
    float3 padding2;
};

RWStructuredBuffer<VertexAttributes> rw_buffer : register(u5);
StructuredBuffer<SparseDelta> shapekey : register(t51);

Buffer<float> shape_configs : register(t54);

Texture1D<float4> IniParams : register(t120);

#define PI 3.141592653589793
#define GLOBAL_SPEED_MULTIPLIER 1.0
#define ORIG_V_COUNT ((uint)round(IniParams[115].x))

[numthreads(256, 1, 1)]
void main(uint3 threadID : SV_DispatchThreadID)
{
    uint i = threadID.x;
    uint sparse_count, stride;
    shapekey.GetDimensions(sparse_count, stride);
    if (i >= sparse_count) return;

    SparseDelta entry = shapekey[i];
    uint vertex_id = entry.vertex_id;

    uint vertex_count, rw_stride;
    rw_buffer.GetDimensions(vertex_count, rw_stride);
    if (vertex_id >= vertex_count) return;
    
    // RAYVICH EDIT: keep VFX vertices appended after original mesh untouched by native shapes.
    if (vertex_id >= ORIG_V_COUNT) return;

    // --- 1. Get all parameters ---
    float input_val = IniParams[88].x;
    int anim_type = (int)round(IniParams[88].y);
    int config_index = (int)round(IniParams[88].z);

    // Read static parameters from flat float buffer (6 floats per config)
    uint base_offset = config_index * 6;
    float start_time = shape_configs[base_offset + 0];
    float end_time = shape_configs[base_offset + 1];
    float multiplier = shape_configs[base_offset + 2];
    float is_inverse = shape_configs[base_offset + 3];
    float t2 = shape_configs[base_offset + 4];
    float t3 = shape_configs[base_offset + 5];

    float weight = 0.0;

    if (anim_type == -2)
    {
        // Static fallback mode (no range remap, multiplier, or inverse)
        weight = input_val;
    }
    else if (anim_type == -1)
    {
        // Linear mode with range remap, multiplier, and inverse
        weight = input_val;
        float rmin = start_time;
        float rmax = end_time;
        float rspan = rmax - rmin;
        if (rmin > 0.0001 || rmax < 0.9999)
        {
            if (weight <= rmin)
            {
                weight = 0.0;
            }
            else if (weight >= rmax)
            {
                weight = 1.0;
            }
            else if (rspan > 0.0001)
            {
                weight = (weight - rmin) / rspan;
            }
            else
            {
                weight = 0.0;
            }
        }

        // Apply multiplier and inverse
        if (is_inverse > 0.5)
        {
            weight = 1.0 - (weight * multiplier);
        }
        else
        {
            weight = weight * multiplier;
        }
    }
    else
    {
        // Animation mode
        float global_time = frac(input_val * GLOBAL_SPEED_MULTIPLIER);

        if (global_time >= start_time && global_time <= end_time)
        {
            float rise_dur = t2 - start_time;
            float fall_dur = end_time - t3;

            if (rise_dur > 0.0 && global_time < t2)
            {
                float progress = (global_time - start_time) / rise_dur;
                weight = 0.5 * (1.0 - cos(progress * PI));
            }
            else if (fall_dur > 0.0 && global_time > t3)
            {
                float progress = (end_time - global_time) / fall_dur;
                weight = 0.5 * (1.0 - cos(progress * PI));
            }
            else
            {
                weight = 1.0;
            }
        }

        // Apply multiplier and inverse
        if (is_inverse > 0.5)
        {
            weight = 1.0 - (weight * multiplier);
        }
        else
        {
            weight = weight * multiplier;
        }
    }

    rw_buffer[vertex_id].position += entry.delta * weight;
}
