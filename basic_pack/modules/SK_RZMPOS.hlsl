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

Texture1D<float4> IniParams : register(t120);

#define PI 3.141592653589793
#define GLOBAL_SPEED_MULTIPLIER 10.0
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
    float start_time = IniParams[88].z;
    float end_time = IniParams[88].w;
    float multiplier = IniParams[89].x;
    float is_inverse = IniParams[89].y;

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
        float duration = end_time - start_time;

        if (duration > 0.0 && global_time >= start_time && global_time <= end_time)
        {
            float local_progress = (global_time - start_time) / duration;

            switch (anim_type)
            {
                case 200: // Double Linear
                {
                    float linear_weight;
                    if (local_progress < 0.5)
                    {
                        linear_weight = local_progress * 2.0;
                    }
                    else
                    {
                        linear_weight = 1.0 - (local_progress - 0.5) * 2.0;
                    }
                    weight = linear_weight * 2.0;
                    break;
                }
                case 1: // Hammer
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
                case 0: // Standard Sine
                default:
                {
                    weight = sin(local_progress * PI);
                    break;
                }
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
