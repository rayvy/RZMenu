struct VertexAttributes {
    float3 position;
    float3 normal;
    float4 tangent;
};

RWStructuredBuffer<VertexAttributes> rw_buffer : register(u5);
StructuredBuffer<VertexAttributes> base : register(t50);
StructuredBuffer<VertexAttributes> shapekey : register(t51);

Texture1D<float4> IniParams : register(t120);
#define FREQ IniParams[88].x
static const float PI = 3.14159265359;

// Кривая морфинга — piecewise: 4 качели -> spike -> normalize -> hold(1.0)
float MorphCurve(float t)
{
    const float stageCyclesEnd = 0.65;   // 0..0.5 — четыре качельки с ростом до 0.35
    const float stageSpikeEnd  = 0.70;   // 0.5..0.7 — резкий рост до 1.2 (разрыв)
    const float stageNormEnd   = 0.95;   // 0.7..0.85 — возврат к 1.0
    const float ampMax = 0.35;           // максимальная амплитуда пред-спайка

    if (t < stageCyclesEnd)
    {
        float local = t / stageCyclesEnd; // 0..1 по всему блоку
        float cycles = 4.0;               // 4 повторения
        // float amp = ampMax * local;       // постепенно растущая амплитуда
        float amp = lerp(0.0, 0.15, local); // вместо роста до 0.35, фиксируем потолок
        // sin даёт волны 0..amp (sin->-1..1 -> ((sin+1)/2)*amp)
        float s = sin(local * cycles * 2.0 * PI);
        float base = amp * 0.5 * (s + 1.0);
        return base;
    }
    else if (t < stageSpikeEnd)
    {
        float local = (t - stageCyclesEnd) / (stageSpikeEnd - stageCyclesEnd); // 0..1
        // ускоренное вхождение в пик: ease-in (quad)
        float start = ampMax;
        float end   = 1.2;
        float eased = start + (end - start) * (local * local);
        return eased;
    }
    else if (t < stageNormEnd)
    {
        float local = (t - stageSpikeEnd) / (stageNormEnd - stageSpikeEnd); // 0..1
        // мягкий ease-out (cubic) от 1.2 к 1.0
        float inv = 1.0 - local;
        float ease = 1.0 - inv * inv * inv;
        float val = lerp(1.2, 1.0, ease);
        return val;
    }
    else
    {
        return 1.0;
    }
}

[numthreads(1, 1, 1)]
void main(uint3 threadID : SV_DispatchThreadID)
{
    uint i = threadID.x;

    VertexAttributes diff;
    diff.position = shapekey[i].position - base[i].position;
    diff.normal   = shapekey[i].normal - base[i].normal;
    diff.tangent  = shapekey[i].tangent - base[i].tangent;

    float t = saturate(FREQ);
    float k = MorphCurve(t);

    // Применяем обычный морф (позиция/нормаль/тангент)
    rw_buffer[i].position += diff.position * k;
    rw_buffer[i].normal   += diff.normal   * k;
    rw_buffer[i].tangent  += diff.tangent  * k;

    // ========== JIGGLE (вертикальное смещение Y) ==========
    // Условие запуска: t в указанном окне
    const float jiggleT0 = 0.65;
    const float jiggleT1 = 0.95;

    if (t >= jiggleT0 && t <= jiggleT1)
    {
        // защита / fallback-значения
        float maxDiff = 40;
        if (maxDiff <= 1e-5) maxDiff = 0.20;        // рекомендую ~0.1-0.3
        float jStrength = 10;
        if (jStrength <= 0.0) jStrength = 0.12;     // базовая сила jiggle
        float jCycles = 8;
        if (jCycles <= 0.0) jCycles = 12.0;         // сколько синусов поместить в окне

        // амплитуда зависит от величины diff (если diff==0 -> ничего не двигается)
        float diffMag = length(diff.position);      // magnitude of position change
        float ampScale = saturate(diffMag / maxDiff);

        // локальная координата внутри jiggle-окна 0..1
        float localJ = (t - jiggleT0) / (jiggleT1 - jiggleT0);

        // огибающая: начинается заметно и затухает к концу окна
        // тут квадратичное затухание, можно заменить на exp() для иного поведения
        float envelope = (1.0 - localJ) * (1.0 - localJ);

        // волна: быстрое колебание внутри окна
        float wave = sin(localJ * jCycles * 2.0 * PI);

        // итоговое вертикальное смещение (up/down)
        float vertOffset = wave * envelope * ampScale * jStrength;

        // если хочешь, чтобы величина вертикального смещения была связана с вертикальной частью диффа,
        // можно умножить на sign(diff.position.y) или на abs(diff.position.y/maxDiff). Сейчас - независимое up/down.
        rw_buffer[i].position.y += vertOffset;
    }
}
