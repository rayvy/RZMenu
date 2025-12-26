RWBuffer<float4> Output : register(u0);
cbuffer cb1 : register(b1)
{
  float4 cb1[29];
}
#define NOISE_THRESHOLD 0.01

[numthreads(1, 1, 1)]
void main()
{
  float4 current_pos = cb1[0];
  float4 previous_pos = Output[0];
  float distance_val = distance(current_pos.xyz, previous_pos.xyz);
  if (distance_val < NOISE_THRESHOLD)
  {
    distance_val = 0.0;
  }
  Output[0] = current_pos;
  Output[1] = previous_pos;
  Output[2] = distance_val*100;
}