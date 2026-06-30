RWTexture2D<float4> Target : register(u0);
Texture2D<float4> DecalTexture : register(t0);
Texture2D<float4> SlotMask : register(t5);
struct StampRecord {
    uint target_xy;
    uint decal_uv;
    uint weight_flags;
};
StructuredBuffer<StampRecord> StampBuffer : register(t6);
Texture1D<float4> IniParams : register(t120);

#define ColorMultiplier IniParams[43]
#define CompRect        IniParams[45]
#define OverlayColor    IniParams[47]
#define StateFlags      IniParams[24]
#define UseMask         (StateFlags.w > 0.5f)

#define RZM_STAMP_MAGIC 0x444D5A52u

SamplerState samLinear {
    Filter = MIN_MAG_MIP_LINEAR;
    AddressU = Clamp;
    AddressV = Clamp;
};

uint UnpackLo16(uint v) { return v & 0xFFFFu; }
uint UnpackHi16(uint v) { return (v >> 16) & 0xFFFFu; }
float UnpackUnorm16(uint v) { return (float)(v & 0xFFFFu) * (1.0f / 65535.0f); }
float UnpackUnorm16Hi(uint v) { return (float)((v >> 16) & 0xFFFFu) * (1.0f / 65535.0f); }

float2 ApplyDecalRuntimeTransform(float2 uv) {
    bool isPass1 = StateFlags.z > 0.5f;
    int mirrorMode = isPass1 ? (int)IniParams[108].y : (int)IniParams[108].x;
    bool mirror = mirrorMode == 1 || mirrorMode == 3;
    bool flip = mirrorMode == 2 || mirrorMode == 3;
    if (mirror) uv.x = 1.0f - uv.x;
    if (flip) uv.y = 1.0f - uv.y;
    return uv;
}

[numthreads(256, 1, 1)]
void main(uint3 dispatchThreadID : SV_DispatchThreadID) {
    uint structCount;
    uint stride;
    StampBuffer.GetDimensions(structCount, stride);
    if (structCount <= 1u) return;

    StampRecord header = StampBuffer[0];
    if (header.target_xy != RZM_STAMP_MAGIC) return;

    uint recordIndex = dispatchThreadID.x;
    uint recordCount = structCount - 1u;
    if (recordIndex >= recordCount) return;

    StampRecord stamp = StampBuffer[recordIndex + 1u];

    uint2 targetPos = uint2(UnpackLo16(stamp.target_xy), UnpackHi16(stamp.target_xy));
    float2 uv = float2(UnpackUnorm16(stamp.decal_uv), UnpackUnorm16Hi(stamp.decal_uv));
    float weight = UnpackUnorm16(stamp.weight_flags);

    uint2 targetDim;
    Target.GetDimensions(targetDim.x, targetDim.y);
    if (targetPos.x >= targetDim.x || targetPos.y >= targetDim.y) return;

    if (CompRect.z > 0.0f && CompRect.w > 0.0f) {
        if (targetPos.x < (uint)CompRect.x || targetPos.x >= (uint)(CompRect.x + CompRect.z) ||
            targetPos.y < (uint)CompRect.y || targetPos.y >= (uint)(CompRect.y + CompRect.w)) return;
    }

    bool isPass1 = StateFlags.z > 0.5f;
    if (isPass1) {
        float yVal = StateFlags.y + 0.1f;
        bool mirrorTargetX = (yVal >= 1.0f && yVal < 2.0f) || (yVal >= 3.0f);
        bool mirrorTargetY = (yVal >= 2.0f);
        if (mirrorTargetX) targetPos.x = targetDim.x - 1u - targetPos.x;
        if (mirrorTargetY) targetPos.y = targetDim.y - 1u - targetPos.y;
    }

    uv = ApplyDecalRuntimeTransform(saturate(uv));

    float4 decalColor = DecalTexture.SampleLevel(samLinear, uv, 0) * ColorMultiplier;
    decalColor.a *= weight;

    if (UseMask) {
        float2 maskUV = (float2(targetPos) + 0.5f) / float2(targetDim);
        if (CompRect.z > 0.0f && CompRect.w > 0.0f) {
            maskUV = (float2(targetPos) + 0.5f - CompRect.xy) / CompRect.zw;
        }
        decalColor.a *= SlotMask.SampleLevel(samLinear, maskUV, 0).r;
    }

    if (decalColor.a <= 0.001f) return;
    if (OverlayColor.w > 0.0f) {
        decalColor.rgb = lerp(decalColor.rgb, OverlayColor.rgb, saturate(decalColor.a * OverlayColor.w));
    }

    float4 bg = Target[targetPos];
    bg.rgb = lerp(bg.rgb, decalColor.rgb, decalColor.a);
    bg.a = max(bg.a, decalColor.a);
    Target[targetPos] = bg;
}
