// BlendResize.hlsl - Advanced Bone-Based Resize Shader
// Supports 12 master slots via register c88, c87, c86

// Master Sliders (passed from ini as x88, y88, z88, w88, etc.)
// register(c88) = slots 0, 1, 2, 3
// register(c87) = slots 4, 5, 6, 7
// register(c86) = slots 8, 9, 10, 11

float4 slots0_3 : register(c88);
float4 slots4_7 : register(c87);
float4 slots8_11 : register(c86);

// Bone Mapping Buffer
struct BoneData {
    int slot_index;
    int parent_index;
    float3 scale_axes;
    float3 origin;
    float3 offset;
};

Buffer<float4> bone_buffer : register(t1);

// Helper to get slot value by index
float GetSlotValue(int index) {
    if (index < 0) return 0;
    if (index < 4) return slots0_3[index]; // x88=index 0, y88=index 1...
    if (index < 8) return slots4_7[index - 4];
    if (index < 12) return slots8_11[index - 8];
    return 0;
}

// Helper to load bone data from Buffer<float4>
// Each BoneData is 11 floats (44 bytes), packed into 3 float4 (48 bytes total)
// Entry Layout:
// f0: [float slot_idx, float parent_idx, float scale_mask.x, float scale_mask.y]
// f1: [float scale_mask.z, float origin.x, float origin.y, float origin.z]
// f2: [float offset.x, float offset.y, float offset.z, (unused/0.0)]
BoneData LoadBone(int index) {
    BoneData d;
    float4 f0 = bone_buffer.Load(index * 3 + 0);
    float4 f1 = bone_buffer.Load(index * 3 + 1);
    float4 f2 = bone_buffer.Load(index * 3 + 2);
    
    d.slot_index = (int)f0.x;
    d.parent_index = (int)f0.y;
    d.scale_axes = float3(f0.z, f0.w, f1.x);
    d.origin = f1.yzw;
    d.offset = f2.xyz;
    return d;
}

void main(
    float4 pos : POSITION,
    float4 blend_indices : BLENDINDICES,
    float4 blend_weights : BLENDWEIGHT,
    out float4 out_pos : SV_POSITION
) {
    float3 finalPos = pos.xyz;
    float3 totalOffset = float3(0, 0, 0);

    // Apply transformation weighted by bone influences
    [unroll]
    for (int i = 0; i < 4; i++) {
        float weight = blend_weights[i];
        if (weight <= 0) continue;
        
        int bone_idx = (int)blend_indices[i];
        BoneData data = LoadBone(bone_idx);
        
        if (data.slot_index >= 0) {
            float scale_factor = GetSlotValue(data.slot_index);
            
            // Calculate scale vector based on axis masks
            // We use (1 + mask * factor) logic
            float3 s = float3(1, 1, 1) + (data.scale_axes * scale_factor);
            
            // Apply scale relative to origin
            float3 localPos = pos.xyz - data.origin;
            float3 scaledPos = localPos * s;
            
            // Apply custom offset (also scaled by factor)
            scaledPos += data.offset * scale_factor;
            
            // Blend into final position
            float3 delta = (scaledPos + data.origin) - pos.xyz;
            totalOffset += delta * weight;
        }
    }

    out_pos = float4(finalPos + totalOffset, 1.0);
}
