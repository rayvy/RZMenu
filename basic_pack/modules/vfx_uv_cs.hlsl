// vfx_uv_cs.hlsl
// Production-ready UV animation compute shader.

struct VertexAttributes {
    float3 position;
    float3 normal;
    float4 tangent;
};

struct TexcoordVertex {
    uint uv0;     // 4 bytes (UNORM16/FP16 packed or float U)
    uint dummy1;  // 4 bytes (float V for float32 or UNORM16/FP16 packed UV1)
    uint dummy2;  // 4 bytes
    uint dummy3;  // 4 bytes
    uint dummy4;  // 4 bytes
};

struct CurvePoint {
    float3 position;
    float3 tangent;
    float3 normal;
    float u;
};

struct CurveUVPoint {
    float2 start_uv;
    float2 end_uv;
};

#define TIME            IniParams[98].x
#define ORIG_V_COUNT    (uint)IniParams[115].x
#define FORMAT          ((uint)IniParams[116].z)

RWStructuredBuffer<TexcoordVertex> rw_texcoord : register(u5);
Texture1D<float4> IniParams : register(t120);

StructuredBuffer<VertexAttributes> PositionData : register(t50);
StructuredBuffer<CurvePoint> CurveData : register(t51);
StructuredBuffer<CurveUVPoint> CurveUVData : register(t52);
StructuredBuffer<TexcoordVertex> original_texcoord : register(t53);

[numthreads(128, 1, 1)]
void main(uint3 threadID : SV_DispatchThreadID)
{
    uint i = threadID.x;
    
    uint vertex_count, stride;
    rw_texcoord.GetDimensions(vertex_count, stride);
    if (i >= vertex_count) return;

    // Skip original mesh vertices
    uint cutoff = (uint)ORIG_V_COUNT;
    if (i < cutoff) return;

    // 1. Unpack curve index and parameters from PositionData
    uint curve_idx = (uint)PositionData[i].normal.z;
    
    // 2. Read start/end UVs
    float2 start_uv = CurveUVData[curve_idx].start_uv;
    float2 end_uv = CurveUVData[curve_idx].end_uv;

    // If both start and end UVs are zero, it means Animated UV is disabled for this curve.
    // In this case, we keep the original base UV and do not modify it.
    if (all(start_uv == 0.0f) && all(end_uv == 0.0f)) {
        return;
    }

    CurvePoint p_meta = CurveData[curve_idx * 257 + 256];
    float packed_fx_and_end = p_meta.position.x;
    uint packed_val = (uint)floor(packed_fx_and_end + 1e-6f);
    float CFG_TL_END = clamp((packed_fx_and_end - (float)packed_val) * 10.0f, 0.0f, 1.0f);
    
    float CFG_CYCLE_DURATION = p_meta.tangent.y;
    float CFG_PHASE_RANDOMNESS = p_meta.normal.x;
    
    float packed_tls = p_meta.normal.z + 0.1f;
    float CFG_TL_MID   = floor(packed_tls / 1000.0f) / 100.0f;
    float CFG_TL_START = frac(floor(packed_tls) / 1000.0f) * 10.0f;

    float phase_offset_raw = PositionData[i].normal.x;
    float phase_offset = phase_offset_raw * CFG_PHASE_RANDOMNESS;
    
    float cycle = frac(TIME / CFG_CYCLE_DURATION + phase_offset);
    float active_t = clamp((cycle - CFG_TL_START) / max(CFG_TL_END - CFG_TL_START, 1e-5f), 0.0f, 1.0f);
    
    float k = clamp((CFG_TL_MID - CFG_TL_START) / max(CFG_TL_END - CFG_TL_START, 1e-5f), 0.01f, 0.99f);
    float A = (0.5f - k) / (k * k - k);
    float B = 1.0f - A;
    float path_progress = clamp(A * active_t * active_t + B * active_t, 0.0f, 1.0f);

    // 3. Read base UV from original_texcoord
    float u = 0.0f;
    float v = 0.0f;
    if (FORMAT == 1) {
        uint packed_uv = original_texcoord[i].uv0;
        u = f16tof32(packed_uv & 0xffff);
        v = f16tof32(packed_uv >> 16);
    } else {
        u = asfloat(original_texcoord[i].uv0);
        v = asfloat(original_texcoord[i].dummy1);
    }

    float2 base_uv = float2(u, v);

    // 4. Interpolate
    float2 animated_uv;
    if (path_progress < 0.5f) {
        animated_uv = lerp(start_uv, base_uv, path_progress * 2.0f);
    } else {
        animated_uv = lerp(base_uv, end_uv, (path_progress - 0.5f) * 2.0f);
    }

    // 5. Store back to rw_texcoord (write to both UV0 and UV1 slots to be safe!)
    if (FORMAT == 1) {
        uint u_half = f32tof16(animated_uv.x);
        uint v_half = f32tof16(animated_uv.y);
        uint packed_uv = (v_half << 16) | (u_half & 0xffff);
        rw_texcoord[i].uv0 = packed_uv;
        rw_texcoord[i].dummy1 = packed_uv; // Overwrite UV1 too
    } else {
        rw_texcoord[i].uv0 = asuint(animated_uv.x);
        rw_texcoord[i].dummy1 = asuint(animated_uv.y);
    }
}
