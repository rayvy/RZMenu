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
    report.append("XXMI METADATA ARCHITECTURE UNIT TEST (V11.0 SHARED BUFFER)")
    report.append(f"Source: {input_path}")
    report.append("=" * 70 + "\n")

    # Mapping structure: { classification: { base_name: full_info } }
    # This allows resolving "Head" if we know the parent is "WhiteBody"
    hierarchical_mapping = {}
    component_summaries = []

    for i, item in enumerate(data):
        base_name = item.get("component_name", f"Component{i}")
        classifications = item.get("object_classifications", [])
        
        comp_info = {
            "index": i,
            "base_name": base_name,
            "shared_buffer": f"{base_name}Position.buf",
            "materials": classifications if classifications else ["Single"]
        }
        component_summaries.append(comp_info)

        # Map base name
        hierarchical_mapping.setdefault(base_name.lower(), {})[base_name.lower()] = f"Component{i}"
        
        # Map classifications
        for cls in classifications:
            cls_low = cls.lower()
            # Link classification to its base component
            hierarchical_mapping.setdefault(cls_low, {})[base_name.lower()] = f"Component{i}{cls}"

    # Simulation of find_component_mapping(obj_name, parent_collection_name)
    def simulate_find(coll_name, parent_coll_name=None):
        coll_low = coll_name.lower()
        if coll_low not in hierarchical_mapping:
            return None, "Not Found"
        
        matches = hierarchical_mapping[coll_low]
        if len(matches) == 1:
            return list(matches.values())[0], "Direct Match"
        
        # Ambiguity! e.g. "Head" in "WhiteBody" vs "Limbs"
        if parent_coll_name:
            parent_low = parent_coll_name.lower()
            if parent_low in matches:
                return matches[parent_low], f"Resolved via Parent ({parent_low})"
            
            # Try matching parent against base names in matches
            for base_name in matches:
                if base_name in parent_low:
                     return matches[base_name], f"Resolved via Parent Match ({base_name})"
        
        return list(matches.values())[0], "Ambiguous (Defaulted to First)"

    # Generate Report
    for comp in component_summaries:
        report.append(f"[{comp['index']}] Logical Component: '{comp['base_name']}'")
        report.append(f"    Shared Position Buffer: {comp['shared_buffer']}")
        if comp['materials'] == ["Single"]:
             report.append(f"    Status: Single Material")
        else:
             report.append(f"    Status: Multi-Material ({len(comp['materials'])} parts)")
             report.append(f"    Materials: {', '.join(comp['materials'])}")
        report.append("-" * 40)

    report.append(f"\nSIMULATION: AMBIGUITY RESOLUTION")
    test_cases = [
        ("Hair", None),
        ("Head", "WhiteBody"),
        ("Head", "Limbs"),
        ("Head", "BlackBody"),
        ("Dress", "BlackBody"),
    ]
    
    for coll, parent in test_cases:
        res, msg = simulate_find(coll, parent)
        report.append(f"  Collection: '{coll}' (Parent: '{parent}') -> Result: {res} [{msg}]")

    report.append("\n" + "=" * 70)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(report))

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
