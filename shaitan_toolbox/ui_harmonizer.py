import bpy
from bpy.types import UIList

from .harmonizer_utils import (
    status_counts,
    selected_approved_row,
    selected_issue_item,
    matrix_cell_suggestions,
    tag_view3d_redraw,
)


class RZM_UL_approved_matrix(UIList):
    def filter_items(self, context, data, propname):
        rows = getattr(data, propname)
        if not context.scene.rzm_weight_settings.matrix_only_incomplete:
            return [], []
        return [self.bitflag_filter_item if any(cell.plan_index < 0 for cell in row.cells) else 0 for row in rows], []

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.canonical_name, icon="BONE_DATA")
        for cell in item.cells:
            if cell.plan_index >= 0:
                op = row.operator("rzm_weights.select_approved_cell", text=cell.display_text, emboss=True)
                op.plan_index = cell.plan_index
            else:
                row.label(text="—")


class RZM_UL_weight_plan(UIList):
    filter_status = ""

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        return [self.bitflag_filter_item if item.status == self.filter_status else 0 for item in items], []

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=f"{item.object_name}[{item.group_index:03d}] {item.original_name}")
        row.label(text="→")
        row.prop(item, "resolved_name", text="")
        row.label(text=f"{item.confidence * 100:3.0f}%")


class RZM_UL_conflict(RZM_UL_weight_plan):
    filter_status = "CONFLICT"


class RZM_UL_unknown(RZM_UL_weight_plan):
    filter_status = "UNKNOWN"


class RZM_UL_ignored(RZM_UL_weight_plan):
    filter_status = "IGNORED"


def draw_component_summary(layout, scene):
    box = layout.box()
    box.label(text="Заполненность компонентов", icon="INFO")
    for item in scene.rzm_component_summary:
        row = box.row(align=True)
        row.label(text=item.object_name)
        row.label(text=f"Arm {item.occupied_default}/{item.default_total}")
        row.label(text=f"holes {item.missing_default}")
        row.label(text=f"A {item.approved}")
        row.label(text=f"C {item.conflict}")
        row.label(text=f"U {item.unknown}")
        if item.duplicate_approved:
            row.label(text=f"⚠ dup {item.duplicate_approved}")


def draw_matrix_target(layout, scene):
    matrix_row = selected_approved_row(scene)
    if matrix_row is None:
        layout.label(text="Matrix target: <не выбран>")
        return

    settings = scene.rzm_weight_settings
    box = layout.box()
    box.label(text=f"Matrix target: {matrix_row.canonical_name}", icon="BONE_DATA")

    for cell in matrix_row.cells:
        row = box.row(align=True)
        state = cell.display_text if cell.plan_index >= 0 else "EMPTY"
        row.label(text=f"{cell.object_name}: {state}")
        op = row.operator("rzm_weights.open_matrix_cell_editor", text="Edit", icon="GREASEPENCIL")
        op.object_name = cell.object_name
        if cell.plan_index >= 0:
            clear = row.operator("rzm_weights.clear_matrix_cell", text="X", icon="X")
            clear.object_name = cell.object_name
            clear.canonical_name = matrix_row.canonical_name

    editor_object = settings.matrix_editor_object
    if not editor_object:
        return

    edit_box = box.box()
    edit_box.label(text=f"Attach to {matrix_row.canonical_name}: {editor_object}", icon="EYEDROPPER")
    manual = edit_box.row(align=True)
    manual.prop(settings, "matrix_manual_group_index", text="VG index")
    manual.operator("rzm_weights.assign_matrix_manual_index", text="Attach manually", icon="CHECKMARK")

    suggestions = matrix_cell_suggestions(scene, matrix_row.canonical_name, editor_object, limit=8)
    edit_box.label(text="Top 8 theoretical candidates")
    for pair_start in range(0, len(suggestions), 2):
        suggestion_row = edit_box.row(align=True)
        for plan_index, score in suggestions[pair_start: pair_start + 2]:
            item = scene.rzm_weight_plan[plan_index]
            label = f"[{item.group_index:03d}] {item.original_name}  {score * 100:.0f}%  ({item.status[0]})"
            op = suggestion_row.operator("rzm_weights.assign_matrix_suggestion", text=label, icon="LINKED")
            op.plan_index = plan_index
            op.canonical_name = matrix_row.canonical_name


def draw_candidate_buttons(layout, item, item_index):
    row = layout.row(align=True)
    for slot in (1, 2, 3):
        candidate = getattr(item, f"candidate_{slot}")
        score = getattr(item, f"candidate_{slot}_score")
        if candidate:
            op = row.operator("rzm_weights.assign_candidate", text=f"#{slot} {candidate} ({score * 100:.0f}%)")
            op.item_index = item_index
            op.slot = slot


def draw_item_details(layout, scene, item, item_index, approve_button=False, demote_button=False):
    if item is None:
        return
    box = layout.box()
    box.label(text=f"{item.object_name}[{item.group_index:03d}] {item.original_name}", icon="BONE_DATA")
    box.prop(item, "resolved_name", text="Итоговое имя")
    box.label(text=f"Nearest: {item.nearest_bone or '<нет>'} | dist={item.nearest_distance:.4f}")
    box.label(text=f"Confidence={item.confidence:.3f} | margin={item.margin:.3f}")
    if item.decision_reason:
        box.label(text=f"Reason: {item.decision_reason}")
    if item.conflict_cluster:
        box.label(text=f"Rival refs: {item.conflict_cluster}", icon="ERROR")
    draw_candidate_buttons(box, item, item_index)
    row = box.row(align=True)
    op = row.operator("rzm_weights.force_aux_name", text="Отдельная доп. кость")
    op.item_index = item_index
    row.operator("rzm_weights.refresh_overlay", text="Refresh Overlay")
    if approve_button:
        box.operator("rzm_weights.approve_selected_conflict", text="APPROVE CURRENT NAME", icon="CHECKMARK")
    if demote_button:
        box.operator("rzm_weights.demote_approved_detail", text="Вернуть в Conflict")


def draw_approved_tab(layout, scene, settings):
    row = layout.row(align=True)
    row.label(text="Кость | компоненты по исходным VG-индексам")
    row.prop(settings, "matrix_only_incomplete", toggle=True)
    header = layout.row(align=True)
    header.label(text="Bone")
    for component in scene.rzm_component_summary:
        header.label(text=component.object_name)
    layout.template_list("RZM_UL_approved_matrix", "matrix", scene, "rzm_approved_matrix", settings, "approved_row_index", rows=11)
    draw_matrix_target(layout, scene)
    index = settings.approved_detail_index
    if 0 <= index < len(scene.rzm_weight_plan) and scene.rzm_weight_plan[index].status == "APPROVED":
        draw_item_details(layout, scene, scene.rzm_weight_plan[index], index, demote_button=True)


def draw_issue_tab(layout, scene, settings, status):
    draw_matrix_target(layout, scene)
    if status == "CONFLICT":
        layout.template_list("RZM_UL_conflict", "conflicts", scene, "rzm_weight_plan", settings, "conflict_index", rows=10)
    elif status == "UNKNOWN":
        layout.template_list("RZM_UL_unknown", "unknowns", scene, "rzm_weight_plan", settings, "unknown_index", rows=10)
    else:
        layout.template_list("RZM_UL_ignored", "ignored", scene, "rzm_weight_plan", settings, "ignored_index", rows=6)
    item, index = selected_issue_item(scene)
    draw_item_details(layout, scene, item, index, approve_button=(status == "CONFLICT"))
    if status in {"CONFLICT", "UNKNOWN"} and item is not None:
        layout.operator("rzm_weights.assign_selected_to_matrix_row", text="ASSIGN TO SELECTED MATRIX ROW", icon="CHECKMARK")


def draw_base_mesh_setup_ui(self, context, layout):
    scene = context.scene
    settings = scene.rzm_weight_settings
    counts = status_counts(scene)

    actions = layout.box()
    row = actions.row(align=True)
    row.operator("rzm_weights.apply_plan", icon="MOD_ARMATURE")
    row.operator("rzm_weights.restore_backup", icon="LOOP_BACK")
    row = actions.row(align=True)
    row.operator("rzm_weights.build_plan", icon="VIEWZOOM")
    row.operator("rzm_weights.clear_plan", icon="TRASH")

    refs = layout.box()
    row = refs.row(align=True)
    row.prop(settings, "target_armature")
    row.prop(settings, "reference_mesh")

    compact = layout.box()
    row = compact.row(align=True)
    row.prop(settings, "approved_threshold", text="Strong")
    row.prop(settings, "conflict_threshold", text="Floor")
    row.prop(settings, "unique_margin", text="Margin")
    row.prop(settings, "assignment_margin", text="Rival")
    row.prop(settings, "unknown_cluster_threshold", text="Merge")
    row = compact.row(align=True)
    row.prop(settings, "create_missing_bones")
    row.prop(settings, "ignore_multiple_toe", toggle=True)
    row.prop(settings, "show_overlay", toggle=True)
    row.prop(settings, "overlay_all_components", toggle=True)
    row.prop(settings, "overlay_point_size", text="Dots")

    if not scene.rzm_weight_plan:
        layout.label(text="Выбери armature + reference, выдели компоненты, построй Plan")
        return

    draw_component_summary(layout, scene)
    tabs = layout.box()
    tabs.prop(settings, "active_tab", expand=True)
    tabs.label(text=f"Approved {counts['APPROVED']} | Conflict {counts['CONFLICT']} | Unknown {counts['UNKNOWN']} | Mask* {counts['IGNORED']}")
    if settings.active_tab == "APPROVED":
        draw_approved_tab(tabs, scene, settings)
    else:
        draw_issue_tab(tabs, scene, settings, settings.active_tab)


classes_to_register = [
    RZM_UL_approved_matrix,
    RZM_UL_weight_plan,
    RZM_UL_conflict,
    RZM_UL_unknown,
    RZM_UL_ignored,
]
