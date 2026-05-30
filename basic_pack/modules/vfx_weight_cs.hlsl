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
#define ORIG_V_COUNT ((uint)round(IniParams.Load(int2(115, 0)).x))
#define TIME         IniParams.Load(int2(98, 0)).x

[numthreads(32, 1, 1)]
void main(uint3 threadID : SV_DispatchThreadID)
{
    uint i = threadID.x;
    uint vertex_count, stride;
    rw_blend.GetDimensions(vertex_count, stride);
    if (i >= vertex_count) return;

    // Skip original mesh vertices — only touch VFX particles
    // round() prevents float→uint truncation errors
    uint cutoff = ORIG_V_COUNT;
    if (i < cutoff) return;

    // Read timing metadata for shape blend (matches position CS exactly)
    uint  curve_idx = (uint)vb0[i].normal.z;
    CurvePoint p_meta = CurveData[curve_idx * 257 + 256];

    float packed_fx   = p_meta.position.x;
    uint  packed_val  = (uint)floor(packed_fx + 1e-6f);
    uint  num_shapes  = packed_val / 10u;
    float CFG_TL_END  = clamp((packed_fx - (float)packed_val) * 10.0f, 0.0f, 1.0f);
    float CFG_CYCLE_DURATION = p_meta.tangent.y;
    float CFG_PHASE_RANDOMNESS = p_meta.normal.x;

    float packed_tls   = p_meta.normal.z + 0.1f;
    float CFG_TL_MID   = floor(packed_tls / 1000.0f) / 100.0f;
    float CFG_TL_START = frac(floor(packed_tls) / 1000.0f) * 10.0f;

    // Per-particle path_progress (same easing as position CS)
    float phase    = vb0[i].normal.x;
    float phase_offset = phase * CFG_PHASE_RANDOMNESS;
    float cycle    = frac(TIME / max(CFG_CYCLE_DURATION, 1e-5f) + phase_offset);
    float active_t = clamp((cycle - CFG_TL_START) / max(CFG_TL_END - CFG_TL_START, 1e-5f), 0.0f, 1.0f);
    float k = clamp((CFG_TL_MID - CFG_TL_START) / max(CFG_TL_END - CFG_TL_START, 1e-5f), 0.01f, 0.99f);
    float A = (0.5f - k) / (k * k - k);
    float B = 1.0f - A;
    float path_progress = clamp(A * active_t * active_t + B * active_t, 0.0f, 1.0f);

    // Shape blend — global (same for all particles, mirrors position CS)
    float shape_blend = frac(TIME / max(CFG_CYCLE_DURATION, 1e-5f));

    // Shape indices & factor (same math as SampleCurve in position CS)
    uint  shape_idx0   = 0u;
    uint  shape_idx1   = 0u;
    float shape_factor = 0.0f;
    if (num_shapes > 0u) {
        float t_scaled = clamp(shape_blend, 0.0f, 1.0f) * (float)num_shapes;
        shape_idx0 = (uint)floor(t_scaled);
        shape_idx1 = min(shape_idx0 + 1u, num_shapes);
        shape_factor = t_scaled - (float)shape_idx0;
        if (shape_idx0 >= num_shapes) { shape_idx0 = num_shapes; shape_idx1 = num_shapes; shape_factor = 0.0f; }
    }

    // Point index along curve (arc-length, same as position CS)
    uint point_idx = min((uint)(path_progress * 31.0f + 0.5f), 31u);

    // Sample weight from both shape layers and lerp
    // Layout: curve_idx * 256 + shape_idx * 32 + point_idx
    uint base = curve_idx * 256u;
    BlendData w0 = CurveWeightData[base + shape_idx0 * 32u + point_idx];
    BlendData w1 = CurveWeightData[base + shape_idx1 * 32u + point_idx];

    // Lerp weights; indices from dominant shape (shape_factor < 0.5 → shape0, else shape1)
    BlendData result;
    result.weights = lerp(w0.weights, w1.weights, shape_factor);
    result.indices = (shape_factor < 0.5f) ? w0.indices : w1.indices;

    rw_blend[i] = result;

}
