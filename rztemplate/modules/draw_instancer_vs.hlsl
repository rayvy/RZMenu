// draw_instancer_vs.hlsl - RZMenu Main Vertex Shader
struct VS_INPUT {
    uint vertex_id : SV_VertexID;
    uint instance_id : SV_InstanceID;
};

struct VS_OUTPUT {
    float4 pos : SV_POSITION;
    float2 uv : TEXCOORD0;
    float4 color : COLOR0;
    float4 style_params : TEXCOORD1;
};

// Buffers
Buffer<float4> ResourceDataBuffer : register(t100);
Buffer<float4> ResourceMeshVertexBuffer : register(t107);
Buffer<float4> ResourceSkinWeightBuffer : register(t108);
Buffer<float4> ResourceAnimatedBoneBuffer : register(t109);

Texture2D<float4> StereoParams : register(t125); 

void main(VS_INPUT input, out VS_OUTPUT output) {
    uint base = input.instance_id * 7;
    float4 d0 = ResourceDataBuffer.Load(base + 0); // pos_x, pos_y, width, height
    float4 d1 = ResourceDataBuffer.Load(base + 1); // tex_x, tex_y, tex_w, tex_h
    float4 d2 = ResourceDataBuffer.Load(base + 2); // color (RGBA)
    float4 d4 = ResourceDataBuffer.Load(base + 4); // [style_id, unused, mesh_offset, drawType]
    
    float2 el_pos = d0.xy;
    float2 el_size = d0.zw;
    float4 el_color = d2;
    float drawType = d4.w;
    
    float2 final_pos_local;
    float2 final_uv;
    
    if (drawType == 9.0) {
        uint mesh_base = (uint)d4.z; 
        uint v_idx = mesh_base + input.vertex_id;
        float4 v_raw = ResourceMeshVertexBuffer.Load(v_idx);
        final_pos_local = v_raw.xy;
        final_uv = v_raw.zw;
        
        float4 w0 = ResourceSkinWeightBuffer.Load(v_idx * 2 + 0);
        float4 w1 = ResourceSkinWeightBuffer.Load(v_idx * 2 + 1);
        
        float2 skinned_pos = float2(0, 0);
        float weights[4] = {w0.y, w0.w, w1.y, w1.w};
        int bones[4] = {(int)w0.x, (int)w0.z, (int)w1.x, (int)w1.z};
        
        bool has_skinning = false;
        [unroll]
        for(int i=0; i<4; i++) {
            if (weights[i] > 0.0 && bones[i] >= 0) {
                float4 r0 = ResourceAnimatedBoneBuffer.Load(bones[i] * 2 + 0);
                float4 r1 = ResourceAnimatedBoneBuffer.Load(bones[i] * 2 + 1);
                skinned_pos.x += dot(float3(final_pos_local, 1.0), r0.xyz) * weights[i];
                skinned_pos.y += dot(float3(final_pos_local, 1.0), r1.xyz) * weights[i];
                has_skinning = true;
            }
        }
        if (has_skinning) final_pos_local = skinned_pos;
    } else {
        if (input.vertex_id >= 6) {
            output.pos = float4(0,0,0,0);
            output.uv = float2(0,0);
            output.color = float4(0,0,0,0);
            output.style_params = float4(0,0,0,0);
            return;
        }
        float2 quad_uvs[6] = {
            float2(0,0), float2(1,0), float2(0,1),
            float2(0,1), float2(1,0), float2(1,1)
        };
        float2 uv = quad_uvs[input.vertex_id];
        final_pos_local = uv * el_size;
        final_uv = d1.xy + uv * d1.zw;
    }
    
    float4 sw = StereoParams.Load(uint3(0,0,0));
    float2 world_pos = el_pos + final_pos_local;
    float2 ndc = (world_pos / sw.xy) * 2.0 - 1.0;
    ndc.y = -ndc.y;
    
    output.pos = float4(ndc, 0, 1);
    output.uv = final_uv;
    output.color = el_color;
    output.style_params = d4;
}
