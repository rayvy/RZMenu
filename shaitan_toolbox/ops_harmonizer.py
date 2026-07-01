import bpy
import json
from collections import defaultdict, Counter
from datetime import datetime
from mathutils import Vector
from bpy.types import Operator
from bpy.props import StringProperty, IntProperty, BoolProperty

from .harmonizer_utils import (
    invalidate_matrix_suggestion_cache,
    tag_view3d_redraw,
    is_mask_group,
    build_bone_segments,
    object_world_scale,
    collect_group_fingerprints,
    canonical_name_for_mapping,
    build_assignment_conflicts,
    add_plan_item,
    rebuild_matrix_and_summary,
    selected_approved_row,
    selected_issue_item,
    assign_plan_item_to_canonical,
    find_plan_item_by_object_and_group_index,
    refresh_matrix_and_summary,
    generated_aux_name,
    BACKUP_TEXT,
    displace_existing_approved,
    get_lr_suffix,
    has_lr_suffix,
    apply_lr_suffix_to,
    strip_blender_collision_suffix,
)


# ============================================================
# LR-SAFE NAME PREFLIGHT
# ============================================================
# Blender appends .001/.002 AFTER the whole vertex-group name.
# That means a valid mirror name like "Forearm.L" becomes
# "Forearm.L.001", and naïve suffix checks stop seeing .L/.R.
# These helpers treat Blender collision tails as garbage BEFORE
# any deduplication, pairing, or final rename happens.

import re

_RZM_BLENDER_AUTO_SUFFIX_RE = re.compile(r"(?:\.\d{3})+$")
_RZM_FINAL_LR_RE = re.compile(r"^(?P<base>.+?)(?P<sep>[._\-\s])(?P<side>[LRlr])$")
_RZM_SAFE_NAME_RE = re.compile(r"[^0-9A-Za-zА-Яа-я_\.\-\s\+]+")


def _rzm_strip_auto_suffix(name):
    """Remove Blender's trailing .001/.002 collision suffixes.

    The local regex is intentionally used even though harmonizer_utils also
    exposes strip_blender_collision_suffix: old versions missed names like
    Bone.L.001 because the LR suffix was not at the literal end anymore.
    """
    name = str(name or "").strip()
    try:
        name = strip_blender_collision_suffix(name)
    except Exception:
        pass
    return _RZM_BLENDER_AUTO_SUFFIX_RE.sub("", name).strip()


def _rzm_sanitize_name(name, fallback="Aux"):
    name = _rzm_strip_auto_suffix(name)
    name = _RZM_SAFE_NAME_RE.sub("_", name)
    name = re.sub(r"\s+", " ", name).strip(" ._-")
    return name or fallback


def _rzm_lr_parts(name):
    """Return (side, base, suffix, clean_name).

    side:  'L', 'R', or None
    base:  name without LR suffix and without Blender .NNN tail
    suffix: original separator + uppercase side, e.g. '.L', '_R', or None
    clean_name: full cleaned name without Blender .NNN
    """
    clean = _rzm_sanitize_name(name)
    match = _RZM_FINAL_LR_RE.match(clean)
    if not match:
        return None, clean, None, clean

    side = match.group("side").upper()
    sep = match.group("sep") or "."
    base = match.group("base").strip(" ._-") or clean
    return side, base, f"{sep}{side}", f"{base}{sep}{side}"


def _rzm_name_key(name):
    return _rzm_sanitize_name(name).casefold()


def _rzm_base_key(name):
    _side, base, _suffix, _clean = _rzm_lr_parts(name)
    return re.sub(r"[._\-\s]+", "_", base).strip("_").casefold()


def _rzm_stem_counter_parts(stem):
    """Split readable Harmonizer counter from a name stem.

    Clavicle2   -> (Clavicle2, 1)
    Clavicle2_2 -> (Clavicle2, 2)
    Clavicle_12 -> (Clavicle, 12)

    Only our own underscore counter is treated as a counter.  Digits that are
    part of the real bone name stay untouched.
    """
    stem = _rzm_sanitize_name(_rzm_lr_parts(stem)[1])
    m = re.match(r"^(?P<root>.+?)_(?P<num>[2-9]\d*)$", stem)
    if not m:
        return stem, 1
    root = m.group("root").strip(" ._-") or stem
    return root, int(m.group("num"))


def _rzm_numbered_stem(root, counter):
    root = _rzm_sanitize_name(root)
    return root if int(counter) <= 1 else f"{root}_{int(counter)}"


def _rzm_apply_suffix(base, suffix):
    base = _rzm_lr_parts(base)[1]
    base = _rzm_sanitize_name(base)
    return f"{base}{suffix}" if suffix else base


def _rzm_conflict_name(candidate, used_names):
    """Create a readable unique name without Blender-style .001.

    Counters are inserted before .L/.R and increment an existing Harmonizer
    counter instead of nesting it:
        Thigh.R        -> Thigh_2.R
        Belly3.R       -> Belly3_2.R
        Clavicle2_2.R  -> Clavicle2_3.R
        Torso          -> Torso_2
    """
    side, base, suffix, clean = _rzm_lr_parts(candidate)
    suffix = suffix or ""
    stem = base if side else clean
    root, start_counter = _rzm_stem_counter_parts(stem)

    first_stem = _rzm_numbered_stem(root, start_counter)
    first_name = _rzm_apply_suffix(first_stem, suffix) if side else first_stem
    if first_name not in used_names:
        return first_name, False

    counter = max(start_counter + 1, 2)
    while True:
        stem = _rzm_numbered_stem(root, counter)
        candidate = _rzm_apply_suffix(stem, suffix) if side else stem
        if candidate not in used_names:
            return candidate, True
        counter += 1


def _rzm_item_status_rank(item):
    status = getattr(item, "status", "")
    return {
        "APPROVED": 40,
        "CONFLICT": 30,
        "UNKNOWN": 20,
        "IGNORED": 0,
    }.get(status, 10)


def _rzm_get_item_guard(item):
    try:
        return bool(item.get("_updating_cluster", False))
    except Exception:
        return bool(getattr(item, "_updating_cluster", False))


def _rzm_set_item_guard(item, value):
    """Temporarily suppress cluster-sync update callbacks on plan items.

    The UI has cluster synchronization: changing resolved_name on one item can
    copy the same name into every item in the cluster.  That is useful for
    normal manual edits, but it is poison inside LR preflight because a mirror
    pair must be assigned as stem.L + stem.R, not stem.R + stem.R.
    
    Blender PropertyGroup supports custom-property syntax, while unit-test
    fakes usually only support normal attributes, so support both.
    """
    try:
        item["_updating_cluster"] = bool(value)
    except Exception:
        try:
            setattr(item, "_updating_cluster", bool(value))
        except Exception:
            pass


def _rzm_silent_set_resolved_name(item, new_name):
    old_guard = _rzm_get_item_guard(item)
    _rzm_set_item_guard(item, True)
    try:
        item.resolved_name = new_name
    finally:
        _rzm_set_item_guard(item, old_guard)


def _rzm_push_plan_guard(plan):
    """Guard every plan row against cluster-name update callbacks.

    Some Blender PropertyGroup update callbacks can sync the whole cluster when
    one resolved_name changes.  Pair-safe preflight must be a transaction, so
    all rows are guarded for the entire pass, not only the row currently being
    edited.
    """
    state = []
    for item in list(plan or []):
        old_guard = _rzm_get_item_guard(item)
        state.append((item, old_guard))
        _rzm_set_item_guard(item, True)
    return state


def _rzm_pop_plan_guard(state):
    for item, old_guard in reversed(state or []):
        _rzm_set_item_guard(item, old_guard)


def _rzm_item_debug_dict(item, plan_index=None):
    orig_side, orig_base, orig_suffix, orig_clean = _rzm_lr_parts(getattr(item, "original_name", ""))
    res_side, res_base, res_suffix, res_clean = _rzm_lr_parts(getattr(item, "resolved_name", ""))
    data = {
        "plan_index": plan_index,
        "object": getattr(item, "object_name", ""),
        "vg_index": int(getattr(item, "group_index", -1)),
        "original_name": getattr(item, "original_name", ""),
        "resolved_name": getattr(item, "resolved_name", ""),
        "status": getattr(item, "status", ""),
        "cluster_id": getattr(item, "cluster_id", ""),
        "manual_override": bool(getattr(item, "manual_override", False)),
        "create_bone": bool(getattr(item, "create_bone", False)),
        "is_helper": bool(getattr(item, "is_helper", False)),
        "decision_reason": getattr(item, "decision_reason", ""),
        "original_lr": {
            "side": orig_side,
            "base": orig_base,
            "suffix": orig_suffix,
            "clean": orig_clean,
        },
        "resolved_lr": {
            "side": res_side,
            "base": res_base,
            "suffix": res_suffix,
            "clean": res_clean,
        },
    }
    return data


def _rzm_plan_index_lookup(plan):
    return {id(item): i for i, item in enumerate(list(plan or []))}


def _rzm_duplicate_name_groups(items, plan_index_by_id=None):
    buckets = defaultdict(list)
    for item in list(items or []):
        name = _rzm_sanitize_name(getattr(item, "resolved_name", ""))
        buckets[name].append(item)

    groups = []
    for name, rows in sorted(buckets.items(), key=lambda kv: (kv[0].casefold(), len(kv[1]))):
        if len(rows) <= 1:
            continue
        groups.append({
            "name": name,
            "count": len(rows),
            "items": [
                _rzm_item_debug_dict(row, None if plan_index_by_id is None else plan_index_by_id.get(id(row)))
                for row in sorted(rows, key=lambda r: int(getattr(r, "group_index", -1)))
            ],
        })
    return groups


def _rzm_blender_suffix_groups(items, plan_index_by_id=None):
    groups = []
    for item in list(items or []):
        name = getattr(item, "resolved_name", "") or ""
        if _RZM_BLENDER_AUTO_SUFFIX_RE.search(name):
            groups.append(_rzm_item_debug_dict(item, None if plan_index_by_id is None else plan_index_by_id.get(id(item))))
    return groups


def _rzm_broken_pair_details(pair_contracts, plan_index_by_id=None):
    broken = []
    for contract in list(pair_contracts or []):
        item_l = contract["L"]
        item_r = contract["R"]
        l_side, l_base, _ls, _lc = _rzm_lr_parts(getattr(item_l, "resolved_name", ""))
        r_side, r_base, _rs, _rc = _rzm_lr_parts(getattr(item_r, "resolved_name", ""))
        if l_side != "L" or r_side != "R" or l_base != r_base:
            broken.append({
                "base_key": contract.get("base_key", ""),
                "pair_index": contract.get("pair_index", 0),
                "cluster_id": contract.get("cluster_id", ""),
                "L": _rzm_item_debug_dict(item_l, None if plan_index_by_id is None else plan_index_by_id.get(id(item_l))),
                "R": _rzm_item_debug_dict(item_r, None if plan_index_by_id is None else plan_index_by_id.get(id(item_r))),
                "reason": "resolved names are not identical except for final .L/.R",
            })
    return broken


def _rzm_write_name_error(scene, *, stage, object_name, reason, items, pair_contracts=None, extra=None):
    plan_index_by_id = _rzm_plan_index_lookup(getattr(scene, "rzm_weight_plan", []))
    payload = {
        "stage": stage,
        "object": object_name,
        "reason": reason,
        "duplicate_groups": _rzm_duplicate_name_groups(items, plan_index_by_id),
        "blender_suffix_rows": _rzm_blender_suffix_groups(items, plan_index_by_id),
        "broken_mirror_pairs": _rzm_broken_pair_details(pair_contracts or [], plan_index_by_id),
        "extra": extra or {},
    }
    try:
        scene["rzm_harmonizer_name_error"] = json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception:
        pass

    print("\n" + "=" * 90)
    print("[RZM Weight Harmonizer] NAME PREFLIGHT ERROR")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("=" * 90 + "\n")
    return payload


def _rzm_error_short_message(payload):
    dups = payload.get("duplicate_groups") or []
    if dups:
        first = dups[0]
        members = []
        for row in first.get("items", [])[:4]:
            members.append(
                f"#{row.get('vg_index')} {row.get('original_name')} -> {row.get('resolved_name')}"
                + (f" [cluster={row.get('cluster_id')}]" if row.get('cluster_id') else "")
            )
        tail = " | ".join(members)
        more = " ..." if len(first.get("items", [])) > 4 else ""
        return f"duplicate '{first.get('name')}' used by {first.get('count')} rows: {tail}{more}"

    suffix_rows = payload.get("blender_suffix_rows") or []
    if suffix_rows:
        row = suffix_rows[0]
        return f"Blender suffix survived at #{row.get('vg_index')}: {row.get('original_name')} -> {row.get('resolved_name')}"

    broken = payload.get("broken_mirror_pairs") or []
    if broken:
        row = broken[0]
        return f"broken mirror pair {row.get('base_key')}: {row.get('L', {}).get('resolved_name')} / {row.get('R', {}).get('resolved_name')}"

    return payload.get("reason", "unknown name preflight error")


def _rzm_choose_mirror_stem(item_l, item_r):
    """Pick the ONE stem owned by a remembered L/R pair.

    This is the contract rule: a remembered mirror pair is never deduplicated
    as two independent rows.  If either side already carries a readable
    Harmonizer counter, the whole pair is promoted to that counter.

    Example:
        8.L candidate -> Clavicle2.L
        8.R candidate -> Clavicle2_2.R
        pair stem     -> Clavicle2_2
        final         -> Clavicle2_2.L / Clavicle2_2.R
    """
    _ls, l_base, _l_suffix, _l_clean = _rzm_lr_parts(getattr(item_l, "resolved_name", ""))
    _rs, r_base, _r_suffix, _r_clean = _rzm_lr_parts(getattr(item_r, "resolved_name", ""))

    l_root, l_counter = _rzm_stem_counter_parts(l_base)
    r_root, r_counter = _rzm_stem_counter_parts(r_base)

    if l_root.casefold() == r_root.casefold():
        # Highest counter wins for BOTH sides.  No "I grabbed Clavicle first,
        # you get Clavicle_2" nonsense inside a mirror contract.
        return _rzm_numbered_stem(l_root, max(l_counter, r_counter))

    # If roots differ, prefer the more explicit countered candidate.  This
    # covers user/manual edits that moved one side away from the initial match.
    if l_counter != r_counter:
        root = l_root if l_counter > r_counter else r_root
        return _rzm_numbered_stem(root, max(l_counter, r_counter))

    # Otherwise choose the stronger UI/solver decision, but still only the stem.
    def quality(item):
        return (
            1 if getattr(item, "manual_override", False) else 0,
            _rzm_item_status_rank(item),
            0 if getattr(item, "create_bone", False) else 1,
            -int(getattr(item, "group_index", 0)),
        )

    leader = item_l if quality(item_l) >= quality(item_r) else item_r
    return _rzm_lr_parts(getattr(leader, "resolved_name", ""))[1]


def _rzm_preflight_plan_names(scene, settings, *, stage="build"):
    """Normalize and deduplicate plan names BEFORE touching Blender names.

    This function treats original mirror pairs as an atomic contract.
    A pair is not two independent names.  It is one stem allocation that
    produces stem.L and stem.R together.  If either side conflicts, the
    whole pair moves to stem_2.L and stem_2.R, never only one side.

    Guarantees for non-ignored plan items:
      * no trailing Blender .001/.002 tails;
      * original .L/.R survives even if the original was .L.001/.R.001;
      * remembered mirror pairs end as the same stem + opposite sides;
      * names are unique inside every mesh object;
      * conflict counters are readable (_2, _3), never Blender .001.

    A JSON report is stored on the scene for debugging.  If something still
    manages to break the contract, rzm_harmonizer_name_error contains the exact
    duplicate/broken rows.
    """
    empty_report = {"stage": stage, "objects": {}, "mirror_pairs": [], "renamed": [], "conflicts": [], "errors": []}
    if not scene.rzm_weight_plan:
        return empty_report

    preserve_lr = bool(getattr(settings, "preserve_lr_suffixes", True))
    grouped = defaultdict(list)
    report = {"stage": stage, "objects": {}, "mirror_pairs": [], "renamed": [], "conflicts": [], "errors": []}
    plan_guard_state = _rzm_push_plan_guard(scene.rzm_weight_plan)

    try:
        def item_key(item):
            return (getattr(item, "object_name", ""), int(getattr(item, "group_index", -1)))

        def set_resolved(item, new_name, reason=""):
            new_name = _rzm_sanitize_name(new_name)
            old_name = getattr(item, "resolved_name", "")
            if old_name == new_name:
                return False
            # All plan items are guarded for the full preflight transaction, but
            # keep this setter guarded too for external direct calls/tests.
            _rzm_silent_set_resolved_name(item, new_name)
            if reason:
                old_reason = getattr(item, "decision_reason", "") or ""
                if reason not in old_reason:
                    item.decision_reason = (old_reason + "; " if old_reason else "") + reason
            report["renamed"].append({
                "object": getattr(item, "object_name", ""),
                "index": int(getattr(item, "group_index", -1)),
                "from": old_name,
                "to": new_name,
                "reason": reason,
            })
            return True

        def suffix_for_pair(item_l, item_r):
            _ls, _lb, l_suffix, _lc = _rzm_lr_parts(getattr(item_l, "original_name", ""))
            _rs, _rb, r_suffix, _rc = _rzm_lr_parts(getattr(item_r, "original_name", ""))
            # Pair must be byte-identical except for the last side letter.  Prefer
            # dot style because Blender and armature symmetry tools understand it.
            if (l_suffix and l_suffix.startswith(".")) or (r_suffix and r_suffix.startswith(".")):
                sep = "."
            elif l_suffix:
                sep = l_suffix[0]
            elif r_suffix:
                sep = r_suffix[0]
            else:
                sep = "."
            return f"{sep}L", f"{sep}R"

        def pair_names_for_stem(stem, l_suffix, r_suffix):
            stem = _rzm_sanitize_name(_rzm_lr_parts(stem)[1])
            return _rzm_apply_suffix(stem, l_suffix), _rzm_apply_suffix(stem, r_suffix)

        def allocate_pair_names(stem, l_suffix, r_suffix, used):
            """Allocate stem.L/stem.R atomically.

            If either side is occupied, both sides receive the same readable
            counter.  Existing Harmonizer counters are incremented rather than
            nested:
                Clavicle2_2.L/R occupied -> Clavicle2_3.L/R
            """
            root, start_counter = _rzm_stem_counter_parts(stem)
            counter = start_counter
            while True:
                attempt_stem = _rzm_numbered_stem(root, counter)
                left_name, right_name = pair_names_for_stem(attempt_stem, l_suffix, r_suffix)
                if left_name not in used and right_name not in used:
                    return left_name, right_name, counter != start_counter
                counter += 1

        def mark_duplicate_created(item, tag):
            item.create_bone = True
            item.is_helper = True
            reason = getattr(item, "decision_reason", "") or ""
            if tag not in reason:
                item.decision_reason = (reason + "; " if reason else "") + tag

        # First pass: clean Blender .NNN garbage and restore sacred original LR side.
        # This pass is intentionally not responsible for uniqueness.  It only creates
        # a clean candidate that later pair/single allocation can consume.
        for item in scene.rzm_weight_plan:
            if item.status == "IGNORED":
                continue

            grouped[item.object_name].append(item)

            candidate = _rzm_sanitize_name(item.resolved_name or item.original_name)
            if preserve_lr:
                orig_side, _orig_base, orig_suffix, _orig_clean = _rzm_lr_parts(item.original_name)
                if orig_side and orig_suffix:
                    candidate = _rzm_apply_suffix(candidate, orig_suffix)

            set_resolved(item, candidate, "name preflight cleaned Blender suffix")

        # Second pass: build remembered mirror contracts from ORIGINAL names, not from
        # current guesses.  Blender may mutate current names, candidates may be wrong,
        # clusters may sync both sides to one name, but original .L/.R is the truth.
        pair_contracts_by_object = defaultdict(list)
        paired_keys = set()

        if preserve_lr:
            existing_ids = {item.cluster_id for item in scene.rzm_weight_plan if item.cluster_id}
            mirror_counter = 0

            def new_mirror_cluster_id():
                nonlocal mirror_counter
                while f"mirror_{mirror_counter}" in existing_ids:
                    mirror_counter += 1
                cid = f"mirror_{mirror_counter}"
                existing_ids.add(cid)
                mirror_counter += 1
                return cid

            for object_name, items in grouped.items():
                by_original_base = defaultdict(lambda: {"L": [], "R": []})
                for item in items:
                    side, base, _suffix, _clean = _rzm_lr_parts(item.original_name)
                    if side not in {"L", "R"}:
                        continue
                    by_original_base[_rzm_base_key(base)][side].append(item)

                for base_key, sides in by_original_base.items():
                    left_items = sorted(sides["L"], key=lambda row: row.group_index)
                    right_items = sorted(sides["R"], key=lambda row: row.group_index)
                    pair_count = min(len(left_items), len(right_items))
                    for pair_index in range(pair_count):
                        item_l = left_items[pair_index]
                        item_r = right_items[pair_index]
                        l_suffix, r_suffix = suffix_for_pair(item_l, item_r)
                        stem = _rzm_choose_mirror_stem(item_l, item_r)

                        cid = item_l.cluster_id or item_r.cluster_id or new_mirror_cluster_id()
                        item_l.cluster_id = cid
                        item_r.cluster_id = cid

                        # If one side was accepted and the twin was unresolved, promote
                        # the twin.  Names are still side-specific and allocated later.
                        if item_l.status == "APPROVED" and item_r.status not in {"APPROVED", "IGNORED"}:
                            item_r.status = "APPROVED"
                            item_r.manual_override = True
                            item_r.decision_reason = "mirror pair auto-resolved from .L partner"
                        elif item_r.status == "APPROVED" and item_l.status not in {"APPROVED", "IGNORED"}:
                            item_l.status = "APPROVED"
                            item_l.manual_override = True
                            item_l.decision_reason = "mirror pair auto-resolved from .R partner"

                        pair_contracts_by_object[object_name].append({
                            "base_key": base_key,
                            "pair_index": pair_index,
                            "cluster_id": cid,
                            "stem": stem,
                            "L": item_l,
                            "R": item_r,
                            "l_suffix": l_suffix,
                            "r_suffix": r_suffix,
                        })
                        paired_keys.add(item_key(item_l))
                        paired_keys.add(item_key(item_r))

        # Third pass: per-object uniqueness.  Mirror pairs are allocated FIRST and
        # atomically.  Singles then fit around those reserved names.  This prevents:
        #     6.L -> Clavicle.R
        #     6.R -> Clavicle_3.R
        # because the pair asks for two names together: Clavicle.L + Clavicle.R.
        for object_name, items in grouped.items():
            used = set()
            final_names = []

            pair_contracts = sorted(
                pair_contracts_by_object.get(object_name, []),
                key=lambda c: min(c["L"].group_index, c["R"].group_index),
            )

            for contract in pair_contracts:
                item_l = contract["L"]
                item_r = contract["R"]
                old_l = item_l.resolved_name
                old_r = item_r.resolved_name
                left_name, right_name, had_conflict = allocate_pair_names(
                    contract["stem"],
                    contract["l_suffix"],
                    contract["r_suffix"],
                    used,
                )
                used.add(left_name)
                used.add(right_name)
                final_names.extend([left_name, right_name])

                set_resolved(item_l, left_name, "mirror contract preserved .L/.R side")
                set_resolved(item_r, right_name, "mirror contract preserved .L/.R side")

                if had_conflict:
                    mark_duplicate_created(item_l, "mirror pair duplicate resolved before Blender rename")
                    mark_duplicate_created(item_r, "mirror pair duplicate resolved before Blender rename")
                    report["conflicts"].append({
                        "object": object_name,
                        "type": "mirror_pair",
                        "base": contract["base_key"],
                        "requested_stem": contract["stem"],
                        "resolved_L": left_name,
                        "resolved_R": right_name,
                    })

                report["mirror_pairs"].append({
                    "object": object_name,
                    "base": contract["base_key"],
                    "pair_index": contract["pair_index"],
                    "cluster_id": contract["cluster_id"],
                    "requested_stem": contract["stem"],
                    "L": {"index": int(item_l.group_index), "from": old_l, "to": item_l.resolved_name},
                    "R": {"index": int(item_r.group_index), "from": old_r, "to": item_r.resolved_name},
                })

            singles = [item for item in sorted(items, key=lambda row: row.group_index) if item_key(item) not in paired_keys]
            for item in singles:
                candidate = _rzm_sanitize_name(item.resolved_name or item.original_name)

                if preserve_lr:
                    _orig_side, _orig_base, orig_suffix, _orig_clean = _rzm_lr_parts(item.original_name)
                    if orig_suffix:
                        candidate = _rzm_apply_suffix(candidate, orig_suffix)

                final_name, had_conflict = _rzm_conflict_name(candidate, used)
                used.add(final_name)
                final_names.append(final_name)

                if final_name != item.resolved_name:
                    set_resolved(item, final_name, "single duplicate resolved before Blender rename" if had_conflict else "name preflight normalized")

                if had_conflict:
                    mark_duplicate_created(item, "duplicate resolved before Blender rename")
                    report["conflicts"].append({
                        "object": object_name,
                        "type": "single",
                        "index": int(item.group_index),
                        "requested": candidate,
                        "resolved": final_name,
                    })

            # Validation: every remembered pair must still be identical except side.
            plan_index_by_id = _rzm_plan_index_lookup(scene.rzm_weight_plan)
            duplicate_groups = _rzm_duplicate_name_groups(items, plan_index_by_id)
            suffix_rows = _rzm_blender_suffix_groups(items, plan_index_by_id)
            broken_pairs = _rzm_broken_pair_details(pair_contracts, plan_index_by_id)

            report["objects"][object_name] = {
                "planned": len(items),
                "unique_final_names": len({getattr(item, "resolved_name", "") for item in items}),
                "has_duplicates": bool(duplicate_groups),
                "has_blender_suffix": bool(suffix_rows),
                "broken_mirror_pairs": broken_pairs,
                "duplicate_groups": duplicate_groups,
                "blender_suffix_rows": suffix_rows,
            }

            if duplicate_groups or suffix_rows or broken_pairs:
                payload = _rzm_write_name_error(
                    scene,
                    stage=stage,
                    object_name=object_name,
                    reason="post-preflight validation failed",
                    items=items,
                    pair_contracts=pair_contracts,
                    extra={"object_report": report["objects"][object_name]},
                )
                report["errors"].append(payload)

        try:
            scene["rzm_harmonizer_name_preflight"] = json.dumps(report, ensure_ascii=False, indent=2)
        except Exception:
            pass

        return report
    finally:
        _rzm_pop_plan_guard(plan_guard_state)

def _rzm_preflight_after_edit(scene, *, stage="edit"):
    """Run pair-safe preflight after UI/manual edits.

    Several operators change one plan row at a time.  If the row belongs to a
    remembered mirror pair, the partner must be repaired immediately so the UI
    and the final Apply step see the same pair-safe names.
    """
    try:
        _rzm_preflight_plan_names(scene, scene.rzm_weight_settings, stage=stage)
    except Exception as exc:
        print(f"[RZM Weight Harmonizer] name preflight failed at {stage}: {exc}")

# ============================================================
# MIRROR PAIR POST-PROCESSING
# ============================================================

def _resolve_mirror_pairs(scene):
    """Compatibility wrapper used by Build Plan.

    The old implementation tried to fix .L/.R after the plan was already
    built, but it looked at raw names.  Raw Blender names may be .L.001,
    therefore the pair was invisible.  The real work now lives in
    _rzm_preflight_plan_names(), which strips .001 before LR detection,
    remembers complete mirror pairs, and deduplicates final names before
    Blender can mutate them.
    """
    settings = scene.rzm_weight_settings
    if not getattr(settings, "preserve_lr_suffixes", True):
        return
    _rzm_preflight_plan_names(scene, settings, stage="mirror-postprocess")


class RZM_OT_build_plan(Operator):
    bl_idname = "rzm_weights.build_plan"
    bl_label = "Build Remap Plan"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        settings = scene.rzm_weight_settings
        armature_obj = settings.target_armature
        reference_obj = settings.reference_mesh
        if armature_obj is None or armature_obj.type != "ARMATURE":
            self.report({"ERROR"}, "Specify the target armature")
            return {"CANCELLED"}
        if reference_obj is None or reference_obj.type != "MESH":
            self.report({"ERROR"}, "Specify the canonical reference mesh")
            return {"CANCELLED"}
        target_meshes = [obj for obj in context.selected_objects if obj.type == "MESH" and obj != reference_obj]
        if not target_meshes:
            self.report({"ERROR"}, "Select the target components")
            return {"CANCELLED"}

        scene.rzm_weight_plan.clear()
        scene.rzm_approved_matrix.clear()
        scene.rzm_component_summary.clear()
        invalidate_matrix_suggestion_cache()
        depsgraph = context.evaluated_depsgraph_get()
        bone_segments = build_bone_segments(armature_obj)
        character_scale = max(object_world_scale(reference_obj), object_world_scale(armature_obj))

        try:
            reference_fps = [fp for fp in collect_group_fingerprints(reference_obj, depsgraph, bone_segments, character_scale) if not is_mask_group(fp["name"])]
        except RuntimeError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        armature_names = {bone.name for bone in armature_obj.data.bones}
        generated_reserved = set(armature_names)
        generated_reserved.update(canonical_name_for_mapping(fp["name"], settings) for fp in reference_fps)
        unknown_registry = []

        all_target_fps = []
        for target_obj in sorted(target_meshes, key=lambda obj: obj.name.casefold()):
            try:
                target_fps = collect_group_fingerprints(target_obj, depsgraph, bone_segments, character_scale)
            except RuntimeError as error:
                self.report({"ERROR"}, str(error))
                return {"CANCELLED"}

            for fp in target_fps:
                fp["object_name"] = target_obj.name
                fp["target_obj"] = target_obj
                if is_mask_group(fp["name"]):
                    add_plan_item(scene, target_obj, fp, "IGNORED", fp["name"], 1.0, 1.0, [], False, False, reason="Mask* ignored")
                else:
                    all_target_fps.append(fp)

        # Группировка схожих групп разных компонентов (кластеризация)
        clusters = []
        from .harmonizer_utils import fingerprint_similarity

        if settings.match_mode == 'FBX':
            for fp in all_target_fps:
                clusters.append([fp])
        else:
            for fp in all_target_fps:
                best_cluster = None
                best_sim = -1.0
                for cluster in clusters:
                    if any(other["object_name"] == fp["object_name"] for other in cluster):
                        continue
                    leader = cluster[0]
                    sim = fingerprint_similarity(fp, leader, character_scale)
                    if sim >= settings.consensus_threshold and sim > best_sim:
                        best_cluster = cluster
                        best_sim = sim

                if best_cluster is not None:
                    best_cluster.append(fp)
                else:
                    clusters.append([fp])

        # Печать логов кластеризации в консоль
        print(f"\n--- [RZM Weight Harmonizer] Clustered {len(all_target_fps)} groups into {len(clusters)} clusters ---")
        multi_member_clusters_count = 0
        for i, cluster in enumerate(clusters):
            if len(cluster) > 1:
                multi_member_clusters_count += 1
                leader = cluster[0]
                print(f"Cluster {multi_member_clusters_count} (Leader: {leader['object_name']}[{leader['index']:03d}] {leader['name']}):")
                for fp in cluster:
                    sim = fingerprint_similarity(fp, leader, character_scale) if fp != leader else 1.0
                    print(f"  * {fp['object_name']}[{fp['index']:03d}] {fp['name']} (similarity to leader: {sim * 100:.1f}%)")
        if multi_member_clusters_count == 0:
            print("No multi-mesh clusters found.")
        print("-" * 50 + "\n")

        # Map each fingerprint back to its cluster ID
        fp_to_cluster_id = {}
        for i, cluster in enumerate(clusters):
            if len(cluster) > 1:
                cid = f"cluster_{i}"
                for fp in cluster:
                    fp_to_cluster_id[(fp["object_name"], fp["index"])] = cid

        # Расчет консенсусных кандидатов для каждого кластера
        from .harmonizer_utils import top_candidates
        fp_candidates = {}

        for cluster in clusters:
            bone_max_scores = {}
            bone_fps = {}
            for fp in cluster:
                candidates = top_candidates(fp, reference_fps, character_scale, settings, limit=5)
                fp_candidates[(fp["object_name"], fp["index"])] = candidates
                for ref_fp, score in candidates:
                    ref_name = ref_fp["name"]
                    if score > bone_max_scores.get(ref_name, -1.0):
                        bone_max_scores[ref_name] = score
                        bone_fps[ref_name] = ref_fp

            consensus_candidates = []
            for ref_name, max_score in sorted(bone_max_scores.items(), key=lambda item: item[1], reverse=True):
                consensus_candidates.append((bone_fps[ref_name], max_score))
            consensus_candidates = consensus_candidates[:5]

            for fp in cluster:
                fp_candidates[(fp["object_name"], fp["index"])] = consensus_candidates

        # Подготовка глобального списка prepared
        prepared = []
        for fp in all_target_fps:
            candidates = fp_candidates[(fp["object_name"], fp["index"])]
            prepared.append((fp, candidates))

        prepared.sort(key=lambda row: row[1][0][1] if row[1] else 0.0, reverse=True)
        assignment_conflicts = build_assignment_conflicts(prepared, settings.conflict_threshold, settings.assignment_margin)

        claimed_by_object = defaultdict(set)
        cluster_aux_name = {}

        for fp, candidates in prepared:
            target_obj = fp["target_obj"]
            claimed = claimed_by_object[target_obj.name]

            available = [row for row in candidates if row[0]["name"] not in claimed]
            best = available[0] if available else (candidates[0] if candidates else None)
            second = available[1] if len(available) > 1 else None
            best_score = best[1] if best else 0.0
            second_score = second[1] if second else 0.0
            margin = best_score - second_score

            is_fbx_mode = (settings.match_mode == 'FBX')

            if best and (is_fbx_mode or best_score >= settings.conflict_threshold):
                resolved_name = best[0]["name"]
                claimed.add(resolved_name)
                cluster_key = (fp["object_name"], fp["index"])
                conflict_names = sorted(assignment_conflicts.get(cluster_key, set()))
                has_local_rival = second is not None and (is_fbx_mode or second_score >= settings.conflict_threshold) and margin < settings.unique_margin
                has_assignment_rival = bool(conflict_names)

                if has_local_rival or has_assignment_rival:
                    reasons = []
                    if has_local_rival:
                        reasons.append("close candidate")
                    if has_assignment_rival:
                        reasons.append("multiple weights compete")
                    status = "CONFLICT"
                    reason = ", ".join(reasons)
                else:
                    status = "APPROVED"
                    reason = "strong score" if best_score >= settings.approved_threshold else "clean isolated match promoted above Floor"
                    if is_fbx_mode:
                        reason = "FBX direct match"

                # Вычисляем оригинальный скор без консенсуса для вывода инфо
                individual_candidates = top_candidates(fp, reference_fps, character_scale, settings, limit=1)
                orig_score = individual_candidates[0][1] if individual_candidates else 0.0
                if not is_fbx_mode and orig_score < settings.conflict_threshold and best_score >= settings.conflict_threshold:
                    reason += f" (consensus boost from {orig_score*100:.0f}%)"

                add_plan_item(
                    scene,
                    target_obj,
                    fp,
                    status,
                    resolved_name,
                    best_score,
                    margin,
                    candidates,
                    False if is_fbx_mode else (resolved_name not in armature_names),
                    False,
                    reason,
                    ", ".join(conflict_names),
                    cluster_id=fp_to_cluster_id.get((fp["object_name"], fp["index"]), "")
                )
                continue

            # Определение Aux-имени для UNKNOWN
            leader_fp = None
            for c in clusters:
                if fp in c:
                    leader_fp = c[0]
                    break
            leader_key = (leader_fp["object_name"], leader_fp["index"]) if leader_fp else (fp["object_name"], fp["index"])

            clustered_name = cluster_aux_name.get(leader_key)
            if clustered_name is None:
                for registry in unknown_registry:
                    if registry["object_name"] == target_obj.name:
                        continue
                    if fingerprint_similarity(fp, registry["fingerprint"], character_scale) >= settings.unknown_cluster_threshold:
                        clustered_name = registry["resolved_name"]
                        break

            if clustered_name is None:
                clustered_name = generated_aux_name(fp["nearest_bone"], fp["name"], generated_reserved)
                unknown_registry.append({"object_name": target_obj.name, "fingerprint": fp, "resolved_name": clustered_name})

            cluster_aux_name[leader_key] = clustered_name
            add_plan_item(
                scene,
                target_obj,
                fp,
                "UNKNOWN",
                clustered_name,
                best_score,
                margin,
                candidates,
                True,
                False,
                "no candidate above Floor",
                cluster_id=fp_to_cluster_id.get((fp["object_name"], fp["index"]), "")
            )

        # Final plan names are normalized before UI/export sees them.
        # This is the pre-dedup pass: no .001 tails, preserved .L/.R,
        # and no same-name collisions inside a mesh.
        _rzm_preflight_plan_names(scene, settings, stage="build")
        rebuild_matrix_and_summary(scene, target_meshes)
        self.report({"INFO"}, "Remap plan built")
        tag_view3d_redraw()
        return {"FINISHED"}


class RZM_OT_open_matrix_cell_editor(Operator):
    bl_idname = "rzm_weights.open_matrix_cell_editor"
    bl_label = "Edit Matrix Cell"
    object_name: StringProperty()

    def execute(self, context):
        settings = context.scene.rzm_weight_settings
        settings.matrix_editor_object = self.object_name
        settings.matrix_manual_group_index = -1
        tag_view3d_redraw()
        return {"FINISHED"}


class RZM_OT_assign_matrix_suggestion(Operator):
    bl_idname = "rzm_weights.assign_matrix_suggestion"
    bl_label = "Attach Suggested VG"
    plan_index: IntProperty()
    canonical_name: StringProperty()

    def execute(self, context):
        scene = context.scene
        displaced, error, cl_info = assign_plan_item_to_canonical(scene, self.plan_index, self.canonical_name)
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        _rzm_preflight_after_edit(scene, stage="assign-matrix-suggestion")
        refresh_matrix_and_summary(scene)
        self.report({"INFO"}, f"Assigned{cl_info}" + ("; previous owner returned to Conflict" if displaced else ""))
        return {"FINISHED"}


class RZM_OT_assign_matrix_manual_index(Operator):
    bl_idname = "rzm_weights.assign_matrix_manual_index"
    bl_label = "Attach VG index"

    def execute(self, context):
        scene = context.scene
        settings = scene.rzm_weight_settings
        row = selected_approved_row(scene)
        if row is None:
            self.report({"ERROR"}, "Select an Approved Matrix row first")
            return {"CANCELLED"}
        if not settings.matrix_editor_object:
            self.report({"ERROR"}, "Select a component using the Edit button first")
            return {"CANCELLED"}

        plan_index, item = find_plan_item_by_object_and_group_index(scene, settings.matrix_editor_object, settings.matrix_manual_group_index)
        if item is None:
            self.report({"ERROR"}, f"VG index {settings.matrix_manual_group_index} was not found in {settings.matrix_editor_object}")
            return {"CANCELLED"}

        displaced, error, cl_info = assign_plan_item_to_canonical(scene, plan_index, row.canonical_name)
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        _rzm_preflight_after_edit(scene, stage="assign-matrix-manual")
        refresh_matrix_and_summary(scene)
        self.report({"INFO"}, f"Assigned manually{cl_info}" + ("; previous owner returned to Conflict" if displaced else ""))
        return {"FINISHED"}


class RZM_OT_clear_matrix_cell(Operator):
    bl_idname = "rzm_weights.clear_matrix_cell"
    bl_label = "Clear Matrix Cell"
    object_name: StringProperty()
    canonical_name: StringProperty()

    def execute(self, context):
        scene = context.scene
        for item in scene.rzm_weight_plan:
            if item.object_name == self.object_name and item.status == "APPROVED" and item.resolved_name == self.canonical_name:
                item.status = "CONFLICT"
                item.decision_reason = "manually cleared from matrix"
                item.conflict_cluster = self.canonical_name
                _rzm_preflight_after_edit(scene, stage="clear-matrix-cell")
                refresh_matrix_and_summary(scene)
                self.report({"INFO"}, "Cell cleared; previous VG sent to Conflict")
                return {"FINISHED"}
        return {"CANCELLED"}


class RZM_OT_assign_selected_to_matrix_row(Operator):
    bl_idname = "rzm_weights.assign_selected_to_matrix_row"
    bl_label = "ASSIGN TO SELECTED MATRIX ROW"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        row = selected_approved_row(scene)
        item, item_index = selected_issue_item(scene)
        if row is None:
            self.report({"ERROR"}, "Select a canonical row in Approved Matrix first")
            return {"CANCELLED"}
        if item is None or item.status not in {"CONFLICT", "UNKNOWN"}:
            self.report({"ERROR"}, "Choose Conflict or Unknown")
            return {"CANCELLED"}
        displaced, error, cl_info = assign_plan_item_to_canonical(scene, item_index, row.canonical_name)
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        _rzm_preflight_after_edit(scene, stage="assign-selected-to-row")
        refresh_matrix_and_summary(scene)
        self.report({"INFO"}, f"Assigned{cl_info}" + ("; old owner returned to Conflict" if displaced else ""))
        return {"FINISHED"}


class RZM_OT_approve_selected_conflict(Operator):
    bl_idname = "rzm_weights.approve_selected_conflict"
    bl_label = "APPROVE CURRENT NAME"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        item, item_index = selected_issue_item(scene)
        if item is None or item.status != "CONFLICT":
            return {"CANCELLED"}
        desired_name = item.resolved_name.strip()
        if not desired_name:
            return {"CANCELLED"}
        displace_existing_approved(scene, item_index, item.object_name, desired_name)
        item.status = "APPROVED"
        item.manual_override = True
        item.decision_reason = "manual approve"
        item.conflict_cluster = ""
        _rzm_preflight_after_edit(scene, stage="approve-conflict")
        refresh_matrix_and_summary(scene)
        return {"FINISHED"}


class RZM_OT_select_approved_cell(Operator):
    bl_idname = "rzm_weights.select_approved_cell"
    bl_label = "Select Approved Cell"
    plan_index: IntProperty()

    def execute(self, context):
        context.scene.rzm_weight_settings.approved_detail_index = self.plan_index
        tag_view3d_redraw()
        return {"FINISHED"}


class RZM_OT_demote_approved_detail(Operator):
    bl_idname = "rzm_weights.demote_approved_detail"
    bl_label = "Return to Conflict"

    def execute(self, context):
        scene = context.scene
        index = scene.rzm_weight_settings.approved_detail_index
        if not (0 <= index < len(scene.rzm_weight_plan)):
            return {"CANCELLED"}
        item = scene.rzm_weight_plan[index]
        if item.status != "APPROVED":
            return {"CANCELLED"}
        item.status = "CONFLICT"
        item.decision_reason = "manually demoted"
        _rzm_preflight_after_edit(scene, stage="demote-approved")
        refresh_matrix_and_summary(scene)
        return {"FINISHED"}


class RZM_OT_assign_candidate(Operator):
    bl_idname = "rzm_weights.assign_candidate"
    bl_label = "Assign Candidate"
    item_index: IntProperty()
    slot: IntProperty(min=1, max=3)

    def execute(self, context):
        scene = context.scene
        if not (0 <= self.item_index < len(scene.rzm_weight_plan)):
            return {"CANCELLED"}
        item = scene.rzm_weight_plan[self.item_index]
        value = getattr(item, f"candidate_{self.slot}")
        if value:
            cluster_info = ""
            if item.cluster_id:
                other_members = [other for other in scene.rzm_weight_plan if other.cluster_id == item.cluster_id and other != item]
                if other_members:
                    names = [f"{other.object_name} ({other.original_name})" for other in other_members]
                    cluster_info = " (Cluster: also changed " + ", ".join(names) + ")"
            is_helper = (value.startswith("hlp_") or 
                         value.startswith("Helper_") or 
                         any(other.is_helper for other in scene.rzm_weight_plan if other.resolved_name == value))
            item.status = "APPROVED"
            item.create_bone = is_helper
            item.is_helper = is_helper
            item.manual_override = True
            item.resolved_name = value
            _rzm_preflight_after_edit(scene, stage="assign-candidate")
            refresh_matrix_and_summary(scene)
            self.report({"INFO"}, f"Candidate assigned: {value}{cluster_info}")
        tag_view3d_redraw()
        return {"FINISHED"}


class RZM_OT_force_aux_name(Operator):
    bl_idname = "rzm_weights.force_aux_name"
    bl_label = "Separate Helper Bone"
    item_index: IntProperty()

    def execute(self, context):
        scene = context.scene
        if not (0 <= self.item_index < len(scene.rzm_weight_plan)):
            return {"CANCELLED"}
        item = scene.rzm_weight_plan[self.item_index]
        armature = scene.rzm_weight_settings.target_armature
        reserved = {bone.name for bone in armature.data.bones} if armature else set()
        reserved.update(row.resolved_name for row in scene.rzm_weight_plan if row.resolved_name)
        aux_name = generated_aux_name(item.nearest_bone, item.original_name, reserved)
        item.status = "APPROVED"
        item.create_bone = True
        item.is_helper = True
        item.manual_override = True
        item.resolved_name = aux_name
        _rzm_preflight_after_edit(scene, stage="force-aux-name")
        refresh_matrix_and_summary(scene)
        tag_view3d_redraw()
        return {"FINISHED"}


def serialize_backup(scene, armature_obj, generated_bones):
    objects = {}
    for item in scene.rzm_weight_plan:
        obj = bpy.data.objects.get(item.object_name)
        if obj is None or obj.type != "MESH":
            continue
        objects.setdefault(obj.name, {})[str(item.group_index)] = {
            "original_name": item.original_name,
            "resolved_name": item.resolved_name,
            "status": item.status,
        }
    payload = {"version": 1, "created_at": datetime.now().isoformat(timespec="seconds"), "armature": armature_obj.name, "generated_bones": sorted(generated_bones), "objects": objects}
    text = bpy.data.texts.get(BACKUP_TEXT) or bpy.data.texts.new(BACKUP_TEXT)
    text.clear()
    text.write(json.dumps(payload, ensure_ascii=False, indent=2))


def create_missing_bones(context, armature_obj, requests):
    if not requests:
        return []
    old_active = context.view_layer.objects.active
    old_selection = list(context.selected_objects)
    try:
        if old_active is not None and old_active.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        armature_obj.select_set(True)
        context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode="EDIT")
        generated = []
        inv = armature_obj.matrix_world.inverted()
        for name, request in requests.items():
            if name in armature_obj.data.edit_bones:
                continue
            parent = armature_obj.data.edit_bones.get(request["parent"])
            head = inv @ request["centroid"]
            direction = Vector((0.0, 0.0, 1.0))
            length = 0.025
            if parent is not None:
                direction = parent.tail - parent.head
                if direction.length <= 1e-6:
                    direction = Vector((0.0, 0.0, 1.0))
                else:
                    direction.normalize()
                length = max(parent.length * 0.25, 0.015)
            bone = armature_obj.data.edit_bones.new(name)
            bone.head = head
            bone.tail = head + direction * length
            bone.parent = parent
            generated.append(bone.name)
        bpy.ops.object.mode_set(mode="OBJECT")
        if generated:
            hidden_coll = armature_obj.data.collections.get("Hidden Helpers")
            if hidden_coll is None:
                hidden_coll = armature_obj.data.collections.new("Hidden Helpers")
                hidden_coll.is_visible = False
            for bname in generated:
                bone = armature_obj.data.bones.get(bname)
                if bone:
                    hidden_coll.assign(bone)
        return generated
    finally:
        if context.view_layer.objects.active is not None and context.view_layer.objects.active.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        for obj in old_selection:
            if obj.name in bpy.data.objects:
                obj.select_set(True)
        if old_active is not None and old_active.name in bpy.data.objects:
            context.view_layer.objects.active = old_active


class RZM_OT_apply_plan(Operator):
    bl_idname = "rzm_weights.apply_plan"
    bl_label = "APPLY HARMONIZATION"
    bl_options = {"REGISTER", "UNDO"}

    # ------------------------------------------------------------------
    # NAMING RULES (enforced here, nowhere else):
    #
    #   1. If original_name ends with .L / .R (or _L / _R), the final name
    #      MUST end with the SAME suffix.  This is absolute.
    #   2. All final names within one object must be unique.
    #   3. When a conflict arises, a readable counter is inserted BEFORE
    #      the suffix:
    #         Thigh.R  taken → Thigh_2.R  → Thigh_3.R  …
    #         Belly3.R taken → Belly3_2.R → Belly3_3.R …
    #         Torso    taken → Torso_2    → Torso_3    …
    #   4. .001 / .002 style Blender auto-suffixes are FORBIDDEN.
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_names(items, settings, _global_reserved=None):
        """Legacy entry point kept for external callers/tests.

        Final name resolution is now scene-level (_rzm_preflight_plan_names),
        because mirror pairs and duplicate conflicts need to be solved with
        the full object context.  This fallback only performs local cleanup and
        per-object dedup if someone calls the method directly.
        """
        used = set()
        for item in sorted(items, key=lambda r: r.group_index):
            candidate = _rzm_sanitize_name(item.resolved_name or item.original_name)
            if getattr(settings, "preserve_lr_suffixes", True):
                _side, _base, orig_suffix, _clean = _rzm_lr_parts(item.original_name)
                if orig_suffix:
                    candidate = _rzm_apply_suffix(candidate, orig_suffix)
            final_name, had_conflict = _rzm_conflict_name(candidate, used)
            used.add(final_name)
            item.resolved_name = final_name
            if had_conflict:
                item.create_bone = True
                item.is_helper = True
                item.decision_reason = "duplicate resolved before Blender rename"

    def execute(self, context):
        scene = context.scene
        settings = scene.rzm_weight_settings
        armature = settings.target_armature
        if armature is None or not scene.rzm_weight_plan:
            return {"CANCELLED"}

        bone_names = {bone.name for bone in armature.data.bones}

        # ── Phase 1: resolve all names BEFORE touching Blender API ────────────
        # Existing armature bone names are allowed as vertex-group names.
        # They are not collisions; they are the whole point of harmonization.
        # Only duplicate names inside the same mesh are disambiguated.
        _rzm_preflight_plan_names(scene, settings, stage="apply")

        grouped: dict[str, list] = defaultdict(list)
        for item in scene.rzm_weight_plan:
            if item.status != "IGNORED":
                grouped[item.object_name].append(item)

        # ── Phase 2: determine which bones need to be created ─────────────────
        creation_rows: dict[str, list] = defaultdict(list)
        for _object_name, items in grouped.items():
            for item in items:
                if item.resolved_name not in bone_names:
                    creation_rows[item.resolved_name].append(item)

        requests = {}
        for name, citems in creation_rows.items():
            centroid = sum((Vector(i.centroid) for i in citems), Vector()) / max(len(citems), 1)
            parents = Counter(i.nearest_bone for i in citems if i.nearest_bone)
            requests[name] = {"centroid": centroid, "parent": parents.most_common(1)[0][0] if parents else ""}

        generated = []
        if settings.create_missing_bones and settings.match_mode != 'FBX':
            generated = create_missing_bones(context, armature, requests)
        serialize_backup(scene, armature, generated)

        # ── Phase 3: rename vertex groups ─────────────────────────────────────
        for object_name, items in grouped.items():
            obj = bpy.data.objects.get(object_name)
            if obj is None or obj.type != "MESH":
                continue

            planned_indices = {item.group_index for item in items}
            all_original = {vg.index: vg.name for vg in obj.vertex_groups}

            # Temp-rename EVERY VG (planned + ignored) so no name is "live"
            # when we start assigning final names → Blender cannot add .001.
            for vg in obj.vertex_groups:
                vg.name = f"__RZM_TMP__{vg.index:04d}__"

            # Assign final names exactly as preflight decided.  Do NOT run a
            # last-minute row-by-row dedup here: that is precisely how a mirror
            # pair can be broken into Clavicle.R / Clavicle_2.R.  If preflight
            # somehow failed, cancel loudly instead of letting Blender invent
            # .001 tails or silently flipping sides.
            valid_items = [item for item in sorted(items, key=lambda r: r.group_index) if item.group_index < len(obj.vertex_groups)]
            planned_final_names = [item.resolved_name for item in valid_items]

            duplicate_groups = _rzm_duplicate_name_groups(valid_items, _rzm_plan_index_lookup(scene.rzm_weight_plan))
            if duplicate_groups:
                payload = _rzm_write_name_error(
                    scene,
                    stage="apply-final-validation",
                    object_name=object_name,
                    reason="duplicate planned VG names",
                    items=valid_items,
                    extra={
                        "object_vertex_group_count": len(obj.vertex_groups),
                        "note": "These are the exact plan rows that still share one resolved_name right before Blender rename.",
                    },
                )
                self.report({"ERROR"}, f"Name preflight failed for {object_name}: {_rzm_error_short_message(payload)}. Details: scene['rzm_harmonizer_name_error'] / console")
                return {"CANCELLED"}

            suffix_rows = _rzm_blender_suffix_groups(valid_items, _rzm_plan_index_lookup(scene.rzm_weight_plan))
            if suffix_rows:
                payload = _rzm_write_name_error(
                    scene,
                    stage="apply-final-validation",
                    object_name=object_name,
                    reason="Blender .001 suffix survived",
                    items=valid_items,
                    extra={"offending_rows": suffix_rows},
                )
                self.report({"ERROR"}, f"Name preflight failed for {object_name}: {_rzm_error_short_message(payload)}. Details: scene['rzm_harmonizer_name_error'] / console")
                return {"CANCELLED"}

            used_names = set()
            mapping = []
            for item in sorted(items, key=lambda r: r.group_index):
                if item.group_index >= len(obj.vertex_groups):
                    continue
                final_name = item.resolved_name
                used_names.add(final_name)
                obj.vertex_groups[item.group_index].name = final_name
                mapping.append({"original_index": item.group_index, "original_name": item.original_name, "resolved_name": final_name, "status": item.status})

            # Restore unplanned / IGNORED VGs (mask groups etc.) without allowing
            # them to collide with planned names and trigger Blender .001 tails.
            for vg in obj.vertex_groups:
                if vg.index not in planned_indices:
                    wanted = all_original.get(vg.index, vg.name)
                    final_name, _had_conflict = _rzm_conflict_name(wanted, used_names)
                    used_names.add(final_name)
                    vg.name = final_name

            obj["rzm_weight_harmonizer_mapping"] = json.dumps(mapping, ensure_ascii=False)

        refresh_matrix_and_summary(scene)
        self.report({"INFO"}, f"Done. New bones: {len(generated)}. VG order and vertex order were not changed")
        return {"FINISHED"}


class RZM_OT_restore_backup(Operator):
    bl_idname = "rzm_weights.restore_backup"
    bl_label = "RESTORE ORIGINAL NAMES"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        text = bpy.data.texts.get(BACKUP_TEXT)
        if text is None:
            self.report({"WARNING"}, "Backup not found")
            return {"CANCELLED"}
        backup = json.loads(text.as_string())
        for object_name, rows in backup.get("objects", {}).items():
            obj = bpy.data.objects.get(object_name)
            if obj is None or obj.type != "MESH":
                continue
            ordered = sorted(rows.items(), key=lambda pair: int(pair[0]))
            for index_text, _row in ordered:
                index = int(index_text)
                if index < len(obj.vertex_groups):
                    obj.vertex_groups[index].name = f"__RZM_RESTORE_TMP__{index:04d}__"
            for index_text, row in ordered:
                index = int(index_text)
                if index < len(obj.vertex_groups):
                    obj.vertex_groups[index].name = row["original_name"]
            if "rzm_weight_harmonizer_mapping" in obj:
                del obj["rzm_weight_harmonizer_mapping"]

        armature = bpy.data.objects.get(backup.get("armature", ""))
        generated_bones = backup.get("generated_bones", [])
        if armature is not None and armature.type == "ARMATURE" and generated_bones:
            old_active = context.view_layer.objects.active
            old_selection = list(context.selected_objects)
            try:
                if old_active is not None and old_active.mode != "OBJECT":
                    bpy.ops.object.mode_set(mode="OBJECT")
                bpy.ops.object.select_all(action="DESELECT")
                armature.select_set(True)
                context.view_layer.objects.active = armature
                bpy.ops.object.mode_set(mode="EDIT")
                for bone_name in generated_bones:
                    edit_bone = armature.data.edit_bones.get(bone_name)
                    if edit_bone is not None:
                        armature.data.edit_bones.remove(edit_bone)
                bpy.ops.object.mode_set(mode="OBJECT")
            finally:
                if context.view_layer.objects.active is not None and context.view_layer.objects.active.mode != "OBJECT":
                    bpy.ops.object.mode_set(mode="OBJECT")
                bpy.ops.object.select_all(action="DESELECT")
                for obj in old_selection:
                    if obj.name in bpy.data.objects:
                        obj.select_set(True)
                if old_active is not None and old_active.name in bpy.data.objects:
                    context.view_layer.objects.active = old_active

        try: context.view_layer.update()
        except: pass

        self.report({"INFO"}, "Original VG names restored, generated bones removed")
        return {"FINISHED"}


class RZM_OT_clear_plan(Operator):
    bl_idname = "rzm_weights.clear_plan"
    bl_label = "Clear Plan"

    def execute(self, context):
        context.scene.rzm_weight_plan.clear()
        context.scene.rzm_approved_matrix.clear()
        context.scene.rzm_component_summary.clear()
        invalidate_matrix_suggestion_cache()
        tag_view3d_redraw()
        return {"FINISHED"}


class RZM_OT_refresh_overlay(Operator):
    bl_idname = "rzm_weights.refresh_overlay"
    bl_label = "Refresh Overlay"

    def execute(self, context):
        tag_view3d_redraw()
        return {"FINISHED"}


def distance_to_segment(point: Vector, start: Vector, end: Vector) -> float:
    line_vec = end - start
    point_vec = point - start
    line_len_sq = line_vec.length_squared
    if line_len_sq == 0.0:
        return point_vec.length
    t = max(0.0, min(1.0, point_vec.dot(line_vec) / line_len_sq))
    projection = start + t * line_vec
    return (point - projection).length


class RZM_OT_cluster_disband(Operator):
    bl_idname = "rzm_weights.cluster_disband"
    bl_label = "Disband Cluster"
    bl_description = "Disband all weight groups in this cluster"
    cluster_id: StringProperty()

    def execute(self, context):
        if not self.cluster_id:
            return {'CANCELLED'}
        for item in context.scene.rzm_weight_plan:
            if item.cluster_id == self.cluster_id:
                item.cluster_id = ""
        tag_view3d_redraw()
        self.report({"INFO"}, "Cluster disbanded")
        return {'FINISHED'}


class RZM_OT_cluster_split_item(Operator):
    bl_idname = "rzm_weights.cluster_split_item"
    bl_label = "Remove from Cluster"
    bl_description = "Remove the selected group from the cluster"
    plan_index: IntProperty()

    def execute(self, context):
        plan = context.scene.rzm_weight_plan
        if 0 <= self.plan_index < len(plan):
            item = plan[self.plan_index]
            item.cluster_id = ""
            tag_view3d_redraw()
            self.report({"INFO"}, f"Group {item.original_name} removed from the cluster")
            return {'FINISHED'}
        return {'CANCELLED'}


class RZM_OT_cluster_merge_groups(Operator):
    bl_idname = "rzm_weights.cluster_merge_groups"
    bl_label = "Merge Groups into Cluster"
    bl_description = "Merge two groups into one cluster for synchronized editing"
    source_index: IntProperty()
    target_index: IntProperty()

    def execute(self, context):
        scene = context.scene
        plan = scene.rzm_weight_plan
        if not (0 <= self.source_index < len(plan) and 0 <= self.target_index < len(plan)):
            return {'CANCELLED'}

        src = plan[self.source_index]
        tgt = plan[self.target_index]

        cid = src.cluster_id or tgt.cluster_id
        if not cid:
            existing_ids = {item.cluster_id for item in plan if item.cluster_id}
            i = 0
            while f"cluster_manual_{i}" in existing_ids:
                i += 1
            cid = f"cluster_manual_{i}"

        src.cluster_id = cid
        tgt.cluster_id = cid

        best_resolved_name = tgt.resolved_name or src.resolved_name
        best_status = tgt.status if tgt.resolved_name else src.status
        best_create_bone = tgt.create_bone if tgt.resolved_name else src.create_bone

        src["_updating_cluster"] = True
        tgt["_updating_cluster"] = True
        src.resolved_name = best_resolved_name
        src.status = best_status
        src.create_bone = best_create_bone
        tgt.resolved_name = best_resolved_name
        tgt.status = best_status
        tgt.create_bone = best_create_bone
        src["_updating_cluster"] = False
        tgt["_updating_cluster"] = False

        for other in plan:
            if other.cluster_id == cid:
                other["_updating_cluster"] = True
                other.resolved_name = best_resolved_name
                other.status = best_status
                other.create_bone = best_create_bone
                other["_updating_cluster"] = False

        _rzm_preflight_after_edit(scene, stage="cluster-merge")

        try:
            target_names = {item.object_name for item in plan}
            target_meshes = [bpy.data.objects.get(name) for name in target_names if bpy.data.objects.get(name)]
            rebuild_matrix_and_summary(scene, target_meshes)
        except Exception as e:
            print("Error rebuilding matrix:", e)

        tag_view3d_redraw()
        self.report({"INFO"}, f"Groups merged into cluster '{cid}'")
        return {'FINISHED'}


class RZM_OT_switch_active_vg(Operator):
    bl_idname = "rzm_weights.switch_active_vg"
    bl_label = "Switch Active Vertex Group"
    bl_description = "Switch the active vertex group on the object"
    group_index: IntProperty()

    def execute(self, context):
        active_obj = context.active_object
        if not active_obj or active_obj.type != 'MESH':
            return {'CANCELLED'}
        if 0 <= self.group_index < len(active_obj.vertex_groups):
            active_obj.vertex_groups.active_index = self.group_index
            for idx, item in enumerate(context.scene.rzm_weight_plan):
                if item.object_name == active_obj.name and item.group_index == self.group_index:
                    context.scene.rzm_weight_settings.object_plan_index = idx
                    break
            tag_view3d_redraw()
            return {'FINISHED'}
        return {'CANCELLED'}


class RZM_OT_quick_attach_bone(Operator):
    bl_idname = "rzm_weights.quick_attach_bone"
    bl_label = "Quick Attach Bone"
    bl_description = "Attach the vertex group to the selected bone"
    bone_name: StringProperty()
    object_name: StringProperty()
    group_index: IntProperty()
    is_helper: BoolProperty(default=False)

    def execute(self, context):
        scene = context.scene
        plan = scene.rzm_weight_plan

        found_item = None
        for item in plan:
            if item.object_name == self.object_name and item.group_index == self.group_index:
                found_item = item
                break

        if not found_item:
            self.report({"ERROR"}, "Plan item not found")
            return {'CANCELLED'}

        cluster_info = ""
        if found_item.cluster_id:
            other_members = [other for other in plan if other.cluster_id == found_item.cluster_id and other != found_item]
            if other_members:
                names = [f"{other.object_name} ({other.original_name})" for other in other_members]
                cluster_info = " (Cluster: also changed " + ", ".join(names) + ")"

        is_helper = (self.is_helper or
                     self.bone_name.startswith("hlp_") or 
                     self.bone_name.startswith("Helper_") or 
                     any(other.is_helper for other in plan if other.resolved_name == self.bone_name))
        found_item.status = "APPROVED"
        found_item.create_bone = is_helper
        found_item.is_helper = is_helper
        found_item.manual_override = True
        found_item.resolved_name = self.bone_name

        _rzm_preflight_after_edit(scene, stage="quick-attach-bone")

        try:
            target_names = {item.object_name for item in plan}
            target_meshes = [bpy.data.objects.get(name) for name in target_names if bpy.data.objects.get(name)]
            rebuild_matrix_and_summary(scene, target_meshes)
        except Exception as e:
            print("Error rebuilding matrix:", e)

        tag_view3d_redraw()
        self.report({"INFO"}, f"Group attached to bone '{self.bone_name}'{cluster_info}")
        return {'FINISHED'}


class RZM_MT_quick_attach(bpy.types.Menu):
    bl_label = "Quick Attach (Nearest Bones)"
    bl_idname = "RZM_MT_quick_attach"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.rzm_weight_settings
        armature_obj = settings.target_armature
        if not armature_obj:
            layout.label(text="Error: Target Armature is not set in Settings", icon='ERROR')
            return

        active_obj = context.active_object
        if not active_obj or active_obj.type != 'MESH':
            layout.label(text="Error: Active object must be a Mesh", icon='ERROR')
            return

        active_vg = active_obj.vertex_groups.active
        if not active_vg:
            layout.label(text="Error: No active vertex group", icon='ERROR')
            return

        plan_item = None
        for item in scene.rzm_weight_plan:
            if item.object_name == active_obj.name and item.group_index == active_vg.index:
                plan_item = item
                break

        if not plan_item:
            layout.label(text=f"Group '{active_vg.name}' not found in Plan. Build Plan first.", icon='NONE')
            return

        # 1. Create Helper Option
        new_hlp_name = f"hlp_{active_vg.name}"
        op_new = layout.operator("rzm_weights.quick_attach_bone", text=f"Create Helper: {new_hlp_name}", icon='ADD')
        op_new.bone_name = new_hlp_name
        op_new.object_name = active_obj.name
        op_new.group_index = active_vg.index
        op_new.is_helper = True

        # 2. Existing Helpers
        from .ui_harmonizer import get_existing_helpers
        helpers = get_existing_helpers(scene, armature_obj)
        # Don't list the potential new one in the existing list
        filtered_helpers = [h for h in helpers if h != new_hlp_name]
        if filtered_helpers:
            layout.separator()
            layout.label(text="Existing Helpers:")
            for hlp_name in filtered_helpers:
                op_h = layout.operator("rzm_weights.quick_attach_bone", text=hlp_name, icon='LINKED')
                op_h.bone_name = hlp_name
                op_h.object_name = active_obj.name
                op_h.group_index = active_vg.index
                op_h.is_helper = True

        layout.separator()
        centroid = Vector(plan_item.centroid)
        layout.label(text=f"Closest Armature Bones (Centroid: {centroid.x:.2f}, {centroid.y:.2f}, {centroid.z:.2f}):")

        bone_distances = []
        for bone in armature_obj.data.bones:
            head_w = armature_obj.matrix_world @ bone.head_local
            tail_w = armature_obj.matrix_world @ bone.tail_local
            dist = distance_to_segment(centroid, head_w, tail_w)
            bone_distances.append((bone.name, dist))

        bone_distances.sort(key=lambda x: x[1])
        top_10 = bone_distances[:10]

        for bone_name, dist in top_10:
            label = f"{bone_name} ({dist:.3f} m)"
            op = layout.operator("rzm_weights.quick_attach_bone", text=label, icon='BONE_DATA')
            op.bone_name = bone_name
            op.object_name = active_obj.name
            op.group_index = active_vg.index


class RZM_MT_cluster_merge_candidates(bpy.types.Menu):
    bl_label = "Merge into Cluster"
    bl_idname = "RZM_MT_cluster_merge_candidates"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        active_obj = context.active_object
        if not active_obj or active_obj.type != 'MESH':
            return
        active_vg = active_obj.vertex_groups.active
        if not active_vg:
            return

        source_idx = -1
        for idx, item in enumerate(scene.rzm_weight_plan):
            if item.object_name == active_obj.name and item.group_index == active_vg.index:
                source_idx = idx
                break

        if source_idx == -1:
            layout.label(text="Active group not found in Plan")
            return

        layout.label(text="Choose a group to merge:")
        layout.separator()

        source_item = scene.rzm_weight_plan[source_idx]
        source_center = Vector(source_item.centroid)

        candidates = []
        for idx, item in enumerate(scene.rzm_weight_plan):
            if item.object_name != active_obj.name and item.status != "IGNORED":
                dist = (source_center - Vector(item.centroid)).length
                candidates.append((idx, item, dist))

        # Sort by distance ascending
        candidates.sort(key=lambda x: x[2])

        if not candidates:
            layout.label(text="No available groups on other objects")
            return

        for idx, item, dist in candidates:
            label = f"{item.object_name} | {item.original_name} (→ {item.resolved_name or '—'}) - {dist:.3f} m"
            op = layout.operator("rzm_weights.cluster_merge_groups", text=label)
            op.source_index = source_idx
            op.target_index = idx


class RZM_OT_vg_name_transfer(Operator):
    bl_idname = "rzm_weights.vg_name_transfer"
    bl_label = "VG Name Transfer"
    bl_description = "Transfer vertex group names from the donor object to the active one by index"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def _rebuild_vertex_groups_in_order(self, obj, target_order):
        current_names = [vg.name for vg in obj.vertex_groups]
        if current_names == target_order:
            return

        active_name = obj.vertex_groups.active.name if obj.vertex_groups.active else None
        vg_locks = {vg.name: vg.lock_weight for vg in obj.vertex_groups}
        vert_weights = {}

        for vert in obj.data.vertices:
            v_weights = []
            for item in vert.groups:
                if item.group < len(current_names):
                    group_name = current_names[item.group]
                    v_weights.append((group_name, item.weight))
            if v_weights:
                vert_weights[vert.index] = v_weights

        obj.vertex_groups.clear()

        for name in target_order:
            vg = obj.vertex_groups.new(name=name)
            vg.lock_weight = vg_locks.get(name, False)

        name_to_vg = {vg.name: vg for vg in obj.vertex_groups}
        for vert_index, weights in vert_weights.items():
            for name, weight in weights:
                vg = name_to_vg.get(name)
                if vg is not None:
                    vg.add([vert_index], weight, 'REPLACE')

        if active_name and active_name in name_to_vg:
            obj.vertex_groups.active = name_to_vg[active_name]

    def _prepare_vertex_groups(self, obj):
        names = [vg.name for vg in obj.vertex_groups]
        non_masks = [name for name in names if not is_mask_group(name)]
        masks = [name for name in names if is_mask_group(name)]
        target_order = non_masks + masks
        if names != target_order:
            self._rebuild_vertex_groups_in_order(obj, target_order)
        return non_masks, masks

    def execute(self, context):
        active_obj = context.active_object
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if len(selected_meshes) != 2:
            self.report({'ERROR'}, "Select exactly 2 mesh objects (the active one is the Target, the other is the Donor)")
            return {'CANCELLED'}

        donor_obj = selected_meshes[0] if selected_meshes[1] == active_obj else selected_meshes[1]

        target_non_masks, _ = self._prepare_vertex_groups(active_obj)
        donor_non_masks, _ = self._prepare_vertex_groups(donor_obj)

        target_vgs = active_obj.vertex_groups
        donor_vgs = donor_obj.vertex_groups

        if len(target_non_masks) != len(donor_non_masks):
            self.report(
                {'ERROR'},
                f"Group count mismatch (ignoring masks): Target={len(target_non_masks)}, Donor={len(donor_non_masks)}"
            )
            return {'CANCELLED'}

        # Perform transfer
        renamed_count = 0
        for i in range(len(target_non_masks)):
            old_name = target_vgs[i].name
            new_name = donor_vgs[i].name
            if old_name != new_name:
                target_vgs[i].name = new_name
                renamed_count += 1

        try:
            from .harmonizer_utils import invalidate_overlay_cache
            invalidate_matrix_suggestion_cache()
            invalidate_overlay_cache()
        except Exception:
            pass

        self.report({'INFO'}, f"Successfully transferred {renamed_count} group names from {donor_obj.name} to {active_obj.name}")
        return {'FINISHED'}


classes_to_register = [
    RZM_OT_build_plan,
    RZM_OT_open_matrix_cell_editor,
    RZM_OT_assign_matrix_suggestion,
    RZM_OT_assign_matrix_manual_index,
    RZM_OT_clear_matrix_cell,
    RZM_OT_assign_selected_to_matrix_row,
    RZM_OT_approve_selected_conflict,
    RZM_OT_select_approved_cell,
    RZM_OT_demote_approved_detail,
    RZM_OT_assign_candidate,
    RZM_OT_force_aux_name,
    RZM_OT_apply_plan,
    RZM_OT_restore_backup,
    RZM_OT_clear_plan,
    RZM_OT_refresh_overlay,
    RZM_OT_cluster_disband,
    RZM_OT_cluster_split_item,
    RZM_OT_cluster_merge_groups,
    RZM_OT_switch_active_vg,
    RZM_OT_quick_attach_bone,
    RZM_OT_vg_name_transfer,
    RZM_MT_quick_attach,
    RZM_MT_cluster_merge_candidates,
]
