# RZMenu/tests/test_dds_pack.py
import unittest
import os
import numpy as np
import sys

# Add addon root to sys.path to allow imports
addon_dir = os.path.dirname(os.path.dirname(__file__))
if addon_dir not in sys.path:
    sys.path.append(addon_dir)

from core.dds_packer import pack_to_dds, get_texconv_path

class TestDDSPacking(unittest.TestCase):
    def test_texconv_discovery(self):
        path = get_texconv_path()
        if path:
            print(f"Found texconv at: {path}")
        else:
            print("texconv not found (normal if not installed yet)")

    def test_pack_dummy_dds(self):
        texconv = get_texconv_path()
        if not texconv:
            self.skipTest("texconv.exe not found, skipping actual packing test")
            
        width, height = 256, 256
        # Create a gradient RGBA buffer
        pixels = []
        for y in range(height):
            for x in range(width):
                pixels.extend([x/width, y/height, (x+y)/(width+height), 1.0])
        
        output_path = os.path.join(os.path.dirname(__file__), "test_atlas.dds")
        
        success, msg = pack_to_dds(pixels, width, height, output_path, dds_format='BC7_UNORM')
        
        self.assertTrue(success, f"DDS Packing failed: {msg}")
        self.assertTrue(os.path.exists(output_path), "DDS file was not created")
        
        # Check size (BC7 is 1 byte per pixel for 4x4 blocks? No, 16 bytes per 4x4 block = 1 byte per pixel)
        # 256*256 = 65536 bytes + header
        filesize = os.path.getsize(output_path)
        print(f"Generated DDS size: {filesize} bytes")
        self.assertGreater(filesize, 60000)
        
        # Clean up
        if os.path.exists(output_path):
            os.remove(output_path)

if __name__ == '__main__':
    unittest.main()
