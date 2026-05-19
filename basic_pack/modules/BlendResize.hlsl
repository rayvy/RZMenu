Buffer<float4> BoneBuffer : register(t0);
Buffer<float4> DataBuffer : register(t69);
Texture1D<float4> IniParams : register(t120);

// Возвращаем получение переменной из текстуры
float GetVar(int id) {
    if (id < 0) return 1.0;
    uint u_id = (uint)id;
    uint row = 86u + u_id / 4u;
    uint col = u_id % 4u;
    return IniParams.Load(int2((int)row, 0))[(int)col];
}

void main(
  float3 vPos : POSITION0,
  float3 vNormal : NORMAL0,
  float4 vTangent : TANGENT0,
  float4 vWeights : BLENDWEIGHT0,
  int4 vIndices : BLENDINDICES0,
  out float3 oPos : POSITION0,
  out float3 oNormal : TEXCOORD0,
  out float4 oTangent : TEXCOORD1)
{
    oPos = float3(0, 0, 0);
    float3 accN = float3(0, 0, 0);
    float3 accT = float3(0, 0, 0);

    for (int i = 0; i < 4; i++)
    {
        float weight = vWeights[i];
        if (weight <= 0.0001) continue;

        int bID = vIndices[i]; 
        float3 modPos = vPos; 

        uint ptr = 0; 
        
        for (int layer = 0; layer < 10; layer++)
        {
            float4 header = DataBuffer.Load(ptr);
            
            // Защита: проверяем маркер 69 (теперь надежно)
            if (header.x < 68.5 || header.x > 69.5) break; 

            uint boneCount = (uint)(header.y + 0.1);
            float varSlot = header.z;

            float3 globalHead = DataBuffer.Load(ptr + 1).xyz;
            float3 bone_X = DataBuffer.Load(ptr + 2).xyz;
            float3 bone_Y = DataBuffer.Load(ptr + 3).xyz;
            float3 bone_Z = normalize(cross(bone_X, bone_Y));
            
            // ВОЗВРАЩАЕМ: теперь масштаб снова зависит от IniParams
            float lerpFact = GetVar((int)varSlot);

                for (uint j = 0; j < boneCount; j++)
                {
                    uint bPtr = ptr + 4 + j * 3;
                    float4 bData1 = DataBuffer.Load(bPtr);

                    // Защита: мягкое сравнение ID кости
                    if (abs(bData1.w - (float)bID) < 0.1)
                    {
                        float4 bData2 = DataBuffer.Load(bPtr + 1);
                        float4 bData3 = DataBuffer.Load(bPtr + 2);

                        float3 targetScale = bData1.xyz;
                        float3 targetOffset = bData2.xyz;
                        float3 targetRot = bData3.xyz;

                        float3 s = lerp(float3(1,1,1), targetScale, lerpFact);
                        float3 tOffset = lerp(float3(0,0,0), targetOffset, lerpFact);
                        float3 tRot = lerp(float3(0,0,0), targetRot, lerpFact);

                        float3 p = modPos - globalHead;
                        
                        float3 local_p;
                        local_p.x = dot(p, bone_X);
                        local_p.y = dot(p, bone_Y);
                        local_p.z = dot(p, bone_Z);

                        // 1. Scale
                        local_p *= s;

                        // 2. Rotate (Euler)
                        float cx = cos(tRot.x), sx = sin(tRot.x);
                        float cy = cos(tRot.y), sy = sin(tRot.y);
                        float cz = cos(tRot.z), sz = sin(tRot.z);

                        // X-axis rot
                        float3 p1 = local_p;
                        p1.y = local_p.y * cx - local_p.z * sx;
                        p1.z = local_p.y * sx + local_p.z * cx;

                        // Y-axis rot
                        float3 p2 = p1;
                        p2.x = p1.x * cy + p1.z * sy;
                        p2.z = -p1.x * sy + p1.z * cy;

                        // Z-axis rot
                        float3 p3 = p2;
                        p3.x = p2.x * cz - p2.y * sz;
                        p3.y = p2.x * sz + p2.y * cz;

                        local_p = p3;

                        // 3. Offset
                        local_p += tOffset;

                        // Project back
                        modPos = globalHead + (local_p.x * bone_X) + (local_p.y * bone_Y) + (local_p.z * bone_Z);
                        
                        break; 
                    }
                }
            ptr += 4 + boneCount * 3; 
        }

        // Стандартный скиннинг
        int bIdx = bID * 3;
        float4 r0 = BoneBuffer.Load(bIdx + 0);
        float4 r1 = BoneBuffer.Load(bIdx + 1);
        float4 r2 = BoneBuffer.Load(bIdx + 2);

        float4 p4 = float4(modPos, 1.0);
        oPos.x += dot(p4, r0) * weight;
        oPos.y += dot(p4, r1) * weight;
        oPos.z += dot(p4, r2) * weight;

        accN.x += dot(vNormal, r0.xyz) * weight;
        accN.y += dot(vNormal, r1.xyz) * weight;
        accN.z += dot(vNormal, r2.xyz) * weight;

        accT.x += dot(vTangent.xyz, r0.xyz) * weight;
        accT.y += dot(vTangent.xyz, r1.xyz) * weight;
        accT.z += dot(vTangent.xyz, r2.xyz) * weight;
    }

    oNormal = normalize(accN);
    oTangent = float4(normalize(accT), vTangent.w);
}