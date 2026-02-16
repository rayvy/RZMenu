// simple_ps-t0_ps-t16_draw.hlsl
Texture2D<float4> tex[17] : register(t0); 
SamplerState s0_s : register(s0);

struct vs2ps {
    float4 pos : SV_Position;
    float2 uv  : TEXCOORD0;
};

#ifdef VERTEX_SHADER
void main(out vs2ps output, uint vertex_id : SV_VertexID) {
    // Генерирует полноэкранный треугольник
    output.uv = float2((vertex_id << 1) & 2, vertex_id & 2);
    output.pos = float4(output.uv * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
}
#endif

#ifdef PIXEL_SHADER
void main(vs2ps input, out float4 result : SV_Target0)
{
    // Всего текстур 17 (от 0 до 16 включительно)
    float num_tiles = 17.0;
    float scaled_x = input.uv.x * num_tiles;
    uint tex_index = (uint)floor(scaled_x);
    
    // Вычисляем локальный UV для конкретного тайла (растягиваем 1/17 часть до 0..1)
    float2 tile_uv = float2(frac(scaled_x), input.uv.y);
    
    // Выбираем текстуру. Switch — самый безопасный способ для разных версий шейдеров.
    [branch]
    switch(tex_index)
    {
        case 0:  result = tex[0].Sample(s0_s, tile_uv); break;
        case 1:  result = tex[1].Sample(s0_s, tile_uv); break;
        case 2:  result = tex[2].Sample(s0_s, tile_uv); break;
        case 3:  result = tex[3].Sample(s0_s, tile_uv); break;
        case 4:  result = tex[4].Sample(s0_s, tile_uv); break;
        case 5:  result = tex[5].Sample(s0_s, tile_uv); break;
        case 6:  result = tex[6].Sample(s0_s, tile_uv); break;
        case 7:  result = tex[7].Sample(s0_s, tile_uv); break;
        case 8:  result = tex[8].Sample(s0_s, tile_uv); break;
        case 9:  result = tex[9].Sample(s0_s, tile_uv); break;
        case 10: result = tex[10].Sample(s0_s, tile_uv); break;
        case 11: result = tex[11].Sample(s0_s, tile_uv); break;
        case 12: result = tex[12].Sample(s0_s, tile_uv); break;
        case 13: result = tex[13].Sample(s0_s, tile_uv); break;
        case 14: result = tex[14].Sample(s0_s, tile_uv); break;
        case 15: result = tex[15].Sample(s0_s, tile_uv); break;
        case 16: result = tex[16].Sample(s0_s, tile_uv); break;
        default: result = float4(0,0,0,1); break;
    }
}
#endif