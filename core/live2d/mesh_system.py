import struct
from dataclasses import dataclass, field
from typing import List, Tuple

@dataclass
class RZMesh:
    element_uid: str
    cols: int = 4
    rows: int = 4
    # List of (local_x, local_y, uv_x, uv_y)
    vertices: List[Tuple[float, float, float, float]] = field(default_factory=list)
    # List of (bone_id0, weight0, bone_id1, weight1, bone_id2, weight2, bone_id3, weight3)
    skin_weights: List[Tuple[float, ...]] = field(default_factory=list)

    def generate_default_grid(self, width: float, height: float):
        """Generates a uniform rectangular grid for the element."""
        self.vertices.clear()
        for r in range(self.rows):
            for c in range(self.cols):
                ux = c / (self.cols - 1) if self.cols > 1 else 0.5
                uy = r / (self.rows - 1) if self.rows > 1 else 0.5
                self.vertices.append((ux * width, uy * height, ux, uy))
        
        # Initialize default weights (none)
        self.skin_weights = [(-1.0, 0.0, -1.0, 0.0, -1.0, 0.0, -1.0, 0.0)] * len(self.vertices)

    def to_vertex_binary(self) -> bytes:
        """Exports vertices to MeshVertexBuffer format (float4 per vertex)."""
        data = bytearray()
        for v in self.vertices:
            data += struct.pack('4f', *v)
        return bytes(data)

    def to_weight_binary(self) -> bytes:
        """Exports skinning weights to SkinWeightBuffer format (2x float4 per vertex)."""
        data = bytearray()
        for w in self.skin_weights:
            # First 4: (b0, w0, b1, w1)
            data += struct.pack('4f', w[0], w[1], w[2], w[3])
            # Second 4: (b2, w2, b3, w3)
            data += struct.pack('4f', w[4], w[5], w[6], w[7])
        return bytes(data)
