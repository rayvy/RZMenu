#!/usr/bin/env python3
"""
RZMenu - INI Import Preview Script (Standalone)
================================================
Usage: python import_ini_preview.py "G:/path/to/Mod.ini"

Simulates what will be imported into RZM when parsing a 3DMigoto .ini file.
Nothing is written - only a console report.

Ignored:
  - $active, $creditinfo, $mod_info (system vars)
  - global $ (without persist) -- runtime only
  - TextureOverride, Resource, Present sections
  - GPU commands (drawindexed, vb0, ib, ps-t*)
  - run = CommandList\\global\\... (external deps)
"""

import re
import sys
import os

# Force UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dataclasses import dataclass, field
from typing import Optional

# --- Constants ---

IGNORE_VARS = {'active', 'creditinfo', 'mod_info'}
IGNORE_SECTION_PREFIXES = ('TextureOverride', 'Resource', 'Present')
D_PREFIX_CHAR = 'D'  # Second character variant prefix (Dark Skirk)

# --- Result Structures ---

@dataclass
class ParsedVariable:
    name: str
    default_value: int
    val_max: int = 0
    mark_random: bool = False
    variant: str = ''  # '' = main, 'D' = second character

@dataclass
class ParsedKeybind:
    section_name: str
    key: list
    back: list
    type: str
    condition: str
    run_id: str
    cycle_vars: dict  # {var_name: [v0, v1, ...]} for type=cycle

@dataclass
class ParsedProfile:
    name: str   # e.g. 'SaveA', 'Outfit_2'
    source: str  # 'SAVE_SLOT' | 'KEY_CYCLE'
    values: dict  # {var_name: value}

# --- Parser ---

def parse_ini(path: str):
    with open(path, encoding='utf-8', errors='replace') as f:
        raw = f.read()

    lines = raw.splitlines()

    variables: dict = {}
    keybinds: list = []
    profiles: list = []

    # Split into sections
    sections: dict = {}
    current = '__top__'
    sections[current] = []
    for line in lines:
        line = line.rstrip('\r')
        m = re.match(r'^\[([^\]]+)\]', line)
        if m:
            current = m.group(1)
            # Skip if this is a known ignore-section
            should_skip = any(current.startswith(p) for p in IGNORE_SECTION_PREFIXES)
            if should_skip:
                current = '__skip__'
            if current not in sections:
                sections[current] = []
        else:
            sections[current].append(line)

    # -- 1. [Constants] - only global persist ---------------------------------
    for name, body in sections.items():
        if name.lower() != 'constants':
            continue
        for line in body:
            line = line.strip()
            if not line or line.startswith(';'):
                continue

            # global persist $var = N
            m = re.match(r'^global\s+persist\s+\$(\w+)\s*=\s*(-?\d+)', line)
            if m:
                var_name = m.group(1)
                val = int(m.group(2))
                if var_name in IGNORE_VARS:
                    continue
                # Detect D-prefix (second character variant)
                variant = ''
                clean_name = var_name
                if (var_name.startswith(D_PREFIX_CHAR) and len(var_name) > 1
                        and var_name[1].isupper()):
                    variant = D_PREFIX_CHAR
                    clean_name = var_name[1:]

                # Deduplicate: if clean_name already present, skip (D-variant)
                if clean_name not in variables:
                    variables[clean_name] = ParsedVariable(
                        name=clean_name,
                        default_value=val,
                        variant=variant
                    )
                # Note: D-variants are intentionally NOT stored separately

            # global $var (no persist) - skip runtime vars
            # No action needed

    # -- 2. CommandListRandom* - infer val_max --------------------------------
    for name, body in sections.items():
        if not name.startswith('CommandListRandom'):
            continue
        for line in body:
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            # $var = (time*N)%MAX//1
            m = re.match(r'^\$(\w+)\s*=\s*\(time\*\d+\)\s*%\s*(\d+)\s*//\s*1', line)
            if m:
                var_name = m.group(1)
                max_val = int(m.group(2))
                # Normalize D-prefix
                clean_name = var_name
                if (var_name.startswith(D_PREFIX_CHAR) and len(var_name) > 1
                        and var_name[1].isupper()):
                    clean_name = var_name[1:]
                if clean_name in variables:
                    variables[clean_name].val_max = max_val
                    variables[clean_name].mark_random = True

    # -- 3. Key sections ------------------------------------------------------
    SYSTEM_KEYS = {
        'KeyUp', 'KeyDown', 'KeyLeft', 'KeyRight', 'KeyInputModeToggle',
        'KeyGamepadUP', 'KeyGamepadDOWN', 'KeyGamepadLEFT', 'KeyGamepadRIGHT',
        'KeyGamepadToggleEdit', 'KeyInputManager'
    }

    for name, body in sections.items():
        if not name.startswith('Key'):
            continue
        if name in SYSTEM_KEYS:
            continue

        kb_keys = []
        kb_back = []
        kb_type = 'cycle'
        kb_condition = ''
        kb_run_id = ''
        cycle_vars: dict = {}

        for line in body:
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            if line.startswith('key ='):
                kb_keys.append(line.split('=', 1)[1].strip())
            elif line.startswith('back ='):
                kb_back.append(line.split('=', 1)[1].strip())
            elif line.startswith('type ='):
                kb_type = line.split('=', 1)[1].strip()
            elif line.startswith('condition ='):
                raw_cond = line.split('=', 1)[1].strip()
                # Replace simple $active == N with only_menu_active flag
                if re.match(r'^\$active\s*==\s*\d+$', raw_cond):
                    kb_condition = '__menu_active__'
                else:
                    kb_condition = raw_cond
            elif line.startswith('run ='):
                kb_run_id = line.split('=', 1)[1].strip()
            else:
                # Parse cycle values: $var = 0,1,2,...
                m = re.match(r'^\$(\w+)\s*=\s*(.+)$', line)
                if m:
                    var_raw = m.group(1)
                    vals_raw = m.group(2).strip()
                    if var_raw in IGNORE_VARS:
                        continue
                    # Normalize D-prefix
                    clean_name = var_raw
                    if (var_raw.startswith(D_PREFIX_CHAR) and len(var_raw) > 1
                            and var_raw[1].isupper()):
                        clean_name = var_raw[1:]
                    # Try to parse as list of integers
                    try:
                        vals = [int(v.strip()) for v in vals_raw.split(',')]
                        cycle_vars[clean_name] = vals
                    except ValueError:
                        pass

        if not kb_keys:
            continue

        run_link_name = name
        if not kb_run_id and cycle_vars:
            kb_run_id = run_link_name
        elif kb_run_id:
            run_link_name = kb_run_id

        keybinds.append(ParsedKeybind(
            section_name=name,
            key=kb_keys,
            back=kb_back,
            type=kb_type,
            condition=kb_condition,
            run_id=run_link_name,
            cycle_vars=cycle_vars
        ))

    # -- 4. Save/Load profiles ------------------------------------------------
    save_slots: dict = {}

    for name, body in sections.items():
        m = re.match(r'^CommandListSave(\w+)$', name)
        if not m:
            continue
        slot = m.group(1)
        slot_vals = {}
        for line in body:
            line = line.strip()
            if not line or line.startswith(';') or line.startswith('pre '):
                continue
            # $SlotVar = $OrigVar
            mv = re.match(r'^\$(\w+)\s*=\s*\$(\w+)', line)
            if mv:
                src = mv.group(2)
                # Normalize src
                src_clean = src
                if (src.startswith(D_PREFIX_CHAR) and len(src) > 1
                        and src[1].isupper()):
                    src_clean = src[1:]
                if src_clean not in IGNORE_VARS:
                    slot_vals[src_clean] = '__MIRROR__'
        if slot_vals:
            save_slots[slot] = slot_vals

    for slot_name, slot_vals in save_slots.items():
        profiles.append(ParsedProfile(
            name=f'Slot_{slot_name}',
            source='SAVE_SLOT',
            values=slot_vals
        ))

    # -- 5. KeyCycle - matrix presets -> In-Game Profiles ---------------------
    for kb in keybinds:
        if kb.section_name in ('KeyCycle', 'KeyDCycle') and kb.cycle_vars:
            max_len = max(len(v) for v in kb.cycle_vars.values())
            for i in range(max_len):
                preset_vals = {}
                for var_name, vals in kb.cycle_vars.items():
                    if i < len(vals):
                        preset_vals[var_name] = vals[i]
                profiles.append(ParsedProfile(
                    name=f'Outfit_{i}',
                    source='KEY_CYCLE',
                    values=preset_vals
                ))

    return variables, keybinds, profiles


# --- Report ------------------------------------------------------------------

def print_report(variables, keybinds, profiles):
    SEP = '-' * 70
    HDR = '=' * 70

    print(f'\n{HDR}')
    print(f'  RZMenu INI Import Preview')
    print(f'{HDR}\n')

    # -- Variables --
    main_vars = [v for v in variables.values() if v.variant == '']
    d_vars    = [v for v in variables.values() if v.variant != '']

    print(f'[1/3] VARIABLES -> rzm.rzm_values ({len(main_vars)} unique + {len(d_vars)} D-dups skipped)')
    print(SEP)
    for v in sorted(main_vars, key=lambda x: x.name):
        rand_info = f'  [RANDOM: 0..{v.val_max}]' if v.mark_random else ''
        print(f"  ValueProperty(name='{v.name}', default={v.default_value}, val_max={v.val_max}){rand_info}")

    if d_vars:
        d_names = ', '.join(sorted(v.name for v in d_vars[:10]))
        extra = f'... +{len(d_vars)-10} more' if len(d_vars) > 10 else ''
        print(f'\n  [!] D-prefix variants detected ({len(d_vars)} total) - NOT imported as duplicates.')
        print(f'  D-vars: {d_names}{extra}')
    print()

    # -- Keybinds --
    def is_d_variant(kb):
        stripped = kb.section_name.replace('Key', '', 1)
        return (stripped.startswith(D_PREFIX_CHAR) and len(stripped) > 1
                and stripped[1].isupper())

    unique_kbs = [kb for kb in keybinds if not is_d_variant(kb)]
    d_kb_count = len(keybinds) - len(unique_kbs)

    print(f'[2/3] KEYBINDS -> rzm.keybinds ({len(unique_kbs)} unique, {d_kb_count} D-dups skipped)')
    print(SEP)
    for kb in unique_kbs:
        cond_str = ''
        if kb.condition == '__menu_active__':
            cond_str = '  [only_menu_active=True]'
        elif kb.condition:
            cond_str = f"  [condition='{kb.condition}']"

        if kb.cycle_vars:
            items = list(kb.cycle_vars.items())[:3]
            vs = ', '.join(f'${k}=[{len(v)} vals, max={max(v)}]' for k, v in items)
            if len(kb.cycle_vars) > 3:
                vs += f' ... +{len(kb.cycle_vars)-3} more'
            print(f"  Keybind '{kb.section_name}' key={kb.key} type='{kb.type}'{cond_str}")
            print(f"    -> RunLink '{kb.run_id}': {vs}")
        else:
            print(f"  Keybind '{kb.section_name}' key={kb.key} type='{kb.type}' run='{kb.run_id}'{cond_str}")
    print()

    # -- Profiles --
    save_profiles  = [p for p in profiles if p.source == 'SAVE_SLOT']
    cycle_profiles = [p for p in profiles if p.source == 'KEY_CYCLE']

    print(f'[3/3] PROFILES -> in_game_profiles ({len(profiles)} total)')
    print(SEP)

    if save_profiles:
        print(f'  Save/Load slots ({len(save_profiles)}):')
        for p in save_profiles:
            print(f"    Profile '{p.name}' (SAVE_SLOT) -> {len(p.values)} vars")
            print(f"    -> global persist $RZProfile_{p.name}_<var> = <mirror>")

    if cycle_profiles:
        print(f'\n  KeyCycle presets ({len(cycle_profiles)}) - each = full variable state:')
        for p in cycle_profiles[:6]:
            sample = list(p.values.items())[:4]
            s = ', '.join(f'{k}={v}' for k, v in sample)
            if len(p.values) > 4:
                s += f' ... +{len(p.values)-4}'
            print(f"    Profile '{p.name}' -> [{s}]")
        if len(cycle_profiles) > 6:
            print(f'    ... and {len(cycle_profiles)-6} more presets')
    print()

    # -- Summary --
    print(HDR)
    print('  SUMMARY:')
    print(f'    ValueProperty imported:     {len(main_vars)}')
    print(f'    D-variant vars skipped:     {len(d_vars)}')
    print(f'    RZMKeybind imported:        {len(unique_kbs)}')
    print(f'    D-variant keybinds skipped: {d_kb_count}')
    print(f'    In-Game Profiles generated: {len(profiles)}')
    print(HDR)
    print()
    print('  NOT imported:')
    print('    - TextureOverride / Resource (mesh/hash data)')
    print('    - $active, $creditinfo (system vars)')
    print('    - global $ non-persist (runtime only)')
    print('    - drawindexed, vb0, ib, ps-t* (GPU commands)')
    print('    - run = CommandList\\global\\ (external deps)')
    print('    - [Present] section')
    print()


# --- Entry point -------------------------------------------------------------

if __name__ == '__main__':
    if len(sys.argv) < 2:
        ini_path = r'G:\XXMI\GIMI\Mods\Skirk Ultimate V2 - OG Body\DISABLEDSkirk Ultimate.ini'
        if not os.path.exists(ini_path):
            print('Usage: python import_ini_preview.py <path_to_mod.ini>')
            sys.exit(1)
    else:
        ini_path = sys.argv[1]

    print(f'Parsing: {ini_path}')
    variables, keybinds, profiles = parse_ini(ini_path)
    print_report(variables, keybinds, profiles)
