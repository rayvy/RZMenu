import json
import os
import re
import time

import bpy


XXMI_GAMES = {"GenshinImpact", "ZenlessZoneZero", "HonkaiStarRail"}
SNAPSHOT_VERSION = 1


def _game_name(context):
    rzm = getattr(context.scene, "rzm", None)
    game = getattr(getattr(rzm, "game", None), "selection", "")
    return game or getattr(getattr(rzm, "game", None), "name", "")


def _component_manager(context):
    rzm = getattr(context.scene, "rzm", None)
    return getattr(rzm, "component_manager", None) if rzm else None


def _dump_path(context, cm):
    path = getattr(cm, "dump_path", "") if cm else ""
    if not path and hasattr(context.scene, "xxmi"):
        path = getattr(context.scene.xxmi, "dump_path", "")
    if not path:
        return ""
    path = os.path.normpath(bpy.path.abspath(path))
    if os.path.isfile(path):
        path = os.path.dirname(path)
    return path


def _norm(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _load_hash_json(dump_path):
    path = os.path.join(dump_path, "hash.json")
    if not os.path.exists(path):
        return None, None
    with open(path, "r", encoding="utf-8") as handle:
        return path, json.load(handle)


def _texture_summary(component_data):
    textures = {}
    for lod in component_data.get("texture_hashes", []) or []:
        for item in lod or []:
            if not isinstance(item, (list, tuple)) or len(item) < 3:
                continue
            tex_type = str(item[0] or "Unknown")
            ext = str(item[1] or "")
            tex_hash = str(item[2] or "")
            info = textures.setdefault(tex_type, {"count": 0, "formats": [], "hashes": []})
            info["count"] += 1
            if ext and ext not in info["formats"]:
                info["formats"].append(ext)
            if tex_hash and len(info["hashes"]) < 8:
                info["hashes"].append(tex_hash)
    return textures


def _collection_mesh_names(collection):
    names = []
    try:
        objects = collection.all_objects
    except Exception:
        objects = collection.objects
    for obj in objects:
        if obj and obj.type == "MESH" and obj.data:
            names.append(obj.name)
    return sorted(set(names))


def _match_key(collection_key, keys):
    return any(key and collection_key.startswith(key) for key in keys)


def _build_component_entry(component_data, mod_name):
    comp_name = str(component_data.get("component_name", "") or "")
    classifications = [
        str(item or "")
        for item in (component_data.get("object_classifications", []) or [])
        if str(item or "")
    ]
    parts = []
    for suffix in classifications:
        part_name = f"{comp_name}{suffix}"
        parts.append({
            "name": part_name,
            "suffix": suffix,
            "collections": [],
            "objects": [],
        })

    return {
        "name": comp_name,
        "kind": "component_with_parts" if parts else "component_solo",
        "vb0_owner": comp_name,
        "collections": [],
        "objects": [],
        "parts": parts,
        "textures": _texture_summary(component_data),
        "_component_keys": [_norm(comp_name), _norm(f"{mod_name}{comp_name}")],
        "_part_keys": {
            part["name"]: [
                _norm(part["name"]),
                _norm(f"{mod_name}{part['name']}"),
                _norm(f"{comp_name}{part['suffix']}"),
                _norm(f"{mod_name}{comp_name}{part['suffix']}"),
            ]
            for part in parts
        },
    }


def rebuild_component_snapshot(context):
    """Build a compact XXMI component snapshot once, then store it on component_manager."""
    cm = _component_manager(context)
    if not cm:
        return None

    game = _game_name(context)
    if game not in XXMI_GAMES:
        snapshot = {
            "version": SNAPSHOT_VERSION,
            "supported": False,
            "game": game,
            "reason": "Only XXMI games are supported by the dynamic resolver snapshot for now.",
            "components": [],
            "object_index": {},
        }
        cm.resolver_snapshot_json = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
        cm.resolver_snapshot_summary = f"Unsupported game: {game or 'Unknown'}"
        return snapshot

    dump_path = _dump_path(context, cm)
    hash_path, data = _load_hash_json(dump_path) if dump_path else (None, None)
    if not isinstance(data, list):
        snapshot = {
            "version": SNAPSHOT_VERSION,
            "supported": False,
            "game": game,
            "reason": "hash.json not found or invalid.",
            "dump_path": dump_path,
            "components": [],
            "object_index": {},
        }
        cm.resolver_snapshot_json = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
        cm.resolver_snapshot_summary = "XXMI snapshot failed: hash.json missing"
        return snapshot

    mod_name = os.path.basename(os.path.normpath(dump_path))
    components = [
        _build_component_entry(item, mod_name)
        for item in data
        if isinstance(item, dict) and item.get("component_name")
    ]

    object_index = {}
    for collection in bpy.data.collections:
        collection_key = _norm(collection.name)
        mesh_names = _collection_mesh_names(collection)
        if not mesh_names:
            continue

        for component in components:
            matched_part = None
            for part in component["parts"]:
                if _match_key(collection_key, component["_part_keys"].get(part["name"], [])):
                    matched_part = part
                    break

            if matched_part:
                matched_part["collections"].append(collection.name)
                matched_part["objects"] = sorted(set(matched_part["objects"]) | set(mesh_names))
                for obj_name in mesh_names:
                    object_index[obj_name] = {
                        "component": component["name"],
                        "part": matched_part["name"],
                        "collection": collection.name,
                    }
                continue

            if _match_key(collection_key, component["_component_keys"]):
                component["collections"].append(collection.name)
                component["objects"] = sorted(set(component["objects"]) | set(mesh_names))
                for obj_name in mesh_names:
                    current = object_index.get(obj_name)
                    if not current or not current.get("part"):
                        object_index[obj_name] = {
                            "component": component["name"],
                            "part": "",
                            "collection": collection.name,
                        }

    for component in components:
        component.pop("_component_keys", None)
        component.pop("_part_keys", None)
        component["collections"] = sorted(set(component["collections"]))
        component["objects"] = sorted(set(component["objects"]))
        for part in component["parts"]:
            part["collections"] = sorted(set(part["collections"]))
            part["objects"] = sorted(set(part["objects"]))

    parts_count = sum(len(component["parts"]) for component in components)
    mapped_objects_count = len(object_index)
    snapshot = {
        "version": SNAPSHOT_VERSION,
        "supported": True,
        "source": "xxmi_hash_and_collections",
        "game": game,
        "mod_name": mod_name,
        "dump_path": dump_path,
        "hash_path": hash_path,
        "updated_at": int(time.time()),
        "components": components,
        "object_index": object_index,
        "stats": {
            "components": len(components),
            "parts": parts_count,
            "mapped_objects": mapped_objects_count,
        },
    }

    cm.resolver_snapshot_json = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
    cm.resolver_snapshot_summary = (
        f"XXMI: {len(components)} components, {parts_count} parts, "
        f"{mapped_objects_count} mapped objects"
    )
    return snapshot


def load_component_snapshot(context):
    cm = _component_manager(context)
    if not cm:
        return {}
    raw = getattr(cm, "resolver_snapshot_json", "") or "{}"
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def resolve_object_from_snapshot(context, obj):
    if not obj:
        return None, load_component_snapshot(context)
    snapshot = load_component_snapshot(context)
    index = snapshot.get("object_index", {})
    match = index.get(obj.name)
    return match, snapshot
