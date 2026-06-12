# Component Resolver Migration Plan

## Цель

Перевести Component Manager из ручного кэша в единый API-слой определения компонентов, партов, объектов и метаданных мода. Старые `PropertyGroup` остаются persistent-хранилищем и UI-слоем, но бизнес-логика постепенно переезжает в resolver.

## Текущая проблема

- `component_manager` сейчас хранит состояние, но не умеет сам надежно определять компоненты.
- `ComponentCollector` первым читает старый snapshot из `component_manager.components[].objects`; если он устарел, новые объекты игнорируются.
- Shape discovery сканирует ручные `shape_discovery_collections`, хотя принадлежность объекта к компоненту уже должна быть известна.
- Разные модули напрямую обходят `scene.rzm.component_manager` и получают разные трактовки одной и той же модели.
- Автообновление шумит в консоль, потому что fallback-сканирование использует verbose `print()`.

## Первый этап: read-only snapshot

Уже вводится легкий `utils/component_resolver.py`.

- Поддержка только XXMI: `GenshinImpact`, `ZenlessZoneZero`, `HonkaiStarRail`.
- Источник данных: `hash.json` + валидный нейминг коллекций Blender.
- Результат хранится компактно в `scene.rzm.component_manager.resolver_snapshot_json`.
- Расчет выполняется один раз после ручного `cm_update_from_dump` или после импорта, который вызывает этот оператор.
- UI только читает snapshot и не сканирует сцену в `draw()`.

## Модель snapshot

```text
snapshot
├─ game
├─ mod_name
├─ source
├─ stats
│  ├─ components
│  ├─ parts
│  └─ mapped_objects
├─ components[]
│  ├─ name
│  ├─ kind
│  ├─ vb0_owner
│  ├─ collections[]
│  ├─ objects[]
│  ├─ parts[]
│  │  ├─ name
│  │  ├─ suffix
│  │  ├─ collections[]
│  │  └─ objects[]
│  └─ textures
│     ├─ Diffuse
│     ├─ LightMap
│     ├─ NormalMap
│     └─ ...
└─ object_index
   └─ object_name -> component / part / collection
```

## XXMI правила

- Компонент может быть solo, если в `hash.json` нет `object_classifications`.
- Если parts есть, IB разбивается по parts.
- VB0/Position остается владельцем всего компонента, не отдельного part.
- Объекты определяются по валидному неймингу коллекций, а не по ручному списку объектов.
- Snapshot должен хранить и component-level, и part-level связи.
- Текстуры компонента фиксируются из `texture_hashes`: тип, формат, количество, несколько хэшей для диагностики.

## EFMI / WWMI

Пока не поддерживаются новым dynamic snapshot.

Планируемая модель проще:

- Только component-level.
- Parts отсутствуют.
- Определение по валидным коллекциям и именам `ComponentN`.
- Рекурсивный обход коллекций.

## API, к которому надо прийти

```python
get_snapshot(context)
rebuild_snapshot(context, source="manual")
resolve_object(context, obj)
get_component(context, name)
get_component_objects(context, name)
get_part_objects(context, component_name, part_name)
iter_components(context)
iter_parts(context, component_name)
get_texture_summary(context, component_name)
```

## Миграция модулей

1. `xzibit_tachka_na_prokachku` UI: показывает snapshot и активное определение объекта.
2. `shape_ops.py`: discovery берет target objects из resolver snapshot; ручные discovery collections остаются override/fallback.
3. `component_collector.py`: сначала читает resolver snapshot, потом cache, потом legacy fallback.
4. `vfx_buffer_patcher.py`: убирает прямой обход `component_manager.components`.
5. `material_transfer_ops.py`: берет список component/part через API.
6. `rztemplate/modules/utils.j2` и shape templates: получают подготовленные данные, а не напрямую лазят в CM.

## Ограничения первого этапа

- Snapshot не пересчитывается в UI draw.
- Snapshot может устареть после ручного переименования коллекций или добавления объектов; его надо обновить через import/update.
- Matching коллекций сделан консервативно через нормализованный prefix; при странных именах коллекций нужна диагностика.
- Старые поля `components[].objects` пока сохраняются для совместимости.

## Следующий безопасный шаг

Перевести `shape_ops.py` на resolver snapshot:

- если snapshot валиден и игра XXMI, брать объекты из `object_index`;
- если snapshot пустой, показывать понятное предупреждение;
- ручные `shape_discovery_collections` оставить как fallback или advanced override;
- не запускать тяжелый rebuild автоматически в discovery.
