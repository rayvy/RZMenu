// rzm_object_detect.hlsl
// RZMenu: component-level cursor hit detector driven by GS calibration probe.
//
// Expected bindings:
//   cs-t0 = vertex buffer, stride 40: float3 position, float3 normal, float4 tangent
//   cs-t1 = index buffer, R32_UINT
//   cs-t2 = component ObjectMap, Buffer<float4>
//   cs-t3 = ResourceRZMBakeRT, 8x2 R32G32B32A32_FLOAT
//           row 0: clip.xyzw per calibration sample
//           row 1: vertexIndex, sampleSlot, 0, valid
//   cs-u0 = RWBuffer<float4>, closest-hit accumulator
//
// No cb slot discovery is used. A local->clip transform is reconstructed from
// 4 non-coplanar GS-captured samples and then applied to all vertices in CS.

#define THREADS_PER_GROUP 128u
#define MAX_OBJECTS       256u
#define CALIB_SAMPLES     8u
#define RZM_DETECT_LAYOUT_VERSION 5.1f

struct VertexAttributes
{
    float3 position;
    float3 normal;
    float4 tangent;
};

struct HitPayload
{
    float4 slot1;
    float4 slot2;
    float4 slot3;
    float4 slot4;
    float4 slot5;
    float4 slot6;
    float4 slot7;
};

struct Calibration
{
    float3 p0;
    float3 p1;
    float3 p2;
    float3 p3;
    float4 c0;
    float4 c1;
    float4 c2;
    float4 c3;
    float  invDet;
    float  valid;
};

StructuredBuffer<VertexAttributes> gVB0         : register(t0);
Buffer<uint>                       gIndexBuffer : register(t1);
Buffer<float4>                     gObjectMap   : register(t2);
Texture2D<float4>                  gCalibTex    : register(t3);
RWBuffer<float4>                   gBestHit     : register(u0);

Texture1D<float4> IniParams : register(t120);

#define CURSOR_PARAMS IniParams[24]
#define CLICK_PARAMS  IniParams[25]
#define DETECT_PARAMS IniParams[26]
#define ALT_CURSOR_PARAMS IniParams[27]

groupshared float  sBestDepth[THREADS_PER_GROUP];
groupshared float  sBestID[THREADS_PER_GROUP];
groupshared float  sBestFirstIndex[THREADS_PER_GROUP];
groupshared float  sHitCount[THREADS_PER_GROUP];
groupshared float4 sSlot1[THREADS_PER_GROUP];
groupshared float4 sSlot2[THREADS_PER_GROUP];
groupshared float4 sSlot3[THREADS_PER_GROUP];
groupshared float4 sSlot4[THREADS_PER_GROUP];
groupshared float4 sSlot5[THREADS_PER_GROUP];
groupshared float4 sSlot6[THREADS_PER_GROUP];
groupshared float4 sSlot7[THREADS_PER_GROUP];

float Det3(float3 a, float3 b, float3 c)
{
    return dot(a, cross(b, c));
}

float2 CursorUVFromParams(float4 cursorParams)
{
    float2 screenRes = max(cursorParams.zw, float2(1.0f, 1.0f));
    float2 cursor = cursorParams.xy;
    if (cursor.x > 1.0f || cursor.y > 1.0f)
        cursor /= screenRes;
    return saturate(cursor);
}

bool NormalizedCursorValid(float4 cursorParams)
{
    return cursorParams.z > 0.0f
        && cursorParams.w > 0.0f
        && cursorParams.x > 0.0f
        && cursorParams.y > 0.0f
        && cursorParams.x < 1.0f
        && cursorParams.y < 1.0f;
}

bool ReadCalibSample(uint slot, out float3 localPos, out float4 clipPos)
{
    localPos = float3(0.0f, 0.0f, 0.0f);
    clipPos = float4(0.0f, 0.0f, 0.0f, 0.0f);

    float4 clip = gCalibTex.Load(int3(slot, 0, 0));
    float4 meta = gCalibTex.Load(int3(slot, 1, 0));

    if (meta.w < 0.5f || abs(meta.y - (float)slot) > 0.5f)
        return false;

    uint vertexIndex = (uint)(meta.x + 0.5f);

    uint vertexCount;
    uint vertexStride;
    gVB0.GetDimensions(vertexCount, vertexStride);
    if (vertexIndex >= vertexCount)
        return false;

    if (!all(abs(clip) < float4(1000000.0f, 1000000.0f, 1000000.0f, 1000000.0f)))
        return false;

    if (abs(clip.w) <= 1e-5f)
        return false;

    localPos = gVB0[vertexIndex].position;
    clipPos = clip;
    return true;
}

void SelectCalibration(out Calibration cal)
{
    float3 p[CALIB_SAMPLES];
    float4 c[CALIB_SAMPLES];
    float  v[CALIB_SAMPLES];

    [unroll]
    for (uint i = 0u; i < CALIB_SAMPLES; ++i)
    {
        v[i] = ReadCalibSample(i, p[i], c[i]) ? 1.0f : 0.0f;
    }

    float bestVol = 0.0f;
    uint bestA = 0u;
    uint bestB = 1u;
    uint bestC = 2u;
    uint bestD = 3u;

    [loop]
    for (uint a = 0u; a < CALIB_SAMPLES - 3u; ++a)
    {
        [loop]
        for (uint b = a + 1u; b < CALIB_SAMPLES - 2u; ++b)
        {
            [loop]
            for (uint cc = b + 1u; cc < CALIB_SAMPLES - 1u; ++cc)
            {
                [loop]
                for (uint d = cc + 1u; d < CALIB_SAMPLES; ++d)
                {
                    float valid = v[a] * v[b] * v[cc] * v[d];
                    float3 e1 = p[b] - p[a];
                    float3 e2 = p[cc] - p[a];
                    float3 e3 = p[d] - p[a];
                    float vol = abs(Det3(e1, e2, e3)) * valid;

                    if (vol > bestVol)
                    {
                        bestVol = vol;
                        bestA = a;
                        bestB = b;
                        bestC = cc;
                        bestD = d;
                    }
                }
            }
        }
    }

    cal.p0 = p[bestA];
    cal.p1 = p[bestB];
    cal.p2 = p[bestC];
    cal.p3 = p[bestD];
    cal.c0 = c[bestA];
    cal.c1 = c[bestB];
    cal.c2 = c[bestC];
    cal.c3 = c[bestD];

    float det = Det3(cal.p1 - cal.p0, cal.p2 - cal.p0, cal.p3 - cal.p0);
    cal.valid = bestVol > 1e-8f && abs(det) > 1e-8f ? 1.0f : 0.0f;
    cal.invDet = cal.valid > 0.5f ? rcp(det) : 0.0f;
}

float4 LocalToClip(Calibration cal, float3 localPos)
{
    float3 e1 = cal.p1 - cal.p0;
    float3 e2 = cal.p2 - cal.p0;
    float3 e3 = cal.p3 - cal.p0;
    float3 d = localPos - cal.p0;

    float b1 = Det3(d, e2, e3) * cal.invDet;
    float b2 = Det3(e1, d, e3) * cal.invDet;
    float b3 = Det3(e1, e2, d) * cal.invDet;
    float b0 = 1.0f - b1 - b2 - b3;

    return cal.c0 * b0 + cal.c1 * b1 + cal.c2 * b2 + cal.c3 * b3;
}

bool ClipToScreenUV(float4 clipPos, out float2 uv, out float depth)
{
    uv = float2(0.0f, 0.0f);
    depth = 3.402823e+38f;

    if (clipPos.w <= 1e-5f)
        return false;

    float2 ndc = clipPos.xy / clipPos.w;
    uv = float2(ndc.x * 0.5f + 0.5f, 0.5f - ndc.y * 0.5f);
    depth = 1.0f - clipPos.z / clipPos.w;

    return all(abs(ndc) < float2(1000.0f, 1000.0f)) && abs(depth) < 1000.0f;
}

float Cross2(float2 a, float2 b)
{
    return a.x * b.y - a.y * b.x;
}

float3 Barycentric2D(float2 p, float2 a, float2 b, float2 c)
{
    float2 v0 = b - a;
    float2 v1 = c - a;
    float2 v2 = p - a;
    float d00 = dot(v0, v0);
    float d01 = dot(v0, v1);
    float d11 = dot(v1, v1);
    float d20 = dot(v2, v0);
    float d21 = dot(v2, v1);
    float denom = d00 * d11 - d01 * d01;

    if (abs(denom) <= 1e-12f)
        return float3(1.0f, 0.0f, 0.0f);

    float v = (d11 * d20 - d01 * d21) / denom;
    float w = (d00 * d21 - d01 * d20) / denom;
    return float3(1.0f - v - w, v, w);
}

bool PointInTriangle(float2 p, float2 a, float2 b, float2 c)
{
    float e0 = Cross2(b - a, p - a);
    float e1 = Cross2(c - b, p - b);
    float e2 = Cross2(a - c, p - c);
    bool hasNeg = (e0 < 0.0f) || (e1 < 0.0f) || (e2 < 0.0f);
    bool hasPos = (e0 > 0.0f) || (e1 > 0.0f) || (e2 > 0.0f);
    return !(hasNeg && hasPos);
}

float DistSqPointSegment(float2 p, float2 a, float2 b, out float t)
{
    float2 ab = b - a;
    float denom = max(dot(ab, ab), 1e-10f);
    t = saturate(dot(p - a, ab) / denom);
    float2 d = p - (a + ab * t);
    return dot(d, d);
}

bool CursorHitsTriangle(
    float2 cursor,
    float2 a,
    float2 b,
    float2 c,
    float padUV,
    out float3 bary,
    out float inside)
{
    bary = float3(0.0f, 0.0f, 0.0f);
    inside = 0.0f;

    float2 pad = float2(padUV, padUV);
    float2 mn = min(a, min(b, c)) - pad;
    float2 mx = max(a, max(b, c)) + pad;

    if (any(cursor < mn) || any(cursor > mx))
        return false;

    if (PointInTriangle(cursor, a, b, c))
    {
        bary = Barycentric2D(cursor, a, b, c);
        inside = 1.0f;
        return true;
    }

    float tAB, tBC, tCA;
    float dAB = DistSqPointSegment(cursor, a, b, tAB);
    float dBC = DistSqPointSegment(cursor, b, c, tBC);
    float dCA = DistSqPointSegment(cursor, c, a, tCA);
    float bestD = min(dAB, min(dBC, dCA));

    if (bestD > padUV * padUV)
        return false;

    if (bestD == dAB)
        bary = float3(1.0f - tAB, tAB, 0.0f);
    else if (bestD == dBC)
        bary = float3(0.0f, 1.0f - tBC, tBC);
    else
        bary = float3(tCA, 0.0f, 1.0f - tCA);

    return true;
}

uint NearestVertexSlot(float2 cursor, float2 s0, float2 s1, float2 s2, out float distSq)
{
    float d0 = dot(cursor - s0, cursor - s0);
    float d1 = dot(cursor - s1, cursor - s1);
    float d2 = dot(cursor - s2, cursor - s2);

    distSq = min(d0, min(d1, d2));
    if (distSq == d0)
        return 0u;
    if (distSq == d1)
        return 1u;
    return 2u;
}

float3 SelectVertexPosition(uint slot, float3 p0, float3 p1, float3 p2)
{
    if (slot == 0u)
        return p0;
    if (slot == 1u)
        return p1;
    return p2;
}

uint SelectVertexIndex(uint slot, uint i0, uint i1, uint i2)
{
    if (slot == 0u)
        return i0;
    if (slot == 1u)
        return i1;
    return i2;
}

float3 SafeNormalize(float3 v)
{
    float lenSq = dot(v, v);
    if (lenSq <= 1e-20f)
        return float3(0.0f, 0.0f, 1.0f);
    return v * rsqrt(lenSq);
}

void InitPayload(out HitPayload payload)
{
    payload.slot1 = float4(0.0f, 0.0f, 0.0f, 0.0f);
    payload.slot2 = float4(0.0f, 0.0f, 0.0f, 0.0f);
    payload.slot3 = float4(0.0f, 0.0f, 0.0f, 0.0f);
    payload.slot4 = float4(0.0f, 0.0f, 0.0f, 0.0f);
    payload.slot5 = float4(0.0f, 0.0f, 1.0f, 0.0f);
    payload.slot6 = float4(0.0f, 0.0f, 0.0f, 0.0f);
    payload.slot7 = float4(RZM_DETECT_LAYOUT_VERSION, 0.0f, 0.0f, 0.0f);
}

void TestTriangleRange(
    Calibration cal,
    uint tid,
    uint objectIndex,
    uint objectCount,
    uint firstIndex,
    uint indexCount,
    float objectMode,
    float objectID,
    float2 primaryCursor,
    float2 altCursor,
    bool useAltCursor,
    float padUV,
    inout float bestDepth,
    inout float bestID,
    inout float bestFirstIndex,
    inout float hitCount,
    inout HitPayload payload)
{
    uint triangleCount = indexCount / 3u;

    [loop]
    for (uint tri = tid; tri < triangleCount; tri += THREADS_PER_GROUP)
    {
        uint indexBase = firstIndex + tri * 3u;
        uint i0 = gIndexBuffer[indexBase + 0u];
        uint i1 = gIndexBuffer[indexBase + 1u];
        uint i2 = gIndexBuffer[indexBase + 2u];

        float3 p0 = gVB0[i0].position;
        float3 p1 = gVB0[i1].position;
        float3 p2 = gVB0[i2].position;

        float2 s0, s1, s2;
        float d0, d1, d2;
        bool ok0 = ClipToScreenUV(LocalToClip(cal, p0), s0, d0);
        bool ok1 = ClipToScreenUV(LocalToClip(cal, p1), s1, d1);
        bool ok2 = ClipToScreenUV(LocalToClip(cal, p2), s2, d2);

        float3 primaryBary = float3(0.0f, 0.0f, 0.0f);
        float primaryInside = 0.0f;
        float3 altBary = float3(0.0f, 0.0f, 0.0f);
        float altInside = 0.0f;
        bool primaryHit = false;
        bool altHit = false;

        if (ok0 && ok1 && ok2)
        {
            primaryHit = CursorHitsTriangle(primaryCursor, s0, s1, s2, padUV, primaryBary, primaryInside);
            altHit = useAltCursor && CursorHitsTriangle(altCursor, s0, s1, s2, padUV, altBary, altInside);
        }

        if (primaryHit || altHit)
        {
            float2 cursor = altHit ? altCursor : primaryCursor;
            float3 bary = altHit ? altBary : primaryBary;
            float inside = altHit ? altInside : primaryInside;

            hitCount += 1.0f;
            float triDepth = min(d0, min(d1, d2));
            if (triDepth < bestDepth)
            {
                float nearestDistSq;
                uint nearestSlot = NearestVertexSlot(cursor, s0, s1, s2, nearestDistSq);
                float3 faceNormal = SafeNormalize(cross(p1 - p0, p2 - p0));
                float winding = Cross2(s1 - s0, s2 - s0) < 0.0f ? -1.0f : 1.0f;

                bestDepth = triDepth;
                bestID = objectID;
                bestFirstIndex = (float)firstIndex;

                payload.slot1 = float4(p0 * bary.x + p1 * bary.y + p2 * bary.z, objectMode);
                payload.slot2 = float4((float)firstIndex, (float)indexBase, (float)tri, (float)(indexBase / 3u));
                payload.slot3 = float4((float)i0, (float)i1, (float)i2, (float)nearestSlot);
                payload.slot4 = float4(bary, inside);
                payload.slot5 = float4(faceNormal, winding);
                payload.slot6 = float4(SelectVertexPosition(nearestSlot, p0, p1, p2), nearestDistSq);
                payload.slot7 = float4(RZM_DETECT_LAYOUT_VERSION, (float)objectIndex, (float)objectCount, (float)SelectVertexIndex(nearestSlot, i0, i1, i2));
            }
        }
    }
}

[numthreads(THREADS_PER_GROUP, 1, 1)]
void main(uint3 dispatchThreadID : SV_DispatchThreadID,
          uint3 groupThreadID    : SV_GroupThreadID)
{
    uint tid = groupThreadID.x;

    Calibration cal;
    SelectCalibration(cal);

    float bestDepth = 3.402823e+38f;
    float bestID = -1.0f;
    float bestFirstIndex = 0.0f;
    float hitCount = 0.0f;
    HitPayload payload;
    InitPayload(payload);

    if (cal.valid > 0.5f)
    {
        uint objectCount = (uint)min(max(gObjectMap[0u].x, 0.0f), (float)MAX_OBJECTS);
        float2 primaryCursor = CursorUVFromParams(CURSOR_PARAMS);
        float2 altCursor = CursorUVFromParams(ALT_CURSOR_PARAMS);
        bool useAltCursor = NormalizedCursorValid(ALT_CURSOR_PARAMS);
        float2 screenRes = max(CURSOR_PARAMS.zw, float2(1.0f, 1.0f));
        float hitPadPixels = max(DETECT_PARAMS.w, 0.0f);
        float padUV = hitPadPixels / max(screenRes.x, screenRes.y);
        bool isClicked = CLICK_PARAMS.x > 0.0f;

        [loop]
        for (uint objectIndex = 0u; objectIndex < objectCount; objectIndex++)
        {
            float4 entry = gObjectMap[1u + objectIndex];
            uint firstIndex = (uint)max(entry.x, 0.0f);
            uint indexCount = (uint)max(entry.y, 0.0f);
            float objectMode = entry.z;
            float objectID = entry.w > 0.0f ? entry.w : (float)firstIndex;

            bool isHoverType = (objectMode <= 3.0f) || (objectMode == 7.0f) || (objectMode == 8.0f);
            bool isClickType = (objectMode >= 4.0f && objectMode <= 6.0f);
            bool shouldProcess = isHoverType || (isClickType && isClicked);

            if (shouldProcess && indexCount >= 3u)
            {
                TestTriangleRange(
                    cal, tid, objectIndex, objectCount,
                    firstIndex, indexCount, objectMode, objectID,
                    primaryCursor, altCursor, useAltCursor, padUV,
                    bestDepth, bestID, bestFirstIndex, hitCount,
                    payload);
            }
        }
    }

    sBestDepth[tid] = bestDepth;
    sBestID[tid] = bestID;
    sBestFirstIndex[tid] = bestFirstIndex;
    sHitCount[tid] = hitCount;
    sSlot1[tid] = payload.slot1;
    sSlot2[tid] = payload.slot2;
    sSlot3[tid] = payload.slot3;
    sSlot4[tid] = payload.slot4;
    sSlot5[tid] = payload.slot5;
    sSlot6[tid] = payload.slot6;
    sSlot7[tid] = payload.slot7;
    GroupMemoryBarrierWithGroupSync();

    for (uint stride = THREADS_PER_GROUP / 2u; stride > 0u; stride >>= 1u)
    {
        if (tid < stride)
        {
            sHitCount[tid] += sHitCount[tid + stride];
            if (sBestDepth[tid + stride] < sBestDepth[tid])
            {
                sBestDepth[tid] = sBestDepth[tid + stride];
                sBestID[tid] = sBestID[tid + stride];
                sBestFirstIndex[tid] = sBestFirstIndex[tid + stride];
                sSlot1[tid] = sSlot1[tid + stride];
                sSlot2[tid] = sSlot2[tid + stride];
                sSlot3[tid] = sSlot3[tid + stride];
                sSlot4[tid] = sSlot4[tid + stride];
                sSlot5[tid] = sSlot5[tid + stride];
                sSlot6[tid] = sSlot6[tid + stride];
                sSlot7[tid] = sSlot7[tid + stride];
            }
        }
        GroupMemoryBarrierWithGroupSync();
    }

    if (tid == 0u && sBestID[0] >= 0.0f)
    {
        float4 previous = gBestHit[0];
        bool previousInvalid = previous.x < 0.0f || previous.y > 1e30f;

        if (previousInvalid || sBestDepth[0] < previous.y)
        {
            gBestHit[1] = sSlot1[0];
            gBestHit[2] = sSlot2[0];
            gBestHit[3] = sSlot3[0];
            gBestHit[4] = sSlot4[0];
            gBestHit[5] = sSlot5[0];
            gBestHit[6] = sSlot6[0];
            gBestHit[7] = sSlot7[0];
            gBestHit[0] = float4(sBestID[0], sBestDepth[0], sBestFirstIndex[0], sHitCount[0]);
        }
    }
}
