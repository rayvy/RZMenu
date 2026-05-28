# inspect_qa.py
import os
import json
import struct

qa_dir = r"c:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\RZMenu\QA"
cache_path = os.path.join(qa_dir, "test_scene.json")

print("--- Cache Inspection ---")
if os.path.exists(cache_path):
    with open(cache_path, 'r', encoding='utf-8') as f:
        cache_data = json.load(f)
    comp_cache = cache_data.get('components', {}).get('Hair', {})
    print("Hair Component Cache:")
    print(f"  n_verts: {comp_cache.get('n_verts')}")
    print("  Objects:")
    for obj in comp_cache.get('objects', []):
        print(f"    Name: {obj.get('name')}, ib_count: {obj.get('ib_count')}")
else:
    print("Cache file not found.")

print("\n--- IB Files Inspection ---")
no_curves_ib = os.path.join(qa_dir, "NoCurves", "PromeiaHairB.ib")
with_curves_ib = os.path.join(qa_dir, "WithCurves", "PromeiaHairB.ib")

if os.path.exists(no_curves_ib):
    print(f"NoCurves/PromeiaHairB.ib size: {os.path.getsize(no_curves_ib)} bytes")
if os.path.exists(with_curves_ib):
    print(f"WithCurves/PromeiaHairB.ib size: {os.path.getsize(with_curves_ib)} bytes")
