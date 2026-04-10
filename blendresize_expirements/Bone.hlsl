Buffer<float4> t0 : register(t0); // Bone Matrices
Buffer<float4> t1 : register(t1); // Extra params (bonescount)

#define cmp -
Texture1D<float4> IniParams : register(t120);
Texture2D<float4> StereoParams : register(t125);

void main(
  float3 v0 : POSITION0,
  float3 v1 : NORMAL0,
  float4 v2 : TANGENT0,
  float4 v3 : BLENDWEIGHT0,
  int4 v4 : BLENDINDICES0,
  out float3 o0 : POSITION0,
  out float3 o1 : TEXCOORD0,
  out float4 o2 : TEXCOORD1)
{
  float4 r0, r1, r2, r3, r4, r5;
  o0 = float3(0, 0, 0);

  // --- Настройки ресайза ---
  // Вектор (X, Y, Z). 1.0 = без изменений.
  float3 scale_wide = float3(1.5, 1.0, 1.5); // "Раздувание" вширь
  float3 scale_full = float3(1.3, 1.3, 1.3); // Полное увеличение
  
  float3 s[4]; // Множители для 4 влияющих костей

  // Заполняем веса масштабирования для каждой кости из v4
  int indices[4] = {v4.x, v4.y, v4.z, v4.w};
  
  [unroll]
  for(int i = 0; i < 4; i++) {
    if (indices[i] >= 0 && indices[i] <= 10) {
      s[i] = scale_wide;
    } else if (indices[i] > 10 && indices[i] <= 25) {
      s[i] = scale_full;
    } else {
      s[i] = float3(1, 1, 1);
    }
  }

  float3 localPos = v0.xyz;

  // --- Расчет X Row ---
  int4 r_idx_x = v4 * 3;
  
  r2 = t0.Load(r_idx_x.x) * v3.x;
  o0.x += dot(float4(localPos * s[0], 1), r2);
  r1 = r2;

  r2 = t0.Load(r_idx_x.y) * v3.y;
  o0.x += dot(float4(localPos * s[1], 1), r2);
  r1 += r2;

  r2 = t0.Load(r_idx_x.z) * v3.z;
  o0.x += dot(float4(localPos * s[2], 1), r2);
  r1 += r2;

  r2 = t0.Load(r_idx_x.w) * v3.w;
  o0.x += dot(float4(localPos * s[3], 1), r2);
  r1 += r2;

  // --- Расчет Y Row ---
  int4 r_idx_y = v4 * 3 + 1;

  r2 = t0.Load(r_idx_y.x) * v3.x;
  o0.y += dot(float4(localPos * s[0], 1), r2);
  r3 = r2;

  r2 = t0.Load(r_idx_y.y) * v3.y;
  o0.y += dot(float4(localPos * s[1], 1), r2);
  r3 += r2;

  r2 = t0.Load(r_idx_y.z) * v3.z;
  o0.y += dot(float4(localPos * s[2], 1), r2);
  r3 += r2;

  r2 = t0.Load(r_idx_y.w) * v3.w;
  o0.y += dot(float4(localPos * s[3], 1), r2);
  r3 += r2;

  // --- Расчет Z Row ---
  int4 r_idx_z = v4 * 3 + 2;

  r2 = t0.Load(r_idx_z.x) * v3.x;
  o0.z += dot(float4(localPos * s[0], 1), r2);
  r5 = r2;

  r2 = t0.Load(r_idx_z.y) * v3.y;
  o0.z += dot(float4(localPos * s[1], 1), r2);
  r5 += r2;

  r2 = t0.Load(r_idx_z.z) * v3.z;
  o0.z += dot(float4(localPos * s[2], 1), r2);
  r5 += r2;

  r2 = t0.Load(r_idx_z.w) * v3.w;
  o0.z += dot(float4(localPos * s[3], 1), r2);
  r5 += r2;

  // --- Трансформация векторов (Нормали и Тангенты) ---
  // Направления не скейлим, только поворачиваем
  o1.x = dot(v1.xyz, r1.xyz);
  o1.y = dot(v1.xyz, r3.xyz);
  o1.z = dot(v1.xyz, r5.xyz);

  o2.x = dot(v2.xyz, r1.xyz);
  o2.y = dot(v2.xyz, r3.xyz);
  o2.z = dot(v2.xyz, r5.xyz);
  o2.w = v2.w;

  return;
}