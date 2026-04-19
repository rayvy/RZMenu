// animate_bones.hlsl - Hierarchical Bone Transform for Live2D
// t106: ResourceBoneBuffer (Input: Local PRS + parent_idx)
// u7: ResourceAnimatedBoneBuffer (Output: World Matrices for Skinning)

struct BoneInput {
    float2 local_pos;
    float local_rot;
    float local_scale;
    int parent_idx;
    float3 padding;
};

struct BoneOutput {
    float4 mat_row0;
    float4 mat_row1;
};

Buffer<float4> BonesIn : register(t106);
RWBuffer<float4> BonesOut : register(u7);

#define MAX_BONES 256

[numthreads(1, 1, 1)]
void main(uint3 dtid : SV_DispatchThreadID) {
    // Only first thread handles the hierarchy to ensure parents are computed before children.
    // Given the small number of bones (max 256), this is extremely fast on GPU.
    if (dtid.x > 0) return;

    // Temporary storage for computed world matrices in this pass
    // mat2x3 represented as float4x2 or just two float4
    float4 world_mat_r0[MAX_BONES];
    float4 world_mat_r1[MAX_BONES];

    // Assuming bones are sorted: parent_idx < current_idx
    for (int i = 0; i < MAX_BONES; i++) {
        float4 f0 = BonesIn.Load(i * 2 + 0); // pos.xy, rot, scale
        float4 f1 = BonesIn.Load(i * 2 + 1); // parent_idx, pad.xyz
        
        if (f0.w == 0.0 && f1.x == -1) break; // End of list marker? Or just use a count

        float2 b_pos = f0.xy;
        float b_rot = f0.z;
        float b_scale = f0.w;
        int p_idx = (int)f1.x;

        // Construct local matrix (2x3 Affine)
        float s, c;
        sincos(b_rot, s, c);
        
        float m00 = c * b_scale;
        float m01 = -s * b_scale;
        float m02 = b_pos.x;
        float m10 = s * b_scale;
        float m11 = c * b_scale;
        float m12 = b_pos.y;

        if (p_idx >= 0 && p_idx < i) {
            // Parent World * Local 
            float4 pr0 = world_mat_r0[p_idx];
            float4 pr1 = world_mat_r1[p_idx];

            float wr00 = pr0.x * m00 + pr0.y * m10;
            float wr01 = pr0.x * m01 + pr0.y * m11;
            float wr02 = pr0.x * m02 + pr0.y * m12 + pr0.z; // pr0.z is tx

            float wr10 = pr1.x * m00 + pr1.y * m10;
            float wr11 = pr1.x * m01 + pr1.y * m11;
            float wr12 = pr1.x * m02 + pr1.y * m12 + pr1.z; // pr1.z is ty

            world_mat_r0[i] = float4(wr00, wr01, wr02, 0);
            world_mat_r1[i] = float4(wr10, wr11, wr12, 0);
        } else {
            // No parent, world = local
            world_mat_r0[i] = float4(m00, m01, m02, 0);
            world_mat_r1[i] = float4(m10, m11, m12, 0);
        }

        // Write output
        BonesOut[i * 2 + 0] = world_mat_r0[i];
        BonesOut[i * 2 + 1] = world_mat_r1[i];
    }
}
