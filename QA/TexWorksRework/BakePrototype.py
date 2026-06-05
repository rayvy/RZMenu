import bpy


GROUP_NAME = "RZM TexWorks Material"
TEXTURE_INPUTS = ["Diffuse", "LightMap", "MaterialMap", "NormalMap", "Extra"]
RUNTIME_NAMESPACE_KEY = "rzm_qa_texworks_atlas_runtime"


def iter_rzm_nodes():
    group = bpy.data.node_groups.get(GROUP_NAME)
    if not group:
        return

    for mat in bpy.data.materials:
        if not mat.use_nodes or not mat.node_tree:
            continue

        for node in mat.node_tree.nodes:
            if node.bl_idname == "ShaderNodeGroup" and node.node_tree == group:
                yield mat, node


def image_from_socket(sock):
    if not sock or not sock.is_linked:
        return None, "EMPTY"

    link = sock.links[0]
    node = link.from_node
    if node.bl_idname != "ShaderNodeTexImage":
        return None, f"UNSUPPORTED_LINK:{node.bl_idname}"

    return node.image, "IMAGE"


def run(context, operator=None):
    print("\n========== RZM QA BAKE PROTOTYPE ==========")
    print("Mode: dry-run only. No bake, no UV edits, no file writes.")

    count = 0
    for mat, node in iter_rzm_nodes() or []:
        count += 1
        print(f"\nMaterial: {mat.name}")
        print(f"Node: {node.name}")

        for slot_name in TEXTURE_INPUTS:
            image, status = image_from_socket(node.inputs.get(slot_name))
            if image:
                size = tuple(image.size[:])
                filepath = image.filepath or image.filepath_raw
                print(f"  {slot_name}: {status} | {image.name} | {size} | {filepath}")
            else:
                print(f"  {slot_name}: {status}")

    print(f"\nRZM nodes found: {count}")
    print("===========================================\n")

    if operator:
        operator.report({"INFO"}, f"Bake prototype dry-run found {count} RZM node(s).")

    return {"FINISHED"}


def rebuild_textures(context, operator=None):
    print("\n[RZM QA] rebuild_textures dry-run")
    print("Expected future work: collect selected/marked objects, choose reference UV, rebake slot textures, keep source UV safe.")
    if operator:
        operator.report({"INFO"}, "Rebuild textures dry-run. Implement heart in BakePrototype.py.")
    return {"FINISHED"}


def calculate_atlas_size(context, operator=None):
    print("\n[RZM QA] calculate_atlas_size dry-run")
    print("Expected future work: scan collected texture sizes, padding, atlas policy, pack layout, write debug report.")
    if operator:
        operator.report({"INFO"}, "Calculate atlas size dry-run. Implement heart in BakePrototype.py.")
    return {"FINISHED"}


def export_atlas(context, operator=None):
    print("\n[RZM QA] export_atlas dry-run")
    print("Expected future work: write PNGs into Textures/DynAtlas and emit data for later TexWorks collectionProperty injection.")
    if operator:
        operator.report({"INFO"}, "Export atlas dry-run. Implement heart in BakePrototype.py.")
    return {"FINISHED"}


def register_runtime_actions():
    registry = bpy.app.driver_namespace.setdefault(RUNTIME_NAMESPACE_KEY, {})
    registry["bake_prototype"] = run
    registry["rebuild_textures"] = rebuild_textures
    registry["calculate_atlas_size"] = calculate_atlas_size
    registry["export_atlas"] = export_atlas
    print("[RZM QA] BakePrototype runtime actions registered.")


register_runtime_actions()
