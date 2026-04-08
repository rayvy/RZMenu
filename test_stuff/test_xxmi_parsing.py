import json
import os

def run_xxmi_metadata_test(input_path, output_path):
    if not os.path.exists(input_path):
        msg = f"ERROR: Input file not found at {input_path}"
        print(msg)
        return

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        msg = f"ERROR: Failed to parse JSON: {e}"
        print(msg)
        return

    report = []
    report.append("=" * 70)
    report.append("XXMI METADATA ARCHITECTURE UNIT TEST")
    report.append(f"Source: {input_path}")
    report.append("=" * 70 + "\n")

    total_buffers = 0
    mapping_summary = {}

    for i, item in enumerate(data):
        comp_name = item.get("component_name", "Unnamed")
        classifications = item.get("object_classifications", [])
        
        report.append(f"[{i}] Logical Component: '{comp_name}'")
        
        if classifications:
            report.append(f"    Structure: Multi-Material (Classified)")
            report.append(f"    Classifications found: {', '.join(classifications)}")
            for cls in classifications:
                # This is the crucial logic for XXMI buffer resolution
                fullname = f"Component{i}{cls}"
                report.append(f"    |-- Material Buffer: {fullname}")
                total_buffers += 1
                mapping_summary[cls.lower()] = fullname
        else:
            # Traditional single material component
            fullname = f"Component{i}"
            report.append(f"    Structure: Single Material")
            report.append(f"    |-- Material Buffer: {fullname}")
            total_buffers += 1
            mapping_summary[comp_name.lower()] = fullname
        
        report.append("-" * 40)

    report.append(f"\nFINAL ARCHITECTURE SUMMARY")
    report.append(f"Total Top-Level Components: {len(data)}")
    report.append(f"Total Logical Material Buffers: {total_buffers}")
    report.append("\n" + "=" * 70)
    report.append("\nINTERNAL MAPPING DICTIONARY (Simulated find_component_mapping):")
    for key, val in sorted(mapping_summary.items()):
        report.append(f"  '{key}' -> {val}")
    report.append("=" * 70)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(report))
    
    print(f"\n[UNIT TEST] Execution complete.")
    print(f"[UNIT TEST] Input: {os.path.basename(input_path)}")
    print(f"[UNIT TEST] Output: {os.path.basename(output_path)}")

if __name__ == "__main__":
    # Absolute paths provided by user
    BASE_DIR = r'c:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\RZMenu\test_stuff'
    INPUT_FILE = os.path.join(BASE_DIR, 'hash.json')
    OUTPUT_FILE = os.path.join(BASE_DIR, 'metadata_report.txt')
    
    run_xxmi_metadata_test(INPUT_FILE, OUTPUT_FILE)
