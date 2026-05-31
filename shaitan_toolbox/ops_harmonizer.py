import bpy
import json
from collections import defaultdict, Counter
from datetime import datetime
from mathutils import Vector
from bpy.types import Operator
from bpy.props import StringProperty, IntProperty

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
    bl_label = "Построить Remap Plan"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        settings = scene.rzm_weight_settings
        armature_obj = settings.target_armature
        reference_obj = settings.reference_mesh
        if armature_obj is None or armature_obj.type != "ARMATURE":
            self.report({"ERROR"}, "Укажи таргетную арматуру")
            return {"CANCELLED"}
        if reference_obj is None or reference_obj.type != "MESH":
            self.report({"ERROR"}, "Укажи канонический reference mesh")
            return {"CANCELLED"}
        target_meshes = [obj for obj in context.selected_objects if obj.type == "MESH" and obj != reference_obj]
        if not target_meshes:
            self.report({"ERROR"}, "Выдели целевые компоненты")
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

        for target_obj in sorted(target_meshes, key=lambda obj: obj.name.casefold()):
            try:
                target_fps = collect_group_fingerprints(target_obj, depsgraph, bone_segments, character_scale)
            except RuntimeError as error:
                self.report({"ERROR"}, str(error))
                return {"CANCELLED"}

            claimed = set()
            prepared = []
            for fp in target_fps:
                if is_mask_group(fp["name"]):
                    add_plan_item(scene, target_obj, fp, "IGNORED", fp["name"], 1.0, 1.0, [], reason="Mask* ignored")
                    continue
                from .harmonizer_utils import top_candidates
                prepared.append((fp, top_candidates(fp, reference_fps, character_scale, settings, limit=5)))

            prepared.sort(key=lambda row: row[1][0][1] if row[1] else 0.0, reverse=True)
            assignment_conflicts = build_assignment_conflicts(prepared, settings.conflict_threshold, settings.assignment_margin)

            for fp, candidates in prepared:
                from .harmonizer_utils import fingerprint_similarity
                available = [row for row in candidates if row[0]["name"] not in claimed]
                best = available[0] if available else (candidates[0] if candidates else None)
                second = available[1] if len(available) > 1 else None
                best_score = best[1] if best else 0.0
                second_score = second[1] if second else 0.0
                margin = best_score - second_score

                if best and best_score >= settings.conflict_threshold:
                    resolved_name = best[0]["name"]
                    claimed.add(resolved_name)
                    cluster = sorted(assignment_conflicts.get(fp["index"], set()))
                    has_local_rival = second is not None and second_score >= settings.conflict_threshold and margin < settings.unique_margin
                    has_assignment_rival = bool(cluster)
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
                    add_plan_item(scene, target_obj, fp, status, resolved_name, best_score, margin, candidates, resolved_name not in armature_names, reason, ", ".join(cluster))
                    continue

                clustered_name = None
                for registry in unknown_registry:
                    if registry["object_name"] == target_obj.name:
                        continue
                    if fingerprint_similarity(fp, registry["fingerprint"], character_scale) >= settings.unknown_cluster_threshold:
                        clustered_name = registry["resolved_name"]
                        break
                if clustered_name is None:
                    clustered_name = generated_aux_name(fp["nearest_bone"], fp["name"], generated_reserved)
                    unknown_registry.append({"object_name": target_obj.name, "fingerprint": fp, "resolved_name": clustered_name})
                add_plan_item(scene, target_obj, fp, "UNKNOWN", clustered_name, best_score, margin, candidates, True, "no candidate above Floor")

        rebuild_matrix_and_summary(scene, target_meshes)
        self.report({"INFO"}, "Remap Plan построен")
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
        displaced, error = assign_plan_item_to_canonical(context.scene, self.plan_index, self.canonical_name)
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        self.report({"INFO"}, "Назначено" + ("; прежний владелец возвращён in Conflict" if displaced else ""))
        return {"FINISHED"}


class RZM_OT_assign_matrix_manual_index(Operator):
    bl_idname = "rzm_weights.assign_matrix_manual_index"
    bl_label = "Attach VG index"

    def execute(self, context):
        scene = context.scene
        settings = scene.rzm_weight_settings
        row = selected_approved_row(scene)
        if row is None:
            self.report({"ERROR"}, "Сначала выбери строку Approved Matrix")
            return {"CANCELLED"}
        if not settings.matrix_editor_object:
            self.report({"ERROR"}, "Сначала выбери компонент кнопкой Edit")
            return {"CANCELLED"}

        plan_index, item = find_plan_item_by_object_and_group_index(scene, settings.matrix_editor_object, settings.matrix_manual_group_index)
        if item is None:
            self.report({"ERROR"}, f"VG index {settings.matrix_manual_group_index} не найден в {settings.matrix_editor_object}")
            return {"CANCELLED"}

        displaced, error = assign_plan_item_to_canonical(scene, plan_index, row.canonical_name)
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        self.report({"INFO"}, "Назначено вручную" + ("; прежний владелец возвращён in Conflict" if displaced else ""))
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
                self.report({"INFO"}, "Ячейка очищена; прежний VG отправлен в Conflict")
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
            self.report({"ERROR"}, "Сначала выбери каноническую строку в Approved Matrix")
            return {"CANCELLED"}
        if item is None or item.status not in {"CONFLICT", "UNKNOWN"}:
            self.report({"ERROR"}, "Выбери Conflict или Unknown")
            return {"CANCELLED"}
        displaced, error = assign_plan_item_to_canonical(scene, item_index, row.canonical_name)
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        self.report({"INFO"}, "Назначено" + ("; старый владелец возвращён в Conflict" if displaced else ""))
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
    bl_label = "Вернуть в Conflict"

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
    bl_label = "Назначить кандидата"
    item_index: IntProperty()
    slot: IntProperty(min=1, max=3)

    def execute(self, context):
        scene = context.scene
        if not (0 <= self.item_index < len(scene.rzm_weight_plan)):
            return {"CANCELLED"}
        item = scene.rzm_weight_plan[self.item_index]
        value = getattr(item, f"candidate_{self.slot}")
        if value:
            item.resolved_name = value
            item.manual_override = True
        tag_view3d_redraw()
        return {"FINISHED"}


class RZM_OT_force_aux_name(Operator):
    bl_idname = "rzm_weights.force_aux_name"
    bl_label = "Отдельная доп. кость"
    item_index: IntProperty()

    def execute(self, context):
        scene = context.scene
        if not (0 <= self.item_index < len(scene.rzm_weight_plan)):
            return {"CANCELLED"}
        item = scene.rzm_weight_plan[self.item_index]
        armature = scene.rzm_weight_settings.target_armature
        reserved = {bone.name for bone in armature.data.bones} if armature else set()
        reserved.update(row.resolved_name for row in scene.rzm_weight_plan if row.resolved_name)
        item.resolved_name = generated_aux_name(item.nearest_bone, item.original_name, reserved)
        item.create_bone = True
        item.manual_override = True
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
                    item.decision_reason = "duplicate prevented during Apply"
                local_reserved.add(requested)
                if requested not in bone_names and settings.create_missing_bones:
                    creation_rows[requested].append(item)

        requests = {}
        for name, items in creation_rows.items():
            centroid = sum((Vector(item.centroid) for item in items), Vector((0.0, 0.0, 0.0))) / max(len(items), 1)
            parents = Counter(item.nearest_bone for item in items if item.nearest_bone)
            requests[name] = {"centroid": centroid, "parent": parents.most_common(1)[0][0] if parents else ""}

        generated = create_missing_bones(context, armature, requests) if settings.create_missing_bones else []
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
        self.report({"INFO"}, f"Готово. Новых костей: {len(generated)}. VG order и vertex order не менялись")
        return {"FINISHED"}


class RZM_OT_restore_backup(Operator):
    bl_idname = "rzm_weights.restore_backup"
    bl_label = "RESTORE ORIGINAL NAMES"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        text = bpy.data.texts.get(BACKUP_TEXT)
        if text is None:
            self.report({"WARNING"}, "Бэкап не найден")
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

        self.report({"INFO"}, "Исходные имена VG восстановлены, созданные кости удалены")
        return {"FINISHED"}


class RZM_OT_clear_plan(Operator):
    bl_idname = "rzm_weights.clear_plan"
    bl_label = "Очистить Plan"

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
]
