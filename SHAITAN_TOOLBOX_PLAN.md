# Shaitan Toolbox — Plan

UI: Переключатель секции ВНУТРИ RZ Constructor панели (main_ui.py).
Кнопки `RZ Toolbox` / `Shaitan Toolbox` сверху, всё содержимое в `if/elif`.

## Инструменты

| # | Инструмент | Источник | Статус |
|---|-----------|----------|--------|
| 1 | UV Plugin (TexCoord Packer) | `Rayvich_UV_plugin.py` | Перенести логику, `rzm_st.` prefix |
| 2 | Color Attribute Presets | `C:\Blender\Scripts\GI-Vertex Color\*.py` | Операторы для FF8080, FF80CB33, FF80CB66 |
| 3 | Fast VG Sym Rename | `fast_sym_vg_rename_addon.py` | Обёртка над существующей логикой |
| 4 | Body Rename | Пишет сам Rayvich | Placeholder UI (pointer на арматуру + меш-референс + кнопка) |

## Файловая структура

```
RZMenu/
  shaitan_toolbox/
    __init__.py
    ops_uv.py          # apply_uv_math переиспользуется в xxmi_data_predictor
    ops_color_attr.py
    ops_vg_sym.py
    ops_body_rename.py # placeholder
```

## Body Rename Placeholder UI
```
[ Target Armature ] [PointerProperty]
[ Reference Mesh  ] [PointerProperty]
[ Rename Components ] [button — disabled / Coming Soon]
```
Суть: выбрать арматуру, референс-меш, выделить все остальные объекты-компоненты,
нажать кнопку → ренейминг компонентов в человеческий язык тела
(pelvis, hand, arm, head и т.д. вместо абстрактных цифр).

## Примечания
- Standalone файлы (Rayvich_UV_plugin.py, fast_sym_vg_rename_addon.py) — НЕ УДАЛЯТЬ
- Регистрировать через RZMenu/__init__.py
- Добавить `rzm_toolbox_mode` EnumProperty на bpy.types.Scene
