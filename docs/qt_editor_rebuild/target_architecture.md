# Целевая структура

Ниже не финальный код, а целевая схема слоёв.

## Предлагаемый верхний уровень

```text
qt-editor/
  docs/
    qt_editor_rebuild/
      README.md
      current_state.md
      target_architecture.md
      migration_plan.md
  apps/
    qt_editor_app/
      main.cpp
      app/
      ui/
      render/
      assets/
  core/
    model/
    serialization/
    commands/
    undo/
    validation/
    io/
  bridge/
    blender/
    transport/
    protocol/
  plugins/
    blender_addon/
    blender_bridge_client/
  tests/
    unit/
    integration/
```

## Роли слоёв

- `core/` - чистая логика редактора без знания о Blender и без GUI-зависимостей
- `ui/` - окно, панели, инспекторы, списки, доки, hotkeys
- `render/` - GPU-отрисовка, canvas, viewport, сценические примитивы
- `bridge/` - обмен сообщениями с Blender или другими внешними источниками данных
- `plugins/blender_addon/` - тонкая оболочка, которая только запускает клиент и передаёт данные

## Что должно остаться в Blender

- минимальный аддон-запускатель
- сбор данных из сцены
- применение команд обратно в Blender
- синхронизация выделения, undo/redo и состояния проекта

## Что должно уйти из Blender

- большая часть UI
- тяжёлая логика редактирования
- GPU viewport
- обработка команд, если её можно перенести в отдельный процесс

## GPU-направление

Для версии, которой можно гордиться в резюме, разумно держать абстракцию рендер-бэкенда:
- `DirectX` как понятный тебе базовый путь на Windows
- `Vulkan` как отдельный backend для опыта и портфолио

Но для архитектуры V1 важнее не API, а изоляция:
- редактор не должен зависеть от конкретного API на уровне бизнес-логики
- backend должен быть заменяемым

