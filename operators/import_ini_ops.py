# RZMenu/operators/import_ini_ops.py
"""
Blender-operator for importing 3DMigoto .ini into RZM scene data.

Imported:
  - global persist $var = N       ->  rzm.rzm_values  (ValueProperty)
  - $var assignments in TextureOverride blocks -> rzm.toggle_definitions (ToggleDefinition,
                                                  toggle_length from max value found)
  - [Key...] + type=cycle         ->  rzm.keybinds    (RZMKeybind) + rzm.run_links
  - CommandListRandom* %MAX       ->  val_max on matching variable
  - CommandListSave/Load          ->  in_game_profiles (SAVE_SLOT profiles)
  - [KeyCycle] matrix             ->  in_game_profiles (KEY_CYCLE profiles)

NOT imported:
  - Resource, Present, GPU commands (drawindexed, vb0, ib, ps-t*)
  - $active, $creditinfo, $mod_info (system vars)
  - global $ non-persist (runtime only)
"""

import re
import bpy
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy_extras.io_utils import ImportHelper

# --- Constants ----------------------------------------------------------------

IGNORE_VARS = {'active', 'creditinfo', 'mod_info'}
SYSTEM_KEY_NAMES = {
    'KeyUp', 'KeyDown', 'KeyLeft', 'KeyRight', 'KeyInputModeToggle',
    'KeyGamepadUP', 'KeyGamepadDOWN', 'KeyGamepadLEFT', 'KeyGamepadRIGHT',
    'KeyGamepadToggleEdit', 'KeyInputManager',
}
GPU_LINE_PREFIXES = ('vb0', 'vb1', 'ib', 'ps-t', 'drawindexed', 'draw =',
                     'handling', 'hash', 'override_vertex', 'override_byte',
                     'match_first_index', 'Resource', 'Filter')


# --- Parser -------------------------------------------------------------------

def _norm_var(var_name: str, d_prefix: str) -> tuple:
    """Return (clean_name, is_d_variant). Strips D-prefix if configured."""
    clean = var_name
    is_d = False
    if (d_prefix and len(var_name) > 1
            and var_name.startswith(d_prefix)
            and var_name[1].isupper()):
        clean = var_name[1:]
        is_d = True
    return clean, is_d


def _parse_ini(path: str, d_prefix: str = 'D'):
    """
    Returns:
      variables   : dict[clean_name -> {default, val_max, mark_random}]
      toggles     : dict[clean_name -> {toggle_length}]  (from TextureOverride)
      keybinds    : list[dict]
      profiles    : list[dict]
    """
    with open(path, encoding='utf-8', errors='replace') as f:
        raw = f.read()

    # -- Split into sections --------------------------------------------------
    sections = {}          # sec_name -> list[str]
    sec_types = {}         # sec_name -> 'normal' | 'texture_override' | 'skip'
    current = '__top__'
    sections[current] = []
    sec_types[current] = 'skip'

    for line in raw.splitlines():
        line = line.rstrip('\r')
        m = re.match(r'^\[([^\]]+)\]', line)
        if m:
            current = m.group(1)
            if current.startswith('Resource') or current == 'Present':
                sec_types[current] = 'skip'
            elif current.startswith('TextureOverride'):
                sec_types[current] = 'texture_override'
            else:
                sec_types[current] = 'normal'
            if current not in sections:
                sections[current] = []
        else:
            sections[current].append(line)

    variables = {}   # clean_name -> dict
    toggles   = {}   # clean_name -> {toggle_length}
    keybinds  = []
    profiles  = []

    # -- 1. [Constants] — only global persist ---------------------------------
    for sec_name, body in sections.items():
        if sec_name.lower() != 'constants':
            continue
        for line in body:
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            m = re.match(r'^global\s+persist\s+\$(\w+)\s*=\s*(-?\d+)', line)
            if not m:
                continue
            var_name = m.group(1)
            val = int(m.group(2))
            if var_name in IGNORE_VARS:
                continue
            clean, is_d = _norm_var(var_name, d_prefix)
            if clean not in variables:
                variables[clean] = {
                    'default': val, 'val_max': 0,
                    'mark_random': False
                }

    # -- 2. TextureOverride blocks — detect toggles ---------------------------
    # Variables assigned inside TextureOverride sections are toggles.
    # The max value found across all such assignments = toggle_length.
    for sec_name, body in sections.items():
        if sec_types.get(sec_name) != 'texture_override':
            continue
        for line in body:
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            # Skip GPU-specific lines
            if any(line.lower().startswith(p.lower()) for p in GPU_LINE_PREFIXES):
                continue
            # Match: $varname = integer (direct assignment, not formula)
            m = re.match(r'^\$(\w+)\s*=\s*(\d+)\s*(?:;.*)?$', line)
            if m:
                var_name = m.group(1)
                val = int(m.group(2))
                if var_name in IGNORE_VARS:
                    continue
                clean, _ = _norm_var(var_name, d_prefix)
                if clean in toggles:
                    toggles[clean]['toggle_length'] = max(
                        toggles[clean]['toggle_length'], val + 1)
                else:
                    toggles[clean] = {'toggle_length': val + 1}

    # -- 3. CommandListRandom* — infer val_max --------------------------------
    for sec_name, body in sections.items():
        if not sec_name.startswith('CommandListRandom'):
            continue
        for line in body:
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            m = re.match(r'^\$(\w+)\s*=\s*\(time\*\d+\)\s*%\s*(\d+)\s*//\s*1', line)
            if not m:
                continue
            var_name = m.group(1)
            max_val  = int(m.group(2))
            clean, _ = _norm_var(var_name, d_prefix)
            if clean in variables:
                variables[clean]['val_max']     = max_val
                variables[clean]['mark_random'] = True

    # -- 4. Key sections ------------------------------------------------------
    for sec_name, body in sections.items():
        if not sec_name.startswith('Key'):
            continue
        if sec_name in SYSTEM_KEY_NAMES:
            continue
        if sec_types.get(sec_name, 'normal') == 'skip':
            continue

        kb = {
            'name': sec_name, 'key': [], 'back': [],
            'type': 'cycle', 'condition': '',
            'only_menu_active': False,
            'run_id': '', 'cycle_vars': {}
        }

        for line in body:
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            if line.startswith('key ='):
                kb['key'].append(line.split('=', 1)[1].strip())
            elif line.startswith('back ='):
                kb['back'].append(line.split('=', 1)[1].strip())
            elif line.startswith('type ='):
                kb['type'] = line.split('=', 1)[1].strip()
            elif line.startswith('condition ='):
                raw_cond = line.split('=', 1)[1].strip()
                if re.match(r'^\$active\s*==\s*\d+$', raw_cond):
                    kb['only_menu_active'] = True
                else:
                    kb['condition'] = raw_cond
            elif line.startswith('run ='):
                kb['run_id'] = line.split('=', 1)[1].strip()
            else:
                m = re.match(r'^\$(\w+)\s*=\s*(.+)$', line)
                if m:
                    var_raw  = m.group(1)
                    vals_raw = m.group(2).strip()
                    if var_raw in IGNORE_VARS:
                        continue
                    clean, _ = _norm_var(var_raw, d_prefix)
                    try:
                        vals = [int(v.strip()) for v in vals_raw.split(',')]
                        kb['cycle_vars'][clean] = vals
                    except ValueError:
                        pass

        if not kb['key']:
            continue

        if not kb['run_id'] and kb['cycle_vars']:
            kb['run_id'] = sec_name

        keybinds.append(kb)

    # -- 5. Save/Load profiles ------------------------------------------------
    for sec_name, body in sections.items():
        m = re.match(r'^CommandListSave(\w+)$', sec_name)
        if not m:
            continue
        slot = m.group(1)
        slot_vars = {}
        for line in body:
            line = line.strip()
            if not line or line.startswith(';') or line.startswith('pre '):
                continue
            mv = re.match(r'^\$(\w+)\s*=\s*\$(\w+)', line)
            if mv:
                src = mv.group(2)
                clean, _ = _norm_var(src, d_prefix)
                if clean not in IGNORE_VARS:
                    slot_vars[clean] = 0
        if slot_vars:
            profiles.append({'name': f'Slot_{slot}',
                             'source': 'SAVE_SLOT', 'values': slot_vars})

    # -- 6. KeyCycle matrix presets -> profiles -------------------------------
    for kb in keybinds:
        if kb['name'] not in ('KeyCycle', 'KeyDCycle') or not kb['cycle_vars']:
            continue
        max_len = max((len(v) for v in kb['cycle_vars'].values()), default=0)
        for i in range(max_len):
            pv = {}
            for vn, vals in kb['cycle_vars'].items():
                if i < len(vals):
                    pv[vn] = vals[i]
            profiles.append({'name': f'Outfit_{i}',
                             'source': 'KEY_CYCLE', 'values': pv})

    return variables, toggles, keybinds, profiles


def _is_d_keybind(kb_name: str, d_prefix: str = 'D') -> bool:
    stripped = kb_name.replace('Key', '', 1)
    return (bool(d_prefix) and stripped.startswith(d_prefix)
            and len(stripped) > 1 and stripped[1].isupper())


def _next_run_link_id(rzm) -> int:
    """Return next available integer ID for a new RunLink (like image_id)."""
    return max((rl.id for rl in rzm.run_links if rl.id >= 0), default=0) + 1


# --- Operator -----------------------------------------------------------------

class RZM_OT_ImportIni(bpy.types.Operator, ImportHelper):
    """Import variables, toggles, keybinds and profiles from a 3DMigoto .ini file"""
    bl_idname = "rzm.import_ini"
    bl_label  = "Import 3DMigoto .ini"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".ini"
    filter_glob: StringProperty(default="*.ini", options={'HIDDEN'})

    import_variables: BoolProperty(
        name="Import Variables",
        description="Import 'global persist' variables into rzm.rzm_values",
        default=True
    )
    import_toggles: BoolProperty(
        name="Import Toggles (from TextureOverride)",
        description="Variables found in TextureOverride blocks are treated as ToggleDefinitions",
        default=True
    )
    import_keybinds: BoolProperty(
        name="Import Keybinds",
        description="Import [Key...] sections into rzm.keybinds",
        default=True
    )
    import_profiles: BoolProperty(
        name="Import Profiles",
        description="Import Save/Load slots and KeyCycle presets into per-variable profiles",
        default=True
    )
    skip_d_variants: BoolProperty(
        name="Skip D-Prefix Duplicates",
        description="Merge D-prefix variables/keybinds with their base counterparts",
        default=True
    )
    d_prefix: StringProperty(
        name="D-Prefix Character",
        description="Prefix character for duplicate character variant (usually 'D')",
        default="D",
        maxlen=4
    )
    conflict_mode: EnumProperty(
        name="On Conflict",
        description="What to do when a variable/keybind already exists",
        items=[
            ('SKIP',      "Skip",      "Leave existing entries unchanged"),
            ('OVERWRITE', "Overwrite", "Update values of existing entries"),
        ],
        default='SKIP'
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Import Options:", icon='IMPORT')
        col = layout.column(align=True)
        col.prop(self, "import_variables")
        col.prop(self, "import_toggles")
        col.prop(self, "import_keybinds")
        col.prop(self, "import_profiles")
        layout.separator()
        layout.prop(self, "skip_d_variants")
        layout.prop(self, "d_prefix")
        layout.separator()
        layout.prop(self, "conflict_mode")

    def execute(self, context):
        rzm = context.scene.rzm
        dp  = self.d_prefix if self.skip_d_variants else ''

        # Parse
        try:
            variables, toggles, keybinds, profiles = _parse_ini(self.filepath, dp)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to parse .ini: {e}")
            import traceback; traceback.print_exc()
            return {'CANCELLED'}

        stats = {'vars': 0, 'vars_skip': 0,
                 'togs': 0, 'togs_skip': 0,
                 'kbs': 0,  'kbs_skip': 0,
                 'prof': 0}

        # -- 1. Variables ---------------------------------------------------
        if self.import_variables:
            existing = {v.value_name for v in rzm.rzm_values}
            for name, vd in variables.items():
                if name in existing:
                    if self.conflict_mode == 'OVERWRITE':
                        for v in rzm.rzm_values:
                            if v.value_name == name:
                                v.int_value   = vd['default']
                                v.val_max     = float(vd['val_max'])
                                v.mark_random = vd['mark_random']
                                break
                        stats['vars'] += 1
                    else:
                        stats['vars_skip'] += 1
                    continue
                nv = rzm.rzm_values.add()
                nv.value_name  = name
                nv.value_type  = 'INT'
                nv.int_value   = vd['default']
                nv.val_min     = 0.0
                nv.val_max     = float(vd['val_max'])
                nv.mark_random = vd['mark_random']
                stats['vars'] += 1

        # -- 2. Toggles (from TextureOverride) ------------------------------
        if self.import_toggles:
            existing_t = {t.toggle_name for t in rzm.toggle_definitions}
            for name, td in toggles.items():
                if name in existing_t:
                    if self.conflict_mode == 'OVERWRITE':
                        for t in rzm.toggle_definitions:
                            if t.toggle_name == name:
                                t.toggle_length = max(t.toggle_length, td['toggle_length'])
                                break
                        stats['togs'] += 1
                    else:
                        stats['togs_skip'] += 1
                    continue
                nt = rzm.toggle_definitions.add()
                nt.toggle_name   = name
                nt.toggle_length = td['toggle_length']
                stats['togs'] += 1

        # -- 3. Keybinds ----------------------------------------------------
        if self.import_keybinds:
            existing_k = {kb.name for kb in rzm.keybinds}
            for kd in keybinds:
                if self.skip_d_variants and _is_d_keybind(kd['name'], dp):
                    stats['kbs_skip'] += 1
                    continue

                if kd['name'] in existing_k:
                    if self.conflict_mode == 'SKIP':
                        stats['kbs_skip'] += 1
                        continue
                    for i, kb in enumerate(rzm.keybinds):
                        if kb.name == kd['name']:
                            rzm.keybinds.remove(i)
                            break

                nk = rzm.keybinds.add()
                nk.name             = kd['name']
                nk.key              = ', '.join(kd['key'])
                nk.back             = ', '.join(kd['back'])
                nk.type             = kd['type']
                nk.condition        = kd['condition']
                nk.only_menu_active = kd['only_menu_active']
                nk.run_id           = kd['run_id']

                # Auto-create RunLink if inline cycle_vars present
                if kd['cycle_vars']:
                    rl_name = kd['run_id'] or kd['name']
                    existing_rl = next(
                        (rl for rl in rzm.run_links if rl.name == rl_name), None
                    )
                    if not existing_rl:
                        nrl = rzm.run_links.add()
                        nrl.id          = _next_run_link_id(rzm)
                        nrl.name        = rl_name
                        nrl.description = f"Auto-imported from [{kd['name']}]"
                        body_lines = []
                        for vn, vals in kd['cycle_vars'].items():
                            body_lines.append(f'${vn} = {",".join(str(v) for v in vals)}')
                        nrl.body = '\n'.join(body_lines)

                stats['kbs'] += 1

        # -- 4. Profiles ----------------------------------------------------
        if self.import_profiles:
            rzm_addons = rzm.addons
            if not getattr(rzm_addons, 'use_in_game_profiles', False):
                rzm_addons.use_in_game_profiles = True
                self.report({'INFO'}, "In-Game Profiles automatically enabled.")

            for pdata in profiles:
                for vn, val in pdata['values'].items():
                    for v in rzm.rzm_values:
                        if v.value_name == vn:
                            ns = v.in_game_profiles.add()
                            ns.int_value = int(val) if val != '__MIRROR__' else v.int_value
                            break
                stats['prof'] += 1

        # Report
        msg = (f"Import done: {stats['vars']} vars ({stats['vars_skip']} skipped), "
               f"{stats['togs']} toggles ({stats['togs_skip']} skipped), "
               f"{stats['kbs']} keybinds ({stats['kbs_skip']} skipped), "
               f"{stats['prof']} profiles.")
        self.report({'INFO'}, msg)
        print(f"[RZM Import] {msg}")
        return {'FINISHED'}


# --- Registration --------------------------------------------------------------

classes_to_register = [
    RZM_OT_ImportIni,
]
