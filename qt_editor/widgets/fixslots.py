import re

text = """
    def _add_layer(self):
        rzm = bpy.context.scene.rzm; b = rzm.active_tw_block_index; c = rzm.tw_blocks[b].active_component_index; s = rzm.tw_blocks[b].components[c].active_slot_index
        bpy.ops.rzm.add_tw_decal_layer(block_index=b, comp_index=c, slot_index=s)
    def _rem_layer(self, layer_idx):
        rzm = bpy.context.scene.rzm; b = rzm.active_tw_block_index; c = rzm.tw_blocks[b].active_component_index; s = rzm.tw_blocks[b].components[c].active_slot_index
        bpy.ops.rzm.remove_tw_decal_layer(block_index=b, comp_index=c, slot_index=s, index=layer_idx)
    def _move_layer(self, layer_idx, dir):
        rzm = bpy.context.scene.rzm; b = rzm.active_tw_block_index; c = rzm.tw_blocks[b].active_component_index; s = rzm.tw_blocks[b].components[c].active_slot_index
        bpy.ops.rzm.move_tw_item(collection_name="decal_layers", index=layer_idx, direction=dir, block_index=b, comp_index=c, slot_index=s)

    def _draw_slots_mode(self, block):
        if block.active_component_index < 0: return
        comp = block.components[block.active_component_index]; b_idx = bpy.context.scene.rzm.active_tw_block_index; c_idx = block.active_component_index
        row_sel = QtWidgets.QHBoxLayout(); self.details.layout.addLayout(row_sel)
        row_sel.addWidget(RZLabel("Slots:")); self.tab_slots = RZTabRow(); row_sel.addWidget(self.tab_slots, 1)
        self.tab_slots.sync_items([s.name for s in comp.slots], comp.active_slot_index)
        self.tab_slots.clicked.connect(lambda i: self._set_active("slot", i))
        
        btn_add = RZPushButton("+"); btn_add.setFixedSize(24, 24); btn_add.clicked.connect(self._add_slot); row_sel.addWidget(btn_add)
        btn_rem = RZPushButton("x"); btn_rem.setFixedSize(24, 24); btn_rem.clicked.connect(self._rem_slot); row_sel.addWidget(btn_rem)
        
        if comp.active_slot_index < 0 or comp.active_slot_index >= len(comp.slots): return
        slot = comp.slots[comp.active_slot_index]; s_idx = comp.active_slot_index
        
        l_core = self.details.add_section(f"[{slot.name}] Settings")
        
        # Slot Preview & Info
        r_top = QtWidgets.QHBoxLayout(); l_core.addLayout(r_top)
        self.slot_pre = AtlasPreviewWidget(size=140, parent=self); r_top.addWidget(self.slot_pre)
        
        l_info = QtWidgets.QVBoxLayout(); r_top.addLayout(l_info)
        
        chk_act = RZCheckBox("Active"); chk_act.setChecked(slot.active)
        chk_act.toggled.connect(lambda v: self._item_changed("slots", s_idx, "active", b_idx, c_idx, str(v))); l_info.addWidget(chk_act)
        
        r1 = QtWidgets.QHBoxLayout(); l_info.addLayout(r1)
        e_name = RZLineEdit(); e_name.setText(slot.name); e_name.editingFinished.connect(lambda p=e_name: self._item_changed("slots", s_idx, "name", b_idx, c_idx, p.text()))
        r1.addWidget(RZLabel("Name:")); r1.addWidget(e_name, 1)
        l_info.addStretch()

        p = image_utils.get_resource_path(comp.base_resource_name)
        if not p and block.backdrop_resource_name: p = image_utils.get_resource_path(block.backdrop_resource_name)
        layers = [{"rect": [0, 0, comp.rect[2], comp.rect[3]], "path": p, "opacity": 1.0}]
        if slot.active: layers.append({"rect": list(slot.rect), "path": "", "is_decal": True, "opacity": 1.0})
        w, h = (comp.rect[2], comp.rect[3]) if comp.rect[2] > 0 else (1024, 1024)
        self.slot_pre.update_with_layers(layers, (w, h))

        l_mp = self.details.add_section("Multi-Pass")
        r_mp = QtWidgets.QHBoxLayout(); l_mp.addLayout(r_mp)
        cb_mode = ComboBoxFix(); cb_mode.addItems(["NONE", "DUPLICATE", "INDIVIDUAL"]); cb_mode.setCurrentText(slot.multi_pass_mode)
        cb_mode.currentTextChanged.connect(lambda v: self._item_changed("slots", s_idx, "multi_pass_mode", b_idx, c_idx, v))
        r_mp.addWidget(RZLabel("Mode:")); r_mp.addWidget(cb_mode, 1)

        l_trans = self.details.add_section("Transform")
        r_rect = QtWidgets.QHBoxLayout(); l_trans.addLayout(r_rect); r_rect.addWidget(RZLabel("Rect:"))
        for i in range(4):
            sp = RZSpinBox(); sp.setRange(0, 16384); sp.setValue(slot.rect[i])
            sp.editingFinished.connect(lambda p=sp, ix=i: self._item_changed("slots", s_idx, f"rect[{ix}]", b_idx, c_idx, p.value())); r_rect.addWidget(sp)
            
        r_ops = QtWidgets.QHBoxLayout(); l_trans.addLayout(r_ops)
        r_ops.addWidget(RZLabel("Rot:")); sp_rot = RZSpinBox(); sp_rot.setRange(-360, 360); sp_rot.setValue(slot.rotation)
        sp_rot.editingFinished.connect(lambda p=sp_rot: self._item_changed("slots", s_idx, "rotation", b_idx, c_idx, p.value())); r_ops.addWidget(sp_rot)
        chk_m = RZCheckBox("M"); chk_m.setChecked(slot.mirror); chk_m.toggled.connect(lambda v: self._item_changed("slots", s_idx, "mirror", b_idx, c_idx, str(v))); r_ops.addWidget(chk_m)
        chk_f = RZCheckBox("F"); chk_f.setChecked(slot.flip); chk_f.toggled.connect(lambda v: self._item_changed("slots", s_idx, "flip", b_idx, c_idx, str(v))); r_ops.addWidget(chk_f)

        # DECAL LAYERS GALLERY
        l_layers = self.details.add_section("Decal Layers")
        r_l_top = QtWidgets.QHBoxLayout(); l_layers.addLayout(r_l_top)
        btn_add_l = RZPushButton("+ Layer"); btn_add_l.clicked.connect(self._add_layer); r_l_top.addWidget(btn_add_l)
        r_l_top.addStretch()

        scr = RZTabRow(self); scr.setFixedHeight(140)
        l_layers.addWidget(scr)
        
        pref = getattr(bpy.context.preferences.addons.get('RZMenu'), "preferences", None)
        base_path = pref.mod_base_path if pref else ""
        
        for idx, lyr in enumerate(slot.decal_layers):
            w_lyr = QtWidgets.QFrame()
            w_lyr.setFixedSize(120, 120)
            w_lyr.setStyleSheet("QFrame { background: #1a1e24; border: 1px solid #3E4451; border-radius: 4px; }")
            lyr_l = QtWidgets.QVBoxLayout(w_lyr); lyr_l.setContentsMargins(4, 4, 4, 4); lyr_l.setSpacing(2)
            
            # Header with Name and buttons
            r_head = QtWidgets.QHBoxLayout(); lyr_l.addLayout(r_head)
            e_ln = RZLineEdit(); e_ln.setText(lyr.name)
            e_ln.editingFinished.connect(lambda p=e_ln, ix=idx: self._item_changed("decal_layers", ix, "name", b_idx, c_idx, p.text()))
            r_head.addWidget(e_ln, 1)
            b_up = RZPushButton("<"); b_up.setFixedSize(16, 16); b_up.clicked.connect(lambda _, ix=idx: self._move_layer(ix, "UP")); r_head.addWidget(b_up)
            b_dn = RZPushButton(">"); b_dn.setFixedSize(16, 16); b_dn.clicked.connect(lambda _, ix=idx: self._move_layer(ix, "DOWN")); r_head.addWidget(b_dn)
            b_rm = RZPushButton("x"); b_rm.setFixedSize(16, 16); b_rm.clicked.connect(lambda _, ix=idx: self._rem_layer(ix)); r_head.addWidget(b_rm)
            
            # Sub property Count
            r_cnt = QtWidgets.QHBoxLayout(); lyr_l.addLayout(r_cnt)
            r_cnt.addWidget(RZLabel("Count:"))
            sp_cn = RZSpinBox(); sp_cn.setRange(1, 100); sp_cn.setValue(lyr.count)
            sp_cn.editingFinished.connect(lambda p=sp_cn, ix=idx: self._item_changed("decal_layers", ix, "count", b_idx, c_idx, p.value())); r_cnt.addWidget(sp_cn, 1)

            # Preview
            pre_w = ResourcePreviewWidget(64, self); lyr_l.addWidget(pre_w, alignment=QtCore.Qt.AlignCenter)
            import os
            tex_path = os.path.join(base_path, "TexWorks", "Decals", lyr.name)
            if os.path.exists(tex_path):
                imgs = [f for f in os.listdir(tex_path) if f.lower().endswith(('.png', '.dds', '.tga'))]
                if imgs: pre_w.update_from_path(os.path.join(tex_path, imgs[0]))
                else: pre_w.update_resource("") # which clears
            else: pre_w.update_resource("")
            
            scr.container_layout.addWidget(w_lyr)

        if self.show_details:
            l_warp = self.details.add_section("Warping / Lattice (3x3)")
            for pw in [0, 1]:
                en_prop = f"warp_p{pw}_enabled"; grid_prop = f"warp_p{pw}_grid"
                chk_w = RZCheckBox(f"Pass {pw} Warp"); chk_w.setChecked(getattr(slot, en_prop))
                chk_w.toggled.connect(lambda v, p=en_prop: self._item_changed("slots", s_idx, p, b_idx, c_idx, str(v))); l_warp.addWidget(chk_w)
                if getattr(slot, en_prop):
                    gl = QtWidgets.QGridLayout(); l_warp.addLayout(gl)
                    for i in range(18):
                        sp = RZDoubleSpinBox(); sp.setRange(-1.0, 2.0); sp.setValue(slot.warp_p0_grid[i] if pw==0 else slot.warp_p1_grid[i])
                        sp.editingFinished.connect(lambda p=sp, ix=i, gp=grid_prop: self._item_changed("slots", s_idx, f"{gp}[{ix}]", b_idx, c_idx, p.value()))
                        gl.addWidget(sp, i // 6, i % 6)

            if not TEXWORKS_WIP:
                l_calc = self.details.add_section("UV Calculator")
                rc = QtWidgets.QHBoxLayout(); l_calc.addLayout(rc); rc.addWidget(RZLabel("Pad:")); sp_p = RZSpinBox(); sp_p.setValue(slot.calc_padding)
                sp_p.editingFinished.connect(lambda p=sp_p: self._item_changed("slots", s_idx, "calc_padding", b_idx, c_idx, str(p.value()))); rc.addWidget(sp_p)
                rc.addWidget(RZLabel("Res:")); sp_rx = RZSpinBox(); sp_rx.setRange(1, 16384); sp_rx.setValue(slot.calc_res_x); rc.addWidget(sp_rx)
                sp_ry = RZSpinBox(); sp_ry.setRange(1, 16384); sp_ry.setValue(slot.calc_res_y); rc.addWidget(sp_ry)
                sp_rx.editingFinished.connect(lambda p=sp_rx: self._item_changed("slots", s_idx, "calc_res_x", b_idx, c_idx, str(p.value())))
                sp_ry.editingFinished.connect(lambda p=sp_ry: self._item_changed("slots", s_idx, "calc_res_y", b_idx, c_idx, str(p.value())))

        l_fx = self.details.add_section("Effects & Masking")
        row_h = QtWidgets.QHBoxLayout(); l_fx.addLayout(row_h)
        for h in ["hsv_enabled", "hsv_only", "hsv_mask_enabled"]:
            chk = RZCheckBox(h.replace("hsv_", "").upper()); chk.setChecked(getattr(slot, h))
            chk.toggled.connect(lambda v, ch=h: self._item_changed("slots", s_idx, ch, b_idx, c_idx, str(v))); row_h.addWidget(chk)
        e_hl = RZLineEdit(); e_hl.setPlaceholderText("HSV Link"); e_hl.setText(slot.hsv_link); e_hl.editingFinished.connect(lambda p=e_hl: self._item_changed("slots", s_idx, "hsv_link", b_idx, c_idx, p.text())); row_h.addWidget(e_hl, 1)

        row_m = QtWidgets.QHBoxLayout(); l_fx.addLayout(row_m); chk_m = RZCheckBox("MASK"); chk_m.setChecked(slot.mask_enabled)
        chk_m.toggled.connect(lambda v: self._item_changed("slots", s_idx, "mask_enabled", b_idx, c_idx, str(v))); row_m.addWidget(chk_m)
        e_ms = RZLineEdit(); e_ms.setPlaceholderText("Source"); e_ms.setText(slot.mask_source); e_ms.editingFinished.connect(lambda p=e_ms: self._item_changed("slots", s_idx, "mask_source", b_idx, c_idx, p.text())); row_m.addWidget(e_ms, 1)
        for px in [0, 1]:
            chk = RZCheckBox(f"P{px}"); chk.setChecked(getattr(slot, f"pass{px}_use_mask"))
            chk.toggled.connect(lambda v, lpx=px: self._item_changed("slots", s_idx, f"pass{lpx}_use_mask", b_idx, c_idx, str(v))); row_m.addWidget(chk)

        if not TEXWORKS_WIP:
            row_btn = QtWidgets.QHBoxLayout(); l_fx.addLayout(row_btn)
            btn_c0 = RZPushButton("Calc P0"); btn_c0.clicked.connect(lambda: bpy.ops.rzm.calc_slot_config(block_index=b_idx, comp_index=c_idx, slot_index=s_idx, target_pass=0)); row_btn.addWidget(btn_c0)
            btn_c1 = RZPushButton("Calc P1"); btn_c1.clicked.connect(lambda: bpy.ops.rzm.calc_slot_config(block_index=b_idx, comp_index=c_idx, slot_index=s_idx, target_pass=1)); row_btn.addWidget(btn_c1)
            btn_isl = RZPushButton("Calc Split Island"); btn_isl.clicked.connect(lambda: bpy.ops.rzm.calc_splitted_island_config(block_index=b_idx, comp_index=c_idx, slot_index=s_idx)); row_btn.addWidget(btn_isl)
            btn_em = RZPushButton("Easy Mask"); btn_em.clicked.connect(lambda: bpy.ops.rzm.tw_create_easy_mask(block_idx=b_idx, comp_idx=c_idx, slot_idx=s_idx)); row_btn.addWidget(btn_em)

"""

import sys
with open('texworks_panel.py', 'r', encoding='utf-8') as f:
    orig = f.read()

# Replace _draw_slots_mode
part1 = orig.split('    def _draw_slots_mode(self, block):')[0]
part2 = orig.split('def _item_changed(self, coll, idx, prop, b, c, val=None):')[1]

new_content = part1 + text + "    def _item_changed(self, coll, idx, prop, b, c, val=None):\n" + part2

with open('texworks_panel.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print('Success rewriting slots mode!')
