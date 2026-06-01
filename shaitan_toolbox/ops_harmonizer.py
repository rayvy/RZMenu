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
)


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

            if best and best_score >= settings.conflict_threshold:
                resolved_name = best[0]["name"]
                claimed.add(resolved_name)
                cluster_key = (fp["object_name"], fp["index"])
                conflict_names = sorted(assignment_conflicts.get(cluster_key, set()))
                has_local_rival = second is not None and second_score >= settings.conflict_threshold and margin < settings.unique_margin
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

                # Вычисляем оригинальный скор без консенсуса для вывода инфо
                individual_candidates = top_candidates(fp, reference_fps, character_scale, settings, limit=1)
                orig_score = individual_candidates[0][1] if individual_candidates else 0.0
                if orig_score < settings.conflict_threshold and best_score >= settings.conflict_threshold:
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
                    resolved_name not in armature_names,
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
        displaced, error, cl_info = assign_plan_item_to_canonical(context.scene, self.plan_index, self.canonical_name)
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
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

    def execute(self, context):
        scene = context.scene
        settings = scene.rzm_weight_settings
        armature = settings.target_armature
        if armature is None or not scene.rzm_weight_plan:
            return {"CANCELLED"}

        bone_names = {bone.name for bone in armature.data.bones}
        reserved = set(bone_names)
        reserved.update(item.resolved_name for item in scene.rzm_weight_plan if item.resolved_name)
        grouped = defaultdict(list)
        for item in scene.rzm_weight_plan:
            if item.status != "IGNORED":
                grouped[item.object_name].append(item)

        creation_rows = defaultdict(list)
        for _object_name, items in grouped.items():
            local_reserved = set()
            for item in sorted(items, key=lambda row: row.group_index):
                requested = item.resolved_name.strip()
                if not requested or requested in local_reserved:
                    requested = generated_aux_name(item.nearest_bone, item.original_name, reserved)
                    item.resolved_name = requested
                    item.create_bone = True
                    item.is_helper = True
                    item.decision_reason = "duplicate prevented during Apply"
                local_reserved.add(requested)
                if requested not in bone_names:
                    creation_rows[requested].append(item)

        requests = {}
        for name, items in creation_rows.items():
            centroid = sum((Vector(item.centroid) for item in items), Vector((0.0, 0.0, 0.0))) / max(len(items), 1)
            parents = Counter(item.nearest_bone for item in items if item.nearest_bone)
            requests[name] = {"centroid": centroid, "parent": parents.most_common(1)[0][0] if parents else ""}

        generated = create_missing_bones(context, armature, requests)
        serialize_backup(scene, armature, generated)

        for object_name, items in grouped.items():
            obj = bpy.data.objects.get(object_name)
            if obj is None or obj.type != "MESH":
                continue
            for item in items:
                if item.group_index < len(obj.vertex_groups):
                    obj.vertex_groups[item.group_index].name = f"__RZM_TMP__{item.group_index:04d}__"
            mapping = []
            for item in items:
                if item.group_index >= len(obj.vertex_groups):
                    continue
                obj.vertex_groups[item.group_index].name = item.resolved_name
                mapping.append({"original_index": item.group_index, "original_name": item.original_name, "resolved_name": item.resolved_name, "status": item.status})
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
            layout.label(text=f"Group '{active_vg.name}' not found in Plan. Build Plan first.", icon='WARNING')
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

    def execute(self, context):
        active_obj = context.active_object
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if len(selected_meshes) != 2:
            self.report({'ERROR'}, "Select exactly 2 mesh objects (the active one is the Target, the other is the Donor)")
            return {'CANCELLED'}

        donor_obj = selected_meshes[0] if selected_meshes[1] == active_obj else selected_meshes[1]

        target_vgs = active_obj.vertex_groups
        donor_vgs = donor_obj.vertex_groups

        if len(target_vgs) != len(donor_vgs):
            self.report({'ERROR'}, f"Group count mismatch: Target={len(target_vgs)}, Donor={len(donor_vgs)}")
            return {'CANCELLED'}

        # Perform transfer
        renamed_count = 0
        for i in range(len(target_vgs)):
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
