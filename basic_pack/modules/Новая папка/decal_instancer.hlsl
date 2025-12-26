// ==================================================================
// == decal_instancer.hlsl - ВЕРСИЯ, КОТОРАЯ УБИВАЕТ ПОСЛЕДНИЙ WARNING
// ==================================================================
Buffer<float2> DecalDataBuffer : register(t59);

Texture2D<float4> baseTex : register(t40);
Texture2D<float4> atlas_slot_60 : register(t60);
Texture2D<float4> atlas_slot_61 : register(t61);
Texture2D<float4> atlas_slot_62 : register(t62);
Texture2D<float4> atlas_slot_63 : register(t63);
SamplerState s0_s : register(s0);

struct vs2ps {
    float4 pos          : SV_Position;
    float2 uv           : TEXCOORD0;
    
    nointerpolation int    decalIndex : TEXCOORD1;
    nointerpolation int    atlasIndex  : TEXCOORD2;
    float2 tileGrid     : TEXCOORD3;
    nointerpolation bool   mirror      : TEXCOORD4;
    nointerpolation bool   flip        : TEXCOORD5;
};


#ifdef VERTEX_SHADER
// Вертексный шейдер уже идеален, не трогаем его.
void main(out vs2ps output, uint vertex_id : SV_VertexID, uint instance_id : SV_InstanceID)
{
    if (instance_id == 0) {
        output.uv = float2((vertex_id << 1) & 2, vertex_id & 2);
        output.pos = float4(output.uv * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
        output.decalIndex = -1;
        output.atlasIndex = 0;
        output.tileGrid = float2(1,1);
        output.mirror = false;
        output.flip = false;
        return;
    }
    int buffer_idx = instance_id - 1;
    float2 data = DecalDataBuffer[buffer_idx];
    int slotID = (int)data.x;
    output.decalIndex = (int)data.y;

    if (output.decalIndex == 0) {
        output.pos = float4(2.0, 2.0, 2.0, 1.0);
        output.decalIndex = 0;
        output.atlasIndex = 0;
        output.tileGrid = float2(1,1);
        output.mirror = false;
        output.flip = false;
        output.uv = float2(0,0);
        return;
    }
    float2 decalCenter = float2(0,0);
    float2 decalSize = float2(0,0);
    float decalAngle = 0.0f;

    switch (slotID) {
        case 0: decalCenter=float2(0.23,0.8);decalSize=float2(0.2,0.2);decalAngle=0;output.tileGrid=float2(4,4);output.mirror=false;output.flip=false;output.atlasIndex=60;break;
        case 1: decalCenter=float2(0.2225,0.62);decalSize=float2(0.18,0.1);decalAngle=0;output.tileGrid=float2(4,4);output.mirror=false;output.flip=false;output.atlasIndex=61;break;
        case 2: decalCenter=float2(0.27,0.57);decalSize=float2(0.1,0.1);decalAngle=0;output.tileGrid=float2(4,2);output.mirror=false;output.flip=true;output.atlasIndex=62;break;
        case 3: decalCenter=float2(0.17,0.57);decalSize=float2(0.1,0.1);decalAngle=0;output.tileGrid=float2(4,2);output.mirror=false;output.flip=false;output.atlasIndex=62;break;
        case 4: decalCenter=float2(0.11,0.09);decalSize=float2(0.2,0.17);decalAngle=4.75;output.tileGrid=float2(4,4);output.mirror=false;output.flip=true;output.atlasIndex=60;break;
        case 5: decalCenter=float2(0.61,0.09);decalSize=float2(0.2,0.17);decalAngle=-4.75;output.tileGrid=float2(4,4);output.mirror=true;output.flip=true;output.atlasIndex=60;break;
        case 6: decalCenter = float2(0.18025, 0.32276);decalSize = float2(0.35594, 0.111);decalAngle  = 90.0 * 0.01745329;output.tileGrid = float2(4,4);output.mirror = false; output.flip=true; output.atlasIndex = 61; break;
        case 7: decalCenter = float2(0.5375, 0.32276);decalSize = float2(0.35594, 0.111);decalAngle  = -90.0 * 0.01745329;output.tileGrid = float2(4,4);output.mirror = false;output.flip = false;output.atlasIndex = 61;break;
        case 8: decalCenter=float2(0.66,0.75);decalSize=float2(0.17,0.12);decalAngle=0;output.tileGrid=float2(4,4);output.mirror=false;output.flip=false;output.atlasIndex=60;break;
        case 9: decalCenter=float2(0.66,0.57);decalSize=float2(0.17,0.12);decalAngle=0;output.tileGrid=float2(4,4);output.mirror=false;output.flip=false;output.atlasIndex=60;break;
        case 10: decalCenter=float2(0.21,0.47);decalSize=float2(0.17,0.12);decalAngle=0;output.tileGrid=float2(4,4);output.mirror=false;output.flip=false;output.atlasIndex=60;break;
        case 11: decalCenter=float2(0.75,0.84);decalSize=float2(0.18,0.16);decalAngle=-0.34906;output.tileGrid=float2(4,4);output.mirror=false;output.flip=false;output.atlasIndex=60;break;
        case 12: decalCenter=float2(0.56,0.84);decalSize=float2(0.18,0.16);decalAngle=0.34906;output.tileGrid=float2(4,4);output.mirror=false;output.flip=false;output.atlasIndex=60;break;
        case 13: decalCenter=float2(0.375,0.73);decalSize=float2(0.18,0.16);decalAngle=0;output.tileGrid=float2(4,4);output.mirror=false;output.flip=false;output.atlasIndex=60;break;
        case 14: decalCenter=float2(0.125,0.73);decalSize=float2(0.18,0.16);decalAngle=0;output.tileGrid=float2(4,4);output.mirror=false;output.flip=false;output.atlasIndex=60;break;
        case 15: decalCenter=float2(0.21,0.70);decalSize=float2(0.18,0.16);decalAngle=0;output.tileGrid=float2(4,4);output.mirror=false;output.flip=false;output.atlasIndex=60;break;
        default:
            output.pos = float4(2.0, 2.0, 2.0, 1.0);
            output.decalIndex = 0;
            output.atlasIndex = 0;
            output.tileGrid = float2(1,1);
            output.mirror = false;
            output.flip = false;
            output.uv = float2(0,0);
            return;
    }
    float2 screen_pos = float2(0,0);
    switch(vertex_id){case 0:screen_pos=float2(0,1);break; case 1:screen_pos=float2(1,1);break; case 2:screen_pos=float2(0,0);break; case 3:screen_pos=float2(1,0);break;}
    float s = sin(decalAngle), c = cos(decalAngle);
    float2 centered_pos = screen_pos - 0.5;
    float2 rotated_pos;
    rotated_pos.x = centered_pos.x * c - centered_pos.y * s;
    rotated_pos.y = centered_pos.x * s + centered_pos.y * c;
    output.pos.xy = (decalCenter - (decalSize * 0.5)) + (rotated_pos + 0.5) * decalSize;
    output.pos.xy = output.pos.xy * 2.0 - 1.0;
    output.pos.y *= -1.0;
    output.pos.zw = float2(0.5, 1.0);
    output.uv = screen_pos;
}
#endif


#ifdef PIXEL_SHADER
void main(vs2ps input, out float4 result : SV_Target0)
{
    result = float4(0,0,0,0);

    if (input.decalIndex == -1) {
        result = baseTex.Sample(s0_s, input.uv);
        result.w = 1;
        return;
    }
    if (input.decalIndex == 0) {
        return;
    }
    // float4 baseColor = baseTex.Sample(s0_s, input.uv);
    float4 baseColor = 0;
    
    float2 decalUV = input.uv;
    decalUV.x=1-decalUV.x;
    if(input.mirror){decalUV.y=1-decalUV.y;}
    if(input.flip){decalUV.x=1-decalUV.x;}
    float f_decalIndex = (float)input.decalIndex;
    float tileY = floor(f_decalIndex / input.tileGrid.x);
    float tileX = f_decalIndex - tileY * input.tileGrid.x;
    float2 tileSize=1.0/input.tileGrid;
    float2 tileOffset=float2(tileX,tileY)*tileSize;
    decalUV=decalUV*tileSize+tileOffset;
    float4 decalColor;
    switch(input.atlasIndex){
        case 60: decalColor = atlas_slot_60.Sample(s0_s, decalUV); break;
        case 61: decalColor = atlas_slot_61.Sample(s0_s, decalUV); break;
        case 62: decalColor = atlas_slot_62.Sample(s0_s, decalUV); break;
        case 63: decalColor = atlas_slot_63.Sample(s0_s, decalUV); break;
        default: return;
    }
    result = decalColor;
}
#endif