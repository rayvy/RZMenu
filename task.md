# RZMenu Image System — Task List

## Фаза 1: hover_image_id + extramap + Atlas Margin ✅
- [x] atlas_algo.py — ATLAS_MARGIN = 2, margin-aware packing
- [x] image_ops.py — UpdateAtlasLayout: hover + extramap in used_image_ids
- [ ] Modify `dds_packer.py` to add `-srgbi` flag for SRGB formats
- [ ] Research and resolve PNG metadata invisibility in-game
- [x] serialization.py — export/import remap for hover + extramap
- [x] container.j2 — hover block последним в generate_image()
- [x] p_ui.py — extramap_image_id property

## Фаза 2: Animated Images ✅
- [x] core/animated_loader.py — новый модуль (GIF/MP4 deduplication)
- [x] p_images.py — ANIMATED source_type + anim_* поля
- [x] image_ops.py — RZM_OT_AddAnimatedImage, UpdateAtlasLayout пишет anim_frame_coords
- [x] elements_helpers.j2 — if/elif по time для animated
- [x] emulator_ops.py + export — fromjson Jinja2 filter
- [x] deps_manager.py — imageio + imageio-ffmpeg (optional)
- [x] tests/test_atlas_packer.py — unit тесты

## Фаза 3: Dirty Flags ✅
- [x] p_settings.py — atlas_is_dirty + atlas_last_hash в RZMExportSettings
- [x] p_ui.py — update callback на image_id, hover_image_id, extramap_image_id
- [x] p_images.py — update callback на image_pointer, anim_speed_multiplier
- [x] image_ops.py — ExportAtlas dirty check
