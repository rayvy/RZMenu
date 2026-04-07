import struct
import unittest
import os

file1 = r"G:\XXMI\EFMI\Mods\YvonneCasualX\Meshes\Component6_VB0.buf"
file2 = r"G:\XXMI\EFMI\Mods\YvonneCasualX\Blend\Component6_VB0_Sport.buf"

class TestBufferIntegrity(unittest.TestCase):
    def setUp(self):
        self.stride = 16
        with open(file1, "rb") as f1:
            self.d1 = f1.read()
        with open(f2_path if 'f2_path' in globals() else file2, "rb") as f2:
            self.d2 = f2.read()

    def test_size_parity(self):
        """Original and modified buffers must have identical sizes."""
        self.assertEqual(len(self.d1), len(self.d2), "Buffer sizes mismatch!")

    def test_stride_alignment(self):
        """Buffer size must be a multiple of the stride (16 bytes)."""
        self.assertEqual(len(self.d1) % self.stride, 0, f"Original buffer size {len(self.d1)} not multiple of {self.stride}")
        self.assertEqual(len(self.d2) % self.stride, 0, f"Modified buffer size {len(self.d2)} not multiple of {self.stride}")

    def test_invariant_data(self):
        """Non-position data (last 4 bytes of each 16-byte stride) must remain unchanged."""
        vertex_count = len(self.d1) // self.stride
        for i in range(vertex_count):
            offset = i * self.stride
            rest1 = self.d1[offset+12:offset+16]
            rest2 = self.d2[offset+12:offset+16]
            self.assertEqual(rest1, rest2, f"Data corruption at vertex {i} (non-position bytes changed)")

    def test_valid_displacement(self):
        """Vertex positions should not jump over a plausible limit unless intended."""
        # 0.5 units is a massive reasonable limit for a shapekey. 
        # The tool limit is 0.0005, but here we check for 'sanity' (e.g. 10.0 jump).
        sanity_limit = 1.0
        vertex_count = len(self.d1) // self.stride
        for i in range(vertex_count):
            offset = i * self.stride
            v1 = struct.unpack_from("<3f", self.d1, offset)
            v2 = struct.unpack_from("<3f", self.d2, offset)
            dist = sum((a-b)**2 for a, b in zip(v1, v2))**0.5
            self.assertLess(dist, sanity_limit, f"Extreme displacement at vertex {i}: {dist:.4f}")

if __name__ == "__main__":
    unittest.main()
