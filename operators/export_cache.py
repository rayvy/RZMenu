# RZMenu/operators/export_cache.py
# Stores per-component vertex layout data captured from XXMI / EFMI exporters.
# Uses bpy.app.driver_namespace so the cache survives addon reload
# and is visible from any addon in the same Blender session.
#
# Cache schema (bpy.app.driver_namespace['rzm_export_cache']):
# {
#   'source':    'xxmi' | 'efmi',
#   'game':      str,
#   'mod_name':  str,
#   'mod_root':  str,          # absolute path to mod output folder
#   'timestamp': float,
#   'components': {
#       'Hair': {
#           'buf_path':  str,        # absolute path to ...Position.buf / Component0_VB0.buf
#           'stride':    int,        # bytes per vertex
#           'n_verts':   int,        # total vertices in buffer
#           'objects': [             # in ORDER written to buffer
#               { 'name': str, 'vb_offset': int, 'vb_count': int }
#           ]
#       },
#       ...
#   }
# }

import bpy
import os
import time

CACHE_KEY = 'rzm_export_cache'


# ── Public API ────────────────────────────────────────────────────────────────

def get_cache() -> dict | None:
    """Return the current export cache, or None if absent / stale."""
    return bpy.app.driver_namespace.get(CACHE_KEY)


def set_cache(data: dict) -> None:
    bpy.app.driver_namespace[CACHE_KEY] = data


def clear_cache() -> None:
    bpy.app.driver_namespace.pop(CACHE_KEY, None)


def has_cache() -> bool:
    return CACHE_KEY in bpy.app.driver_namespace


def component_cache(comp_name: str) -> dict | None:
    """Shortcut: return cache entry for a single component, or None."""
    c = get_cache()
    if c is None:
        return None
    return c.get('components', {}).get(comp_name)


# ── Builder: XXMI ─────────────────────────────────────────────────────────────

def build_cache_from_xxmi(mod_exporter) -> dict | None:
    """
    Extract vertex-layout metadata from a finished XXMITools ModExporter instance.
    Called AFTER mod_exporter.generate_buffers() has run.

    ModExporter structure (XXMITools/migoto/exporter.py):
        mod_exporter.mod_name           : str
        mod_exporter.destination        : Path
        mod_exporter.game               : GameEnum
        mod_exporter.mod_file.components: list[Component]
            Component.fullname          : str   e.g. 'SkirkHair'
            Component.blend_vb          : str   non-empty → split Position/Blend/Texcoord bufs
            Component.strides           : dict  e.g. {'position': 40}
            Component.parts             : list[Part]
                Part.objects            : list[SubObj]
                    SubObj.name         : str   Blender object name
                    SubObj.vertex_count : int   verts this sub-object contributed
                    SubObj.index_offset : int   (index offset, not vertex offset)

    NOTE: XXMITools does NOT expose vb_offset directly as a SubObj field.
    We reconstruct it by accumulating vertex_count across all sub-objects
    in order — the same order generate_buffers() writes them.
    """
    try:
        mod_name   = mod_exporter.mod_name
        dest       = str(mod_exporter.destination)
        game       = str(mod_exporter.game)          # GameEnum value
        components = {}

        for comp in mod_exporter.mod_file.components:
            # Determine buffer path
            if comp.blend_vb != '':
                # Split-buffer game (GI / ZZZ / HSR)
                buf_path = os.path.join(dest, comp.fullname + 'Position.buf')
            else:
                buf_path = os.path.join(dest, comp.fullname + '.buf')

            stride = (comp.strides.get('position') or
                      next(iter(comp.strides.values()), 0))

            # Reconstruct per-object vertex offsets from sequential accumulation
            objects      = []
            vb_offset    = 0
            for part in comp.parts:
                for sub in part.objects:
                    if sub.vertex_count == 0:
                        continue
                    objects.append({
                        'name':      sub.name,
                        'vb_offset': vb_offset,
                        'vb_count':  sub.vertex_count,
                    })
                    vb_offset += sub.vertex_count

            comp_key = comp.fullname[len(mod_name):]   # strip mod prefix → 'Hair'
            if not comp_key:
                comp_key = comp.fullname

            components[comp_key] = {
                'buf_path': buf_path,
                'stride':   stride,
                'n_verts':  vb_offset,
                'objects':  objects,
            }

        cache = {
            'source':     'xxmi',
            'game':       game,
            'mod_name':   mod_name,
            'mod_root':   dest,
            'timestamp':  time.time(),
            'components': components,
        }
        return cache
    except Exception as e:
        print(f'[RZM] [CACHE] XXMI cache build failed: {e}')
        return None


# ── Builder: EFMI ─────────────────────────────────────────────────────────────

def build_cache_from_efmi(mod_exporter) -> dict | None:
    """
    Extract vertex-layout metadata from a finished EFMI-Tools ModExporter instance.
    Called AFTER mod_exporter.export_mod() has run (before buffers are cleared).

    EFMI ModExporter structure (EFMI-Tools/blender_export/blender_export.py):
        mod_exporter.mod_output_folder       : Path
        mod_exporter.meshes_path             : Path   → where .buf files land
        mod_exporter.cfg.mod_name            : str
        mod_exporter.extracted_object        : ExtractedObject
        mod_exporter.merged_object           : MergedObject
            .components                      : list[MergedObjectComponent]
                .id                          : int
                .vertex_count                : int
                .objects                     : list[TempObject]
                    .name                    : str   original Blender object name
                    .vertex_count            : int
                    .index_offset            : int   (NOT vertex offset — index offset)

    EFMI buffers are named Component{N}_VB{slot}.buf  inside meshes_path.
    Stride comes from the fmt file, but we can estimate from buf size / vertex_count.
    """
    try:
        mod_name   = getattr(mod_exporter.cfg, 'mod_name', 'unknown')
        dest       = str(mod_exporter.mod_output_folder)
        meshes_dir = str(mod_exporter.meshes_path)
        game       = 'ArknightsEndfield'
        components = {}

        for comp in mod_exporter.merged_object.components:
            comp_id   = comp.id
            buf_name  = f'Component{comp_id}_VB0.buf'
            buf_path  = os.path.join(meshes_dir, buf_name)

            # Estimate stride from buffer size and vertex count
            stride = 0
            if os.path.exists(buf_path) and comp.vertex_count > 0:
                stride = os.path.getsize(buf_path) // comp.vertex_count

            # Reconstruct per-object vertex offsets
            objects   = []
            vb_offset = 0
            for tmp in comp.objects:
                if tmp.vertex_count == 0:
                    continue
                objects.append({
                    'name':      tmp.name,
                    'vb_offset': vb_offset,
                    'vb_count':  tmp.vertex_count,
                })
                vb_offset += tmp.vertex_count

            components[f'Component{comp_id}'] = {
                'buf_path': buf_path,
                'stride':   stride,
                'n_verts':  comp.vertex_count,
                'objects':  objects,
            }

        cache = {
            'source':     'efmi',
            'game':       game,
            'mod_name':   mod_name,
            'mod_root':   dest,
            'timestamp':  time.time(),
            'components': components,
        }
        return cache
    except Exception as e:
        print(f'[RZM] [CACHE] EFMI cache build failed: {e}')
        return None


# ── Debug ─────────────────────────────────────────────────────────────────────

def print_cache_summary() -> None:
    c = get_cache()
    if c is None:
        print('[RZM] [CACHE] No export cache present.')
        return
    import datetime
    ts = datetime.datetime.fromtimestamp(c['timestamp']).strftime('%H:%M:%S')
    print(f"[RZM] [CACHE] source={c['source']}  game={c['game']}  mod={c['mod_name']}  @ {ts}")
    for name, comp in c.get('components', {}).items():
        n_obj = len(comp.get('objects', []))
        print(f"  {name}: {comp['n_verts']} verts / stride={comp['stride']} / {n_obj} objects")
        for o in comp.get('objects', []):
            print(f"    [{o['vb_offset']:>6} .. {o['vb_offset']+o['vb_count']-1:>6}]  {o['name']}")
