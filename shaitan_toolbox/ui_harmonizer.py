import bpy
from bpy.types import UIList

from .harmonizer_utils import (
    status_counts,
    selected_approved_row,
    selected_issue_item,
    matrix_cell_suggestions,
    tag_view3d_redraw,
)


def get_existing_helpers(scene, armature_obj):
    helpers = set()
    for item in scene.rzm_weight_plan:
        if item.resolved_name and item.is_helper:
            helpers.add(item.resolved_name)
    return sorted(list(helpers))


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


class RZM_UL_object_weight_plan(UIList):
    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        active_obj = context.active_object
        if not active_obj:
            return [], []
        return [self.bitflag_filter_item if item.object_name == active_obj.name else 0 for item in items], []

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        active_vg = context.active_object.vertex_groups.active
        is_active = active_vg is not None and active_vg.index == item.group_index
        
        op = row.operator("rzm_weights.switch_active_vg", text=f"[{item.group_index:03d}] {item.original_name}", depress=is_active)
        op.group_index = item.group_index
        
        row.label(text="→")
        row.prop(item, "resolved_name", text="")
        
        status_icon = "CHECKMARK" if item.status == "APPROVED" else \
                      "ERROR" if item.status == "CONFLICT" else \
                      "QUESTION" if item.status == "UNKNOWN" else "CANCEL"
        row.label(text="", icon=status_icon)


def draw_weight_paint_helper(layout, context, scene, settings):
    active_obj = context.active_object
    active_vg = active_obj.vertex_groups.active
    
    box = layout.box()
    box.label(text=f"Weight Paint Helper: {active_obj.name}", icon='WPAINT_HLT')
    
    if not scene.rzm_weight_plan:
        box.label(text="Remap Plan empty. Build Plan first.", icon='INFO')
        return

    row_list = box.row()
    row_list.template_list("RZM_UL_object_weight_plan", "", scene, "rzm_weight_plan", settings, "object_plan_index", rows=6)

    if active_vg:
        plan_item = None
        plan_item_idx = -1
        for idx, item in enumerate(scene.rzm_weight_plan):
            if item.object_name == active_obj.name and item.group_index == active_vg.index:
                plan_item = item
                plan_item_idx = idx
                break
                
        if plan_item:
            det = box.box()
            status_icon = "CHECKMARK" if plan_item.status == "APPROVED" else \
                          "ERROR" if plan_item.status == "CONFLICT" else \
                          "QUESTION" if plan_item.status == "UNKNOWN" else "CANCEL"
            
            row_title = det.row(align=True)
            row_title.label(text=f"Active: [{plan_item.group_index:03d}] {plan_item.original_name}", icon='BONE_DATA')
            row_title.label(text=f"Status: {plan_item.status}", icon=status_icon)
            
            row_attach = det.row(align=True)
            row_attach.prop(plan_item, "resolved_name", text="Attachment")
            if plan_item.resolved_name:
                row_attach.prop(plan_item, "is_helper", text="Helper", toggle=True)

            # 1. Cluster Info box (Moved Up)
            if plan_item.cluster_id:
                cl_box = det.box()
                cl_box.label(text=f"Cluster: {plan_item.cluster_id} (Sync Mode)", icon='GROUP')
                
                members = [other for other in scene.rzm_weight_plan if other.cluster_id == plan_item.cluster_id and other != plan_item]
                if members:
                    row_memb = cl_box.row()
                    col_m = row_memb.column()
                    col_m.label(text="Synced other objects:")
                    for m in members:
                        col_m.label(text=f"  * {m.object_name}[{m.group_index:03d}] {m.original_name} (→ {m.resolved_name or '—'})")
                
                row_split = cl_box.row(align=True)
                op_split = row_split.operator("rzm_weights.cluster_split_item", text="Remove from Cluster", icon='UNLINKED')
                op_split.plan_index = plan_item_idx
                
                op_disband = row_split.operator("rzm_weights.cluster_disband", text="Disband Cluster", icon='X')
                op_disband.cluster_id = plan_item.cluster_id
            else:
                row_join = det.row(align=True)
                row_join.operator("wm.call_menu", text="Join / Create Cluster...", icon='LINKED').name = "RZM_MT_cluster_merge_candidates"

            # 2. Helper attachment options (Limited to 5 by default)
            armature_obj = settings.target_armature
            helpers = get_existing_helpers(scene, armature_obj)

            box_hlp = det.box()
            row_hlp_title = box_hlp.row()
            row_hlp_title.label(text="Helper Bones:", icon='BONE_DATA')
            row_hlp_title.prop(settings, "show_all_helpers", text="All", toggle=True)

            new_hlp_name = f"hlp_{plan_item.original_name}"
            op_new = row_hlp_title.operator("rzm_weights.quick_attach_bone", text=f"Create {new_hlp_name}", icon='ADD')
            op_new.bone_name = new_hlp_name
            op_new.object_name = plan_item.object_name
            op_new.group_index = plan_item.group_index
            op_new.is_helper = True

            filtered_helpers = [h for h in helpers if h != new_hlp_name]
            if filtered_helpers:
                col_hlp = box_hlp.column(align=True)
                
                display_helpers = filtered_helpers
                is_truncated = False
                if not settings.show_all_helpers and len(filtered_helpers) > 5:
                    display_helpers = filtered_helpers[:5]
                    is_truncated = True

                for hlp_name in display_helpers:
                    row_h = col_hlp.row(align=True)
                    op_h = row_h.operator("rzm_weights.quick_attach_bone", text=f"Attach to {hlp_name}", icon='LINKED')
                    op_h.bone_name = hlp_name
                    op_h.object_name = plan_item.object_name
                    op_h.group_index = plan_item.group_index
                    op_h.is_helper = True

                if is_truncated:
                    row_more = col_hlp.row()
                    row_more.alignment = 'CENTER'
                    row_more.label(text=f"... and {len(filtered_helpers) - 5} more helpers (toggle 'All' to show)")

            # 3. Nearest & Candidates Info
            row_info = det.row(align=True)
            row_info.label(text=f"Nearest: {plan_item.nearest_bone or '—'} ({plan_item.nearest_distance:.3f} m)")
            
            row_cands = det.row(align=True)
            for slot in (1, 2, 3):
                cand = getattr(plan_item, f"candidate_{slot}")
                score = getattr(plan_item, f"candidate_{slot}_score")
                if cand:
                    op = row_cands.operator("rzm_weights.assign_candidate", text=f"#{slot} {cand} ({score*100:.0f}%)")
                    op.item_index = plan_item_idx
                    op.slot = slot
        else:
            box.label(text="Active VG not in Plan", icon='WARNING')
    else:
        box.label(text="Select a Vertex Group to paint", icon='INFO')


def draw_component_summary(layout, scene):
    box = layout.box()
    box.label(text="Component occupancy", icon="INFO")
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
        layout.label(text="Matrix target: <none selected>")
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
    box.prop(item, "resolved_name", text="Resolved name")
    box.label(text=f"Nearest: {item.nearest_bone or '<none>'} | dist={item.nearest_distance:.4f}")
    box.label(text=f"Confidence={item.confidence:.3f} | margin={item.margin:.3f}")
    if item.decision_reason:
        box.label(text=f"Reason: {item.decision_reason}")
    if item.conflict_cluster:
        box.label(text=f"Rival refs: {item.conflict_cluster}", icon="ERROR")
    draw_candidate_buttons(box, item, item_index)
    row = box.row(align=True)
    op = row.operator("rzm_weights.force_aux_name", text="Separate helper bone")
    op.item_index = item_index
    row.operator("rzm_weights.refresh_overlay", text="Refresh Overlay")
    if approve_button:
        box.operator("rzm_weights.approve_selected_conflict", text="APPROVE CURRENT NAME", icon="CHECKMARK")
    if demote_button:
        box.operator("rzm_weights.demote_approved_detail", text="Return to Conflict")


def draw_approved_tab(layout, scene, settings):
    row = layout.row(align=True)
    row.label(text="Bone | components by source VG indices")
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


def draw_clusters_tab(layout, scene, settings):
    plan = scene.rzm_weight_plan
    clusters = {}
    for idx, item in enumerate(plan):
        if item.cluster_id:
            clusters.setdefault(item.cluster_id, []).append((idx, item))

    layout.label(text="Clusters Management", icon='GROUP')

    active_obj = bpy.context.active_object
    active_cid = None
    if active_obj and active_obj.type == 'MESH':
        active_vg = active_obj.vertex_groups.active
        if active_vg:
            row_join = layout.row()
            row_join.label(text=f"Active: {active_obj.name} | {active_vg.name}")
            row_join.operator("wm.call_menu", text="Join other group...", icon='LINKED').name = "RZM_MT_cluster_merge_candidates"
            for item in plan:
                if item.object_name == active_obj.name and item.group_index == active_vg.index:
                    active_cid = item.cluster_id
                    break
        else:
            layout.label(text="Select a vertex group in Blender to start manual clustering", icon='INFO')
    else:
        layout.label(text="Select a mesh object in Blender to start manual clustering", icon='INFO')

    layout.separator()

    if not clusters:
        layout.label(text="No clusters currently found. Run plan or join groups manually.", icon='INFO')
        return

    sorted_cids = sorted(clusters.keys())
    if active_cid and active_cid in clusters:
        sorted_cids.remove(active_cid)
        sorted_cids.insert(0, active_cid)

    for cid in sorted_cids:
        members = clusters[cid]
        box = layout.box()
        row_header = box.row()
        is_active_highlight = " (Active)" if cid == active_cid else ""
        row_header.label(text=f"Cluster: {cid}{is_active_highlight} ({len(members)} members)", icon='GROUP')
        op_disband = row_header.operator("rzm_weights.cluster_disband", text="Disband", icon='X')
        op_disband.cluster_id = cid

        for idx, item in members:
            row_memb = box.row()
            row_memb.label(text=f"  * {item.object_name} | {item.original_name} (→ {item.resolved_name or '—'})")
            op_split = row_memb.operator("rzm_weights.cluster_split_item", text="", icon='UNLINKED')
            op_split.plan_index = idx


def draw_base_mesh_setup_ui(self, context, layout):
    scene = context.scene
    settings = scene.rzm_weight_settings
    counts = status_counts(scene)

    actions = layout.box()
    if scene.rzm_weight_plan:
        row = actions.row(align=True)
        row.operator("rzm_weights.apply_plan", icon="MOD_ARMATURE")
        row.operator("rzm_weights.restore_backup", icon="LOOP_BACK")
        row = actions.row(align=True)
        row.operator("rzm_weights.build_plan", icon="VIEWZOOM")
        row.operator("rzm_weights.clear_plan", icon="TRASH")
    else:
        actions.operator("rzm_weights.build_plan", icon="VIEWZOOM")

    refs = layout.box()
    row = refs.row(align=True)
    row.prop(settings, "target_armature")
    row.prop(settings, "reference_mesh")

    compact = layout.box()
    row = compact.row(align=True)
    row.prop(settings, "approved_threshold", text="Strong")
    row.prop(settings, "conflict_threshold", text="Floor")
    row.prop(settings, "unique_margin", text="Margin")
    row = compact.row(align=True)
    row.prop(settings, "assignment_margin", text="Rival")
    row.prop(settings, "unknown_cluster_threshold", text="Merge")
    row.prop(settings, "consensus_threshold", text="Consensus")
    row = compact.row(align=True)
    row.prop(settings, "create_missing_bones")
    row.prop(settings, "ignore_multiple_toe", toggle=True)
    row.prop(settings, "show_overlay", toggle=True)
    row.prop(settings, "overlay_all_components", toggle=True)
    row.prop(settings, "overlay_point_size", text="Dots")

    active_obj = context.active_object
    is_wpaint = active_obj and active_obj.type == 'MESH' and (active_obj.mode == 'WEIGHT_PAINT' or context.mode == 'PAINT_WEIGHT')
    if is_wpaint:
        layout.separator()
        draw_weight_paint_helper(layout, context, scene, settings)

    if not scene.rzm_weight_plan:
        layout.label(text="Select an armature + reference, choose the components, then build the plan")
        return

    num_clusters = len({item.cluster_id for item in scene.rzm_weight_plan if item.cluster_id})
    draw_component_summary(layout, scene)
    tabs = layout.box()
    tabs.prop(settings, "active_tab", expand=True)
    tabs.label(text=f"Approved {counts['APPROVED']} | Conflict {counts['CONFLICT']} | Unknown {counts['UNKNOWN']} | Mask* {counts['IGNORED']} | Clusters {num_clusters}")
    if settings.active_tab == "APPROVED":
        draw_approved_tab(tabs, scene, settings)
    elif settings.active_tab == "CLUSTERS":
        draw_clusters_tab(tabs, scene, settings)
    else:
        draw_issue_tab(tabs, scene, settings, settings.active_tab)


classes_to_register = [
    RZM_UL_approved_matrix,
    RZM_UL_weight_plan,
    RZM_UL_conflict,
    RZM_UL_unknown,
    RZM_UL_ignored,
    RZM_UL_object_weight_plan,
]
