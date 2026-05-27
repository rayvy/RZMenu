// vfx_weight_cs.hlsl
// Dynamically writes bone weights for VFX particle vertices each frame.
// Reads per-point weight table (baked at export), samples by particle path_progress.

// ------- Blend buffer layout (stride = 32 for ZZZ) -------
struct BlendData {
    float4 weights; // 4x float32
    uint4  indices; // 4x uint32
};

// ------- Packed VB0 layout (stride = 40) -------
struct VertexPos {
    float3 position;
    float3 normal;   // x=phase, y=speed_scale, z=curve_idx
    float4 tangent;  // xyz=dir, w=v_local_id
};

// ------- CurveData metadata -------
struct CurvePoint {
    float3 position;
    float3 tangent;
    float3 normal;
    float  u;
};

RWStructuredBuffer<BlendData> rw_blend     : register(u5);
StructuredBuffer<VertexPos>   vb0          : register(t50);
StructuredBuffer<CurvePoint>  CurveData    : register(t51);
StructuredBuffer<BlendData>   CurveWeightData : register(t52);

Texture1D<float4> IniParams : register(t120);
#define ORIG_V_COUNT IniParams[115].x
#define TIME         IniParams[98].x

[numthreads(128, 1, 1)]
void main(uint3 threadID : SV_DispatchThreadID)
{
    uint i = threadID.x;
    uint vertex_count, stride;
    rw_blend.GetDimensions(vertex_count, stride);
    if (i >= vertex_count) return;

    // Skip original mesh vertices — only touch VFX particles
    uint cutoff = (uint)ORIG_V_COUNT;
    if (i < cutoff) return;

    // Read particle params from Position buffer (these fields aren't overwritten by position CS)
    float phase     = vb0[i].normal.x;
    uint  curve_idx = (uint)vb0[i].normal.z;

    // Read metadata to compute path_progress (matches position CS logic)
    CurvePoint p_meta = CurveData[curve_idx * 257 + 256];
    float packed_val   = floor(p_meta.position.x + 1e-6f);
    float CFG_TL_END   = clamp((p_meta.position.x - packed_val) * 10.0f, 0.0f, 1.0f);
    float CFG_CYCLE_DUR = p_meta.tangent.y;
    float packed_tls   = p_meta.normal.z + 0.1f;
    float CFG_TL_MID   = floor(packed_tls / 1000.0f) / 100.0f;
    float CFG_TL_START = frac(floor(packed_tls) / 1000.0f) * 10.0f;

    float cycle    = frac(TIME / max(CFG_CYCLE_DUR, 1e-5f) + phase);
    float active_t = clamp((cycle - CFG_TL_START) / max(CFG_TL_END - CFG_TL_START, 1e-5f), 0.0f, 1.0f);
    float k = clamp((CFG_TL_MID - CFG_TL_START) / max(CFG_TL_END - CFG_TL_START, 1e-5f), 0.01f, 0.99f);
    float A = (0.5f - k) / (k * k - k);
    float B = 1.0f - A;
    float path_progress = clamp(A * active_t * active_t + B * active_t, 0.0f, 1.0f);

    // Nearest sample point (no lerping — simple and fast)
    uint point_idx = min((uint)(path_progress * 31.0f + 0.5f), 31u);

    // Copy weight entry directly from lookup table
    rw_blend[i] = CurveWeightData[curve_idx * 32 + point_idx];
}
